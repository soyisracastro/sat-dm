"""Cotizaciones en modo BORRADOR: lee el alias cotizaciones@, arma la cotización
en PDF de marca y la deja como borrador para que Israel revise y envíe — este
agente NO envía nada solo (regla v1, igual que soporte.py).

Hermano de `soporte.py`: reutiliza su mecánica de IMAP (buscar al alias, dejar
borrador hilado con send-as, dedup por Message-ID, readonly). Dos modos:

  - **directo**: un cliente escribe a cotizaciones@. El agente identifica qué
    quiere, arma la bitácora (historial de correos con ese cliente) y cotiza con
    precios del CATÁLOGO (data/productos.json). Si el producto/cantidad no está
    claro, deja nota a Israel en vez de inventar.
  - **forward**: Israel reenvía (o escribe) al alias con el contexto del cliente
    (p. ej. lo que se habló por WhatsApp). Su texto es fuente de confianza: puede
    fijar concepto/precio libres además del catálogo.

Guardrails: el contenido del correo es dato NO confiable — el precio sale del
catálogo (o del texto de Israel en modo forward); los datos bancarios salen
SIEMPRE de data/emisor.json, nunca del correo. Nunca envía: solo borrador.

Uso:
    python agents/cotizaciones.py            # corre (si está encendido)
    python agents/cotizaciones.py --dry-run  # imprime el plan, no toca nada

Kill switch: OPS_COTIZACIONES_ENABLED != "1" → no hace nada (default APAGADO).
Reutiliza las credenciales de soporte@: SOPORTE_EMAIL + SOPORTE_APP_PASSWORD
(cotizaciones@ es un send-as sobre la misma cuenta real).
"""

from __future__ import annotations

import email
import email.utils
import html as html_mod
import imaplib
import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from lib import buzon, correo, cotizacion_pdf, llm

# Plumbing de correo entrante, reutilizado del agente hermano (misma cuenta,
# mismos filtros). Single source of truth; no se duplica.
from agents.soporte import (
    _buscar_al_alias,
    _carpeta_borradores,
    _cuerpo_texto,
    _decodificar,
    _es_automatico,
)

ESTADO = Path("/data/cotizaciones_estado.json")
DATA = Path(__file__).resolve().parent.parent / "data"
MAX_PROCESADOS_GUARDADOS = 500

MESES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]

SISTEMA = (
    "Eres el asistente de cotizaciones de TodoConta (Israel Castro), que revende "
    "licencias de software fiscal (XMLSAT Premium) a despachos y empresas en "
    "México. Lees un correo y devuelves SOLO un JSON con los datos de la "
    "cotización y el cuerpo del correo de respuesta al cliente. "
    "REGLA DE ORO: NUNCA inventes precios. Tú solo identificas el `sku` del "
    "catálogo y la `cantidad`; el precio lo pone el sistema. En modo 'forward' "
    "(el correo viene de Israel con contexto), y SOLO ahí, puedes usar "
    "`concepto_libre` + `precio_libre` si Israel los especifica en su texto. "
    "El cuerpo del correo: español de México, cálido y directo, breve, SIN "
    "guion largo (raya), firmando como 'Israel Castro' con 'TodoConta' y el "
    "WhatsApp +52 (55) 4475-3602. NO incluyas los datos bancarios en el cuerpo "
    "(van en el PDF adjunto). Ofrece factura así: 'Si desean factura, con los "
    "datos que ya tengo la puedo generar de una vez para que programen su pago.' "
    "Si el correo no es una solicitud de cotización, ponlo en "
    "`es_solicitud_cotizacion: false`."
)


# ─────────────────────────── helpers puros (testeables) ───────────────────────────

def _cargar_json(nombre: str) -> dict:
    return json.loads((DATA / nombre).read_text())


def _cargar_estado() -> dict:
    if ESTADO.exists():
        try:
            estado = json.loads(ESTADO.read_text())
            estado.setdefault("procesados", [])
            estado.setdefault("folio_seq", {})
            return estado
        except Exception:  # noqa: BLE001
            pass
    return {"procesados": [], "folio_seq": {}}


def _fecha_es(dt: datetime) -> str:
    return f"{dt.day:02d} de {MESES[dt.month - 1]} de {dt.year}"


def _slug_cliente(nombre: str) -> str:
    base = unicodedata.normalize("NFKD", nombre or "").encode("ascii", "ignore").decode()
    palabras = base.split()
    palabra = palabras[0] if palabras else "CLIENTE"
    slug = re.sub(r"[^A-Za-z0-9]+", "", palabra).upper()
    return slug[:16] or "CLIENTE"


def _primer_correo_cliente(cuerpo: str, excluir: set[str]) -> str:
    """En modo forward, adivina el correo del cliente citado en el cuerpo."""
    for c in re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", cuerpo or ""):
        if c.lower() not in excluir:
            return c
    return ""


def _formatear_bitacora(hilos: list[dict] | None) -> str:
    if not hilos:
        return "(sin historial previo con este cliente)"
    lineas = []
    for h in hilos:
        lineas.append(
            f"- [{h.get('fecha','')}] de {h.get('de','')} · {h.get('asunto','')}\n"
            f"  {h.get('extracto','')[:300]}"
        )
    return "\n".join(lineas)


def _resolver_items(items_llm: list[dict], catalogo: dict, modo: str) -> tuple[list[dict], list[str]]:
    """Convierte los items del LLM en líneas cotizables con precio del catálogo.

    Devuelve (items_resueltos, faltantes). NO inventa precios: un sku
    desconocido o una cantidad inválida no se cotiza, se reporta como faltante.
    En modo 'forward' se acepta concepto_libre + precio_libre (Israel es fuente
    de confianza).
    """
    resueltos: list[dict] = []
    faltantes: list[str] = []
    for it in items_llm or []:
        try:
            cantidad = int(it.get("cantidad"))
        except (TypeError, ValueError):
            cantidad = 0
        sku = (it.get("sku") or "").strip().lower()
        concepto_libre = (it.get("concepto_libre") or "").strip()
        precio_libre = it.get("precio_libre")

        if cantidad <= 0:
            faltantes.append(f"cantidad no clara para «{sku or concepto_libre or '?'}»")
            continue

        if sku and sku in catalogo:
            prod = catalogo[sku]
            resueltos.append({
                "concepto": prod.get("conceptoRenovacion") or prod["nombre"],
                "cantidad": cantidad,
                "precioUnitario": float(prod["precioUnitario"]),
            })
        elif modo == "forward" and concepto_libre and precio_libre is not None:
            try:
                resueltos.append({
                    "concepto": concepto_libre,
                    "cantidad": cantidad,
                    "precioUnitario": float(precio_libre),
                })
            except (TypeError, ValueError):
                faltantes.append(f"precio no numérico para «{concepto_libre}»")
        else:
            faltantes.append(
                f"«{sku or concepto_libre or '?'}» (x{cantidad}) no está en el catálogo — falta precio"
            )
    return resueltos, faltantes


def _prompt_llm(modo: str, catalogo: dict, correo_cliente: str, bitacora: str,
                de_nombre: str, de_email: str, asunto: str, cuerpo: str) -> str:
    catalogo_desc = "\n".join(
        f'- sku "{k}": {v["nombre"]} (${v["precioUnitario"]:,.2f} MXN, IVA inc.)'
        for k, v in catalogo.items()
    )
    esquema = (
        '{"es_solicitud_cotizacion": true|false, '
        '"cliente": {"nombre": "", "atencion": "", "email": "", "rfc": ""}, '
        '"items": [{"sku": "sku-del-catalogo o null", "concepto_libre": "solo modo forward o null", '
        '"cantidad": n, "precio_libre": null}], '
        '"asunto": "asunto del correo de respuesta", '
        '"cuerpo_correo": "texto plano con saltos \\n", '
        '"notas_para_israel": "dudas o datos faltantes, vacío si no hay"}'
    )
    return (
        f"MODO: {modo}\n"
        f"CATÁLOGO (única fuente de precios en modo directo):\n{catalogo_desc}\n\n"
        f"CORREO DEL CLIENTE (probable): {correo_cliente or '(desconocido)'}\n\n"
        f"BITÁCORA (historial con el cliente):\n{bitacora}\n\n"
        f"── CORREO RECIBIDO ──\nDE: {de_nombre} <{de_email}>\nASUNTO: {asunto}\n\n{cuerpo}\n\n"
        f"Responde SOLO este JSON:\n{esquema}"
    )


def _construir_borrador(alias: str, cliente: dict, asunto_resp: str, cuerpo_correo: str,
                        pdf_bytes: bytes, folio: str, modo: str, message_id: str) -> MIMEMultipart:
    """Arma el borrador (cuerpo de texto + PDF adjunto), send-as del alias.

    Hila SOLO en modo directo (el hilo es del cliente); en forward el Message-ID
    es del reenvío de Israel, así que se crea un correo nuevo sin In-Reply-To.
    """
    salida = MIMEMultipart()
    salida["From"] = f"TodoConta <{alias}>"
    if cliente.get("email"):
        salida["To"] = email.utils.formataddr(
            (cliente.get("atencion") or cliente["nombre"], cliente["email"])
        )
    salida["Subject"] = (
        asunto_resp if asunto_resp.lower().startswith(("re:", "cotiz"))
        else f"Cotización — {cliente['nombre']}"
    )
    if modo == "directo" and message_id:
        salida["In-Reply-To"] = message_id
        salida["References"] = message_id
    salida.attach(MIMEText(cuerpo_correo, "plain", "utf-8"))
    adjunto = MIMEApplication(pdf_bytes, _subtype="pdf")
    adjunto.add_header("Content-Disposition", "attachment", filename=f"{folio}.pdf")
    salida.attach(adjunto)
    return salida


def _siguiente_folio(estado: dict, slug: str, dt: datetime) -> str:
    anio = str(dt.year)
    seq = int(estado.get("folio_seq", {}).get(anio, 0)) + 1
    estado.setdefault("folio_seq", {})[anio] = seq
    return f"COT-{slug}-{anio}-{seq:02d}"


# ─────────────────────────────────── main ───────────────────────────────────

def main() -> int:  # noqa: C901
    dry_run = "--dry-run" in sys.argv
    if os.environ.get("OPS_COTIZACIONES_ENABLED", "0") != "1" and not dry_run:
        print("[cotizaciones] apagado por OPS_COTIZACIONES_ENABLED — no se hace nada")
        return 0

    cuenta = os.environ.get("SOPORTE_EMAIL")
    password = os.environ.get("SOPORTE_APP_PASSWORD")
    if not cuenta or not password:
        print("[cotizaciones] faltan SOPORTE_EMAIL/SOPORTE_APP_PASSWORD")
        return 1
    alias = os.environ.get("COTIZACIONES_ALIAS", "cotizaciones@todoconta.com")
    ventana = int(os.environ.get("COTIZACIONES_VENTANA_DIAS", "2"))
    max_corrida = int(os.environ.get("OPS_COTIZACIONES_MAX", "10"))
    # Direcciones que cuentan como "Israel" → activan el modo forward (confianza).
    israel_dirs = {
        d.strip().lower()
        for d in (
            os.environ.get("COTIZACIONES_REMITENTES_ISRAEL", "")
            or f"{cuenta},israel@todoconta.com,{os.environ.get('REPORTE_TO', 'israel.castro@gmail.com')}"
        ).split(",")
        if d.strip()
    }

    emisor = _cargar_json("emisor.json")
    catalogo = _cargar_json("productos.json")["productos"]
    estado = _cargar_estado()
    procesados: list[str] = estado["procesados"]

    imap = imaplib.IMAP4_SSL(os.environ.get("SOPORTE_IMAP_HOST", "imap.gmail.com"))
    try:
        imap.login(cuenta, password)
        imap.select("INBOX", readonly=True)
        uids = _buscar_al_alias(imap, alias, ventana)
        if not uids:
            print(f"[cotizaciones] sin correos nuevos para {alias}")
            return 0

        borradores = None if dry_run else _carpeta_borradores(imap)
        atendidos = 0
        for uid in uids:
            if atendidos >= max_corrida:
                break
            ok, datos = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if ok != "OK" or not datos or not isinstance(datos[0], tuple):
                continue
            msg = email.message_from_bytes(datos[0][1])
            clave = str(msg.get("Message-ID", "")).strip() or f"uid:{uid.decode()}"
            if clave in procesados:
                continue

            de_nombre, de_email = email.utils.parseaddr(_decodificar(msg.get("From")))
            asunto = _decodificar(msg.get("Subject")) or "(sin asunto)"
            de_lower = de_email.lower()

            # El propio alias (loop) se ignora siempre.
            if de_lower == alias.lower():
                if not dry_run:
                    procesados.append(clave)
                continue

            es_de_israel = de_lower in israel_dirs
            modo = "forward" if es_de_israel else "directo"

            # Auto-respuestas/boletines: descartar SOLO si no es Israel (un forward
            # suyo puede traer cabeceras raras del correo citado).
            if not es_de_israel and _es_automatico(msg, de_email):
                if not dry_run:
                    procesados.append(clave)
                print(f"[cotizaciones] auto/boletín descartado: {de_email} — {asunto[:60]}")
                continue

            cuerpo = _cuerpo_texto(msg)[:8000]

            # Bitácora: historial con el cliente. En directo el cliente es el
            # remitente; en forward, se adivina del correo citado.
            correo_cliente = (
                de_email if modo == "directo"
                else _primer_correo_cliente(cuerpo, israel_dirs | {alias.lower()})
            )
            bitacora = _formatear_bitacora(
                buzon.hilos_con(correo_cliente, n=5) if correo_cliente else None
            )

            resultado_llm = llm.generar_json(
                _prompt_llm(modo, catalogo, correo_cliente, bitacora,
                            de_nombre, de_email, asunto, cuerpo),
                sistema=SISTEMA,
                max_tokens=1500,
            ) or {}

            es_cotizacion = bool(resultado_llm.get("es_solicitud_cotizacion"))
            cli = resultado_llm.get("cliente") or {}
            cliente = {
                "nombre": str(cli.get("nombre") or de_nombre or correo_cliente or "Cliente").strip(),
                "atencion": str(cli.get("atencion") or "").strip(),
                "email": str(cli.get("email") or correo_cliente or "").strip(),
                "rfc": str(cli.get("rfc") or "").strip(),
            }
            items_resueltos, faltantes = _resolver_items(
                resultado_llm.get("items") or [], catalogo, modo
            )
            cuerpo_correo = str(resultado_llm.get("cuerpo_correo") or "").strip()
            asunto_resp = str(resultado_llm.get("asunto") or f"Cotización — {cliente['nombre']}").strip()
            notas = str(resultado_llm.get("notas_para_israel") or "").strip()
            if faltantes:
                notas = (notas + "\n" if notas else "") + "Faltantes: " + "; ".join(faltantes)

            if dry_run:
                total = cotizacion_pdf.total_de(items_resueltos) if items_resueltos else 0
                print(
                    f"\n───── [{modo}] {de_email} — {asunto} ─────\n"
                    f"¿cotización?: {es_cotizacion} · cliente: {cliente['nombre']} <{cliente['email']}>\n"
                    f"items: {items_resueltos or '(ninguno resuelto)'}\n"
                    f"total: ${total:,.2f} MXN\n"
                    f"notas: {notas or '(sin notas)'}\n"
                    f"── CUERPO ──\n{cuerpo_correo or '(sin cuerpo)'}\n"
                )
                atendidos += 1
                continue

            if not es_cotizacion:
                procesados.append(clave)
                print(f"[cotizaciones] no parece cotización: {de_email} — {asunto[:60]}")
                # Aviso ligero a Israel por si es un falso negativo (ingreso en juego).
                _avisar(alias, modo, cliente, [], notas or "El agente no lo vio como cotización.",
                        cuerpo, de_nombre, de_email, asunto, borrador_ok=False, requiere=True)
                continue

            # Sin items cotizables → no hay PDF; se avisa a Israel pidiendo el dato.
            if not items_resueltos:
                procesados.append(clave)
                print(f"[cotizaciones] sin items cotizables: {de_email} — {asunto[:60]}")
                _avisar(alias, modo, cliente, [], notas or "No pude resolver ningún producto/precio.",
                        cuerpo, de_nombre, de_email, asunto, borrador_ok=False, requiere=True)
                continue

            # Armar la cotización.
            ahora = datetime.now(timezone.utc)
            folio = _siguiente_folio(estado, _slug_cliente(cliente["nombre"]), ahora)
            datos_pdf = {
                "emisor": emisor,
                "folio": folio,
                "fecha": _fecha_es(ahora),
                "vigenciaDias": emisor.get("vigenciaDias", 15),
                "cliente": cliente,
                "items": items_resueltos,
            }
            try:
                pdf_bytes = cotizacion_pdf.render(datos_pdf)
            except Exception as e:  # noqa: BLE001
                print(f"[cotizaciones] fallo al renderizar PDF ({folio}): {e}")
                # Revertir el folio consumido y reintentar en la próxima corrida.
                estado["folio_seq"][str(ahora.year)] -= 1
                continue

            deja_borrador = False
            if borradores:
                try:
                    salida = _construir_borrador(
                        alias, cliente, asunto_resp, cuerpo_correo, pdf_bytes, folio,
                        modo, str(msg.get("Message-ID", "")).strip(),
                    )
                    imap.append(
                        f'"{borradores}"',
                        r"(\Draft)",
                        imaplib.Time2Internaldate(ahora.timestamp()),
                        salida.as_bytes(),
                    )
                    deja_borrador = True
                except Exception as e:  # noqa: BLE001
                    print(f"[cotizaciones] no pude dejar el borrador: {e}")

            # Aviso a Israel.
            _avisar(alias, modo, cliente, items_resueltos, notas, cuerpo,
                    de_nombre, de_email, asunto, borrador_ok=deja_borrador,
                    requiere=bool(faltantes), folio=folio)

            # Registro best-effort en CRM (solo si el cliente ya es lead conocido).
            _registrar_crm(cliente, folio, items_resueltos)

            # Marca procesado DESPUÉS del APPEND (idempotencia: evita duplicar el
            # borrador si algo posterior falla).
            procesados.append(clave)
            atendidos += 1
            print(f"[cotizaciones] cotización lista [{modo}]: {de_email} — {folio}")

        if not dry_run:
            estado["procesados"] = procesados[-MAX_PROCESADOS_GUARDADOS:]
            try:
                ESTADO.write_text(json.dumps(estado))
            except Exception as e:  # noqa: BLE001
                print(f"[cotizaciones] estado no guardado: {e}")
        print(f"[cotizaciones] corrida terminada — {atendidos} cotización(es)")
        return 0
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass


def _avisar(alias: str, modo: str, cliente: dict, items: list[dict], notas: str,
            cuerpo: str, de_nombre: str, de_email: str, asunto: str,
            borrador_ok: bool, requiere: bool, folio: str = "") -> None:
    """Correo de aviso a Israel por SES (sin adjunto — el PDF va en el borrador)."""
    total = cotizacion_pdf.total_de(items) if items else 0
    lineas_items = "\n".join(
        f"  · {it['cantidad']} × {it['concepto']} = ${it['cantidad'] * it['precioUnitario']:,.2f}"
        for it in items
    ) or "  (sin items cotizables)"
    nota_borrador = (
        f"El borrador (con el PDF {folio}.pdf) ya está en Borradores, sale como {alias}: revisa y envía."
        if borrador_ok else
        "NO se creó borrador — revisa abajo qué falta."
    )
    etiqueta = "REQUIERE TU DATO" if requiere else "listo para enviar"
    texto = (
        f"[{modo}] {etiqueta}\n"
        f"Cliente: {cliente['nombre']} <{cliente.get('email','')}>"
        f"{' · RFC ' + cliente['rfc'] if cliente.get('rfc') else ''}\n"
        f"{('Folio: ' + folio) if folio else ''}\n\n"
        f"Items:\n{lineas_items}\nTotal: ${total:,.2f} MXN\n\n"
        f"{nota_borrador}\n\n"
        f"Notas: {notas or '(sin notas)'}\n\n"
        f"── CORREO ORIGINAL ──\nDe: {de_nombre} <{de_email}>\nAsunto: {asunto}\n\n{cuerpo[:3000]}"
    )
    html = (
        '<div style="font-family:system-ui,sans-serif;font-size:14px;max-width:640px;color:#111">'
        f"<p><b>[{html_mod.escape(modo)}] {html_mod.escape(etiqueta)}</b><br>"
        f"<b>Cliente:</b> {html_mod.escape(cliente['nombre'])} &lt;{html_mod.escape(cliente.get('email',''))}&gt;"
        f"{(' · RFC ' + html_mod.escape(cliente['rfc'])) if cliente.get('rfc') else ''}<br>"
        f"{('<b>Folio:</b> ' + html_mod.escape(folio)) if folio else ''}</p>"
        f'<div style="white-space:pre-wrap;background:#f6f6f3;border-radius:8px;padding:12px">'
        f"{html_mod.escape(lineas_items)}\nTotal: ${total:,.2f} MXN</div>"
        f"<p><i>{html_mod.escape(nota_borrador)}</i></p>"
        f"<p><b>Notas:</b> {html_mod.escape(notas or '(sin notas)')}</p>"
        f'<h4 style="margin-bottom:4px">Correo original</h4>'
        f'<div style="white-space:pre-wrap;color:#52514e">{html_mod.escape(cuerpo[:3000])}</div></div>'
    )
    try:
        correo.enviar(f"[{alias}] {etiqueta} — {cliente['nombre']}", html, texto)
    except Exception as e:  # noqa: BLE001
        print(f"[cotizaciones] aviso a Israel falló: {e}")


def _registrar_crm(cliente: dict, folio: str, items: list[dict]) -> None:
    """Registra el evento en crm_events SOLO si el cliente ya es un lead conocido
    (evita romper por FK con clientes nuevos). Best-effort."""
    correo_cli = cliente.get("email")
    if not correo_cli:
        return
    try:
        from lib import crm

        leads = crm.sb_get(f"crm_leads?select=id&email=eq.{correo_cli}&limit=1")
        if not leads:
            return
        crm.sb_post("crm_events", {
            "lead_id": leads[0]["id"],
            "tipo": "cotizacion_generada",
            "payload": {
                "agente": "cotizaciones", "folio": folio,
                "total": cotizacion_pdf.total_de(items),
                "items": [{"c": it["concepto"], "q": it["cantidad"]} for it in items],
            },
        })
    except Exception as e:  # noqa: BLE001
        print(f"[cotizaciones] crm no registrado (best-effort): {e}")


if __name__ == "__main__":
    raise SystemExit(main())

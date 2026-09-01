"""Primer contacto de soycontador.ai en modo BORRADOR: lee los alias del buzón
compartido (hola@, y opcionalmente soporte@/facturacion@), clasifica con Claude
y deja un borrador para que Israel apruebe — este agente NO responde solo
(regla v1, igual que soporte.py y cotizaciones.py).

Hermano de `soporte.py`: reutiliza su plumbing de IMAP (buscar al alias, dejar
borrador hilado con send-as, dedup por Message-ID, readonly). Lo que cambia es
de dónde saca lo que sabe.

DOS CAPAS DE CONOCIMIENTO, y una regla dura
-------------------------------------------
  - **Pública**: `llms-full.txt` del sitio, descargado en cada corrida. Ahí
    viven los precios y el catálogo reales. Se genera en cada build, así que no
    puede desincronizarse del sitio: si Israel cambia un precio en una página,
    el agente se entera solo. El agente CITA, no parafrasea.
  - **Privada**: `data/conocimiento-soycontador.json`. Lo que el sitio no
    publica: fechas tentativas, política de pago, checklist de facturación.

  REGLA DURA: si el dato no está en ninguna de las dos, **no se inventa**. Se
  escala. Sin "aproximadamente", sin deducir, sin multiplicar precios.

Si `llms-full.txt` no se puede descargar, el agente NO redacta desde su memoria:
avisa a Israel del correo entrante y deja el borrador vacío. Un agente que
inventa precios cuando se cae la red es peor que uno que no contesta.

SIN DATOS BANCARIOS a propósito: `hola@` no tiene ninguna razón legítima para
conocerlos, así que ni siquiera entran a su contexto. Eso vive en emisor.json y
sólo lo usa cotizaciones.py, donde sí hacen falta.

Uso:
    python agents/primer_contacto.py            # corre (si está encendido)
    python agents/primer_contacto.py --dry-run  # imprime el plan, no toca nada

Kill switch: OPS_PRIMER_CONTACTO_ENABLED != "1" → no hace nada (default APAGADO).
Reutiliza las credenciales de soporte@: SOPORTE_EMAIL + SOPORTE_APP_PASSWORD
(los alias de soycontador.ai entregan en la misma cuenta real).
"""

from __future__ import annotations

import email
import email.utils
import html as html_mod
import imaplib
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from lib import correo, llm

# Plumbing de correo entrante, reutilizado del agente hermano (misma cuenta,
# mismos filtros). Single source of truth; no se duplica.
from agents.soporte import (
    _buscar_al_alias,
    _carpeta_borradores,
    _cuerpo_texto,
    _decodificar,
    _es_automatico,
)

ESTADO = Path("/data/primer_contacto_estado.json")
DATA = Path(__file__).resolve().parent.parent / "data"
MAX_PROCESADOS_GUARDADOS = 500

LLMS_URL_DEFAULT = "https://soycontador.ai/llms-full.txt"
# Recorte del corpus público: llms-full.txt es de unos pocos KB, pero acotamos
# para que un sitio que crezca no reviente el contexto ni el costo por corrida.
MAX_CHARS_CORPUS = 24000


def _cargar_conocimiento() -> dict:
    ruta = DATA / "conocimiento-soycontador.json"
    return json.loads(ruta.read_text(encoding="utf-8"))


def _descargar_corpus(url: str) -> str | None:
    """Baja llms-full.txt. Devuelve None si falla — el llamador NO debe seguir.

    Que devuelva None en vez de cadena vacía es a propósito: obliga a distinguir
    "el sitio no dice nada de eso" de "no pude leer el sitio".
    """
    try:
        peticion = urllib.request.Request(
            url, headers={"User-Agent": "ops-primer-contacto/1.0 (+soycontador.ai)"}
        )
        with urllib.request.urlopen(peticion, timeout=20) as resp:
            if resp.status != 200:
                print(f"[primer-contacto] {url} devolvió {resp.status}")
                return None
            return resp.read().decode("utf-8", errors="replace")[:MAX_CHARS_CORPUS]
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        print(f"[primer-contacto] no pude descargar {url}: {e}")
        return None


def _sistema(corpus: str, conocimiento: dict) -> str:
    """Arma el prompt de sistema con las dos capas y los límites."""
    voz = conocimiento.get("voz", {})
    return (
        "Eres el asistente de primer contacto de soycontador.ai, la marca "
        "personal de Israel Castro: contador público y desarrollador de "
        "software en México, que capacita a contadores y despachos en IA "
        "aplicada al trabajo fiscal.\n\n"
        "== LO QUE EL SITIO PUBLICA (única fuente de precios y catálogo) ==\n"
        f"{corpus}\n\n"
        "== LO QUE EL SITIO NO PUBLICA (uso interno) ==\n"
        f"{json.dumps(conocimiento, ensure_ascii=False, indent=1)}\n\n"
        "== REGLA DURA ==\n"
        "Si un dato NO está en ninguna de las dos secciones de arriba, NO lo "
        "inventes: marca escalar=true y di en el borrador que lo confirmas con "
        "Israel. Nunca calcules totales de grupo multiplicando un precio "
        "publicado, nunca ofrezcas descuentos, nunca des una fecha que no esté "
        "listada, y nunca menciones datos bancarios (no los tienes).\n\n"
        "== CÓMO ESCRIBES ==\n"
        f"{voz.get('trato', 'Tuteo, español de México.')} "
        f"{voz.get('extension', 'Máximo 150 palabras.')} "
        f"Firmas «{voz.get('firma', 'Israel — soycontador.ai')}». "
        f"{voz.get('transparenciaIA', '')} "
        f"{voz.get('salidaHumana', '')}"
    )


def _cargar_estado() -> dict:
    if ESTADO.exists():
        try:
            return json.loads(ESTADO.read_text())
        except Exception:  # noqa: BLE001
            pass
    return {"procesados": []}


def main() -> int:  # noqa: C901
    dry_run = "--dry-run" in sys.argv
    if os.environ.get("OPS_PRIMER_CONTACTO_ENABLED", "0") != "1" and not dry_run:
        print("[primer-contacto] apagado por OPS_PRIMER_CONTACTO_ENABLED — no se hace nada")
        return 0

    cuenta = os.environ.get("SOPORTE_EMAIL")
    password = os.environ.get("SOPORTE_APP_PASSWORD")
    if not cuenta or not password:
        print("[primer-contacto] faltan SOPORTE_EMAIL/SOPORTE_APP_PASSWORD")
        return 1

    alias_lista = [
        a.strip().lower()
        for a in os.environ.get("PRIMER_CONTACTO_ALIASES", "hola@soycontador.ai").split(",")
        if a.strip()
    ]
    ventana = int(os.environ.get("PRIMER_CONTACTO_VENTANA_DIAS", "2"))
    max_corrida = int(os.environ.get("OPS_PRIMER_CONTACTO_MAX", "10"))

    conocimiento = _cargar_conocimiento()
    corpus = _descargar_corpus(os.environ.get("PRIMER_CONTACTO_LLMS_URL", LLMS_URL_DEFAULT))
    if corpus is None:
        # Sin la capa pública no hay precios verificables. Seguimos para AVISAR
        # a Israel de lo que entró, pero sin redactar nada.
        print("[primer-contacto] sin corpus público: aviso sin borrador")

    estado = _cargar_estado()
    procesados: list[str] = estado.get("procesados", [])

    imap = imaplib.IMAP4_SSL(os.environ.get("SOPORTE_IMAP_HOST", "imap.gmail.com"))
    try:
        imap.login(cuenta, password)
        # readonly: el buzón es el personal de Israel. El agente jamás lo
        # modifica; el borrador va por APPEND a la carpeta Borradores.
        imap.select("INBOX", readonly=True)

        uids: list[bytes] = []
        origen: dict[bytes, str] = {}
        for alias in alias_lista:
            for uid in _buscar_al_alias(imap, alias, ventana):
                if uid not in origen:
                    origen[uid] = alias
                    uids.append(uid)
        if not uids:
            print(f"[primer-contacto] sin correos nuevos para {', '.join(alias_lista)}")
            return 0

        borradores = None if dry_run else _carpeta_borradores(imap)
        atendidos = 0
        for uid in uids:
            if atendidos >= max_corrida:
                break
            alias = origen[uid]
            ok, datos = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if ok != "OK" or not datos or not isinstance(datos[0], tuple):
                continue
            msg = email.message_from_bytes(datos[0][1])
            clave = str(msg.get("Message-ID", "")).strip() or f"uid:{uid.decode()}"
            if clave in procesados:
                continue

            de_nombre, de_email = email.utils.parseaddr(_decodificar(msg.get("From")))
            asunto = _decodificar(msg.get("Subject")) or "(sin asunto)"
            # Correo propio (Israel escribiendo con copia al alias): ignorar.
            if de_email.lower() in {cuenta.lower(), *alias_lista}:
                if not dry_run:
                    procesados.append(clave)
                continue
            if _es_automatico(msg, de_email):
                if not dry_run:
                    procesados.append(clave)
                print(f"[primer-contacto] auto/boletín descartado: {de_email} — {asunto[:60]}")
                continue

            cuerpo = _cuerpo_texto(msg)[:6000]

            if corpus is None:
                categoria, urgencia, escalar = "sin_corpus", "media", True
                resumen = "No se pudo leer llms-full.txt: no redacto para no inventar precios."
                borrador = ""
            else:
                resultado = llm.generar_json(
                    "Clasifica este correo de primer contacto y redacta el "
                    'borrador de respuesta. Responde JSON: {"categoria": '
                    '"prospecto|capacitacion|facturacion|soporte|otro|'
                    'no_requiere_respuesta", "urgencia": "alta|media|baja", '
                    '"escalar": true|false, "motivo_escalar": "por qué, o cadena '
                    'vacía", "resumen": "1-2 oraciones", "borrador": "texto plano '
                    'con saltos \\n (vacío si no requiere respuesta)"}\n\n'
                    f"ENTRÓ POR: {alias}\n"
                    f"DE: {de_nombre} <{de_email}>\nASUNTO: {asunto}\n\nCUERPO:\n{cuerpo}",
                    sistema=_sistema(corpus, conocimiento),
                    max_tokens=1400,
                ) or {}
                categoria = str(resultado.get("categoria") or "sin_clasificar")
                urgencia = str(resultado.get("urgencia") or "media")
                escalar = bool(resultado.get("escalar"))
                resumen = str(resultado.get("resumen") or "")
                borrador = str(resultado.get("borrador") or "").strip()
                motivo = str(resultado.get("motivo_escalar") or "").strip()
                if escalar and motivo:
                    resumen = f"{resumen} · ESCALA: {motivo}"

            if dry_run:
                print(
                    f"\n───── [{alias}] {de_email} — {asunto} ─────\n"
                    f"[{categoria}/{urgencia}]{' ESCALAR' if escalar else ''} {resumen}\n\n"
                    f"BORRADOR:\n{borrador or '(sin respuesta)'}\n"
                )
                atendidos += 1
                continue

            if categoria == "no_requiere_respuesta":
                procesados.append(clave)
                print(f"[primer-contacto] sin respuesta necesaria: {de_email} — {asunto[:60]}")
                continue

            # 1) Borrador hilado en Borradores, saliendo como el alias por el
            #    que entró (hola@ responde hola@, no la cuenta real).
            deja_borrador = False
            if borrador and borradores:
                try:
                    respuesta = MIMEText(borrador, "plain", "utf-8")
                    respuesta["From"] = f"Israel Castro <{alias}>"
                    respuesta["To"] = email.utils.formataddr((de_nombre, de_email))
                    respuesta["Subject"] = (
                        asunto if asunto.lower().startswith("re:") else f"Re: {asunto}"
                    )
                    message_id = str(msg.get("Message-ID", "")).strip()
                    if message_id:
                        respuesta["In-Reply-To"] = message_id
                        respuesta["References"] = message_id
                    imap.append(
                        f'"{borradores}"',
                        r"(\Draft)",
                        imaplib.Time2Internaldate(datetime.now(timezone.utc).timestamp()),
                        respuesta.as_bytes(),
                    )
                    deja_borrador = True
                except Exception as e:  # noqa: BLE001
                    print(f"[primer-contacto] no pude dejar el borrador en Gmail: {e}")

            # 2) Aviso a Israel con todo el contexto.
            nota = (
                f"El borrador está en tu carpeta Borradores (hilado; sale como {alias}): "
                "ajústalo y envía."
                if deja_borrador
                else "No se dejó borrador en Gmail — cópialo de aquí."
            )
            bandera = "⚠️ REQUIERE TU DECISIÓN · " if escalar else ""
            texto_aviso = (
                f"Entró por: {alias}\nDe: {de_nombre} <{de_email}>\nAsunto: {asunto}\n"
                f"Clasificación: {categoria} / urgencia {urgencia}"
                f"{' / ESCALA' if escalar else ''}\n\n"
                f"Resumen: {resumen}\n\n{nota}\n\n"
                f"── BORRADOR PROPUESTO ──\n{borrador or '(sin borrador)'}\n\n"
                f"── MENSAJE ORIGINAL ──\n{cuerpo[:3000]}"
            )
            html_aviso = (
                '<div style="font-family:system-ui,sans-serif;font-size:14px;max-width:640px;color:#111">'
                f"<p><b>Entró por:</b> {html_mod.escape(alias)}<br>"
                f"<b>De:</b> {html_mod.escape(de_nombre)} &lt;{html_mod.escape(de_email)}&gt;<br>"
                f"<b>Asunto:</b> {html_mod.escape(asunto)}<br>"
                f"<b>Clasificación:</b> {html_mod.escape(categoria)} · urgencia {html_mod.escape(urgencia)}"
                f"{' · <b>ESCALA</b>' if escalar else ''}</p>"
                f"<p>{html_mod.escape(resumen)}</p><p><i>{html_mod.escape(nota)}</i></p>"
                '<h4 style="margin-bottom:4px">Borrador propuesto</h4>'
                '<div style="white-space:pre-wrap;background:#f6f6f3;border-radius:8px;padding:12px">'
                f'{html_mod.escape(borrador or "(sin borrador)")}</div>'
                '<h4 style="margin-bottom:4px">Mensaje original</h4>'
                f'<div style="white-space:pre-wrap;color:#52514e">{html_mod.escape(cuerpo[:3000])}</div></div>'
            )
            try:
                correo.enviar(
                    f"[{alias}] {bandera}{urgencia} · {categoria} — {asunto[:70]}",
                    html_aviso,
                    texto_aviso,
                )
            except Exception as e:  # noqa: BLE001
                print(f"[primer-contacto] aviso a Israel falló: {e} — NO registro para reintentar")
                continue

            procesados.append(clave)
            atendidos += 1
            print(
                f"[primer-contacto] atendido: [{alias}] {de_email} — "
                f"{asunto[:60]} [{categoria}/{urgencia}]"
            )

        if not dry_run:
            estado["procesados"] = procesados[-MAX_PROCESADOS_GUARDADOS:]
            try:
                ESTADO.write_text(json.dumps(estado))
            except Exception as e:  # noqa: BLE001
                print(f"[primer-contacto] estado no guardado: {e}")
        print(f"[primer-contacto] corrida terminada — {atendidos} mensaje(s) atendidos")
        return 0
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    raise SystemExit(main())

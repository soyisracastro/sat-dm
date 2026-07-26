"""SDR inbound: primer contacto y seguimientos a leads que llenaron un
formulario de la landing.

Cada hora lee `crm_leads` con consent_marketing=true y fuente en SDR_FUENTES
(opt-in estricto: gente que PIDIÓ algo — nunca suscriptores del newsletter ni
importados). Fuentes activas hoy: `abacus` y `diagnostico` (`qualifier` quedó
fuera a propósito: era la campaña de saldo a favor, pausada).

REGLA DE ORO del primer toque: responder a la intención REAL del lead, no
crearle una. El lead de `abacus` pidió probar el asistente por WhatsApp; el de
`diagnostico` pidió su plan personalizado.

Secuencia de 3 toques (SDR_SEGUIMIENTOS_DIAS, default 3 y 7 días contados
desde el PRIMER correo):

  1. `primer_contacto`  — entrega lo que pidió (etapa lead → mql).
  2. `seguimiento_1`    — día 3: retoma el hilo con UNA pregunta concreta.
  3. `seguimiento_2`    — día 7: cierre honesto ("si no es el momento, te dejo
     de escribir"). Es el último: nunca hay un cuarto correo.

La secuencia se DETIENE en cuanto pasa cualquiera de estas cosas:

  - el lead respondió (se revisa el buzón por IMAP, ver lib/buzon.py) — se
    registra el evento `respuesta_sdr` y ya nadie le vuelve a escribir;
  - un humano tomó la conversación: un evento `nota` con
    `payload.detener_secuencia = true` (lo que se registra cuando Israel le
    escribe a mano; el robot no manda su seguimiento encima);
  - creó su cuenta en la app (existe en `profiles`): ahí lo toma el lifecycle;
  - alguien movió su etapa fuera de `mql` (Israel cerrando a mano);
  - el primer toque quedó fuera de SDR_SEGUIMIENTO_VENTANA_DIAS (default 30):
    una secuencia vieja no revive por un redeploy.

Si el buzón NO se puede revisar (sin credenciales o IMAP caído) el seguimiento
NO sale: preferimos perder un toque a escribirle encima a quien ya contestó.

Cada correo enviado queda en `crm_events` con su **cuerpo completo** — sin eso
no hay forma de saber qué se le prometió a quién.

Límites: OPS_SDR_MAX_DIA correos por día (default 5, cuenta primeros toques y
seguimientos juntos) y SDR_MAX_EDAD_DIAS (default 14) para el primer contacto.

Uso:
    python agents/sdr_inbound.py            # corre (si está encendido)
    python agents/sdr_inbound.py --dry-run  # imprime lo que mandaría, sin tocar nada

Kill switch: OPS_SDR_ENABLED != "1" → no hace nada (default APAGADO).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from lib import buzon, correo, crm, llm

ESTADO = Path("/data/sdr_estado.json")

# QUÉ PIDIÓ la persona. Es contexto para cualquier toque: describe, no manda.
DESCRIPCION_FUENTE = {
    "abacus": (
        "pidió probar Abacus, el asistente fiscal por WhatsApp que forma parte "
        "de TodoConta"
    ),
    "diagnostico": (
        "contestó el diagnóstico en todoconta.com/diagnostico y pidió su plan "
        "personalizado (se le prometió: 'te lo mando mañana — qué automatizar "
        "primero y cuánto tiempo recuperas'). Sus respuestas vienen en `notas`: "
        "rol, RFCs, dolor, volumen, veredicto y tema del post que lo trajo"
    ),
}

# QUÉ DEBE LOGRAR EL PRIMER correo, por fuente. Solo aplica al toque 1: en los
# seguimientos la entrega ya se hizo y repetirla suena a copia y pega.
OBJETIVO_PRIMER_TOQUE = {
    "abacus": (
        "ayudarle a ACTIVAR su prueba de WhatsApp y quedar a la mano; NO "
        "venderle la app de escritorio de entrada. Máximo 120 palabras."
    ),
    "diagnostico": (
        "ESTE correo es la entrega prometida: un mini-plan concreto para SU "
        "caso (por dónde empezar y qué gana), no un saludo genérico. Puede "
        "extenderse hasta ~220 palabras."
    ),
}

# Qué hace cada toque. Los seguimientos NO repiten el argumento del primero:
# cambian de ángulo y bajan la fricción de responder.
INSTRUCCION_TOQUE = {
    "primer_contacto": (
        "Es el PRIMER correo. Cumple el objetivo de la fuente (abajo) y cierra "
        "con una sola pregunta concreta."
    ),
    "seguimiento_1": (
        "Es el SEGUNDO correo, unos días después del primero y sin respuesta. "
        "MÁXIMO 80 PALABRAS, en prosa: nada de listas, pasos numerados, "
        "features ni volver a explicar el plan (eso ya se mandó y repetirlo "
        "suena a copia y pega). Retoma el hilo sin reclamar el silencio y "
        "ofrece UNA cosa concreta y fácil de aceptar: 20 minutos viendo SU "
        "caso con sus propios datos, cargando su e.firma. Una sola pregunta; "
        "si el lead no dejó teléfono, que la pregunta sea pedirle su WhatsApp."
    ),
    "seguimiento_2": (
        "Es el TERCER Y ÚLTIMO correo. MÁXIMO 70 PALABRAS, en prosa, sin "
        "listas ni features. Cierre honesto: dile que ya no le vas a escribir, "
        "deja la puerta abierta por si más adelante le sirve, y pregúntale si "
        "prefiere que lo dejes ahí. Sin culpa, sin descuentos, sin urgencia "
        "inventada."
    ),
}

SISTEMA = (
    "Eres el asistente comercial de Israel Castro, contador y creador de "
    "TodoConta (todoconta.com): app de escritorio que automatiza la descarga "
    "masiva de CFDI y documentos del SAT para contadores en México (prueba "
    "gratis 15 días; plan Anual $2,990 MXN; Anual con IA $4,990 MXN, que "
    "incluye a Abacus, el asistente fiscal por WhatsApp — Abacus es un feature "
    "del paquete TodoConta, no un producto aparte). Escribes correos a una "
    "persona que llenó un formulario en el sitio. La regla de oro: responde a "
    "la intención REAL de lo que la persona pidió (viene en el contexto de la "
    "fuente) — no le vendas otra cosa. Reglas de forma: español de México, tono "
    "personal de Israel (directo, servicial, cero plantilla corporativa), UNA "
    "sola pregunta concreta al final que invite a responder, sin listas de "
    "features, sin presión de venta, sin enlaces salvo que el contexto lo pida. "
    "Nunca digas «CIEC» (di «Contraseña del SAT»). Nunca inventes datos del lead."
)


def _estado_hoy() -> dict:
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if ESTADO.exists():
        try:
            datos = json.loads(ESTADO.read_text())
            if datos.get("fecha") == hoy:
                return datos
        except Exception:  # noqa: BLE001
            pass
    return {"fecha": hoy, "enviados": 0}


def _fecha(iso: str) -> datetime:
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def _eventos_sdr(lead_id: str) -> list[dict]:
    return crm.sb_get(
        f"crm_events?select=tipo,payload,created_at&lead_id=eq.{lead_id}"
        "&tipo=in.(email_enviado,respuesta_sdr,nota)&order=created_at.asc"
    )


def _detenido(eventos: list[dict]) -> bool:
    """¿Ya cerró esta conversación alguien más?

    Dos formas: el lead respondió (`respuesta_sdr`), o un humano tomó la
    conversación y lo dejó por escrito — un evento `nota` con
    `payload.detener_secuencia = true`. Ese segundo caso es el normal: Israel le
    escribe a mano a un lead y el robot NO debe mandarle su seguimiento encima.
    Pasó con el primer lead del diagnóstico el 2026-07-26.

    Se exige la bandera explícita: una `nota` cualquiera no mata la secuencia en
    silencio.
    """
    for e in eventos:
        if e.get("tipo") == "respuesta_sdr":
            return True
        if e.get("tipo") == "nota" and (e.get("payload") or {}).get("detener_secuencia"):
            return True
    return False


def _hay_contacto_previo(eventos: list[dict]) -> bool:
    """Cualquier correo ya enviado (por el SDR o por otro flujo) o un cierre."""
    return any(
        e.get("tipo") in ("email_enviado", "respuesta_sdr") for e in eventos
    ) or _detenido(eventos)


def _toques_del_sdr(eventos: list[dict]) -> list[dict]:
    return [
        e
        for e in eventos
        if e.get("tipo") == "email_enviado"
        and (e.get("payload") or {}).get("agente") == "sdr"
    ]


def _ya_tiene_cuenta(email: str) -> bool | None:
    """True/False si se pudo consultar; None si Supabase falló (→ no mandamos)."""
    try:
        return bool(crm.sb_get(f"profiles?select=id&email=eq.{quote(email)}&limit=1"))
    except Exception as e:  # noqa: BLE001
        print(f"[sdr] no pude verificar si {email} ya tiene cuenta: {e}")
        return None


def _rubrica_fallback(lead: dict) -> tuple[int, str]:
    """Scoring sin LLM: señales simples de la fila."""
    score = 40
    razones = []
    if lead.get("fuente") == "abacus":
        score += 20
        razones.append("pidió el trial de Abacus (intención alta)")
    if lead.get("telefono"):
        score += 15
        razones.append("dejó teléfono")
    dominio = (lead.get("email") or "").split("@")[-1].lower()
    if dominio and dominio not in (
        "gmail.com", "hotmail.com", "outlook.com", "yahoo.com", "icloud.com", "live.com.mx",
    ):
        score += 15
        razones.append(f"correo de dominio propio ({dominio})")
    if lead.get("nombre"):
        score += 5
        razones.append("dejó nombre")
    return min(score, 100), "; ".join(razones) or "sin señales adicionales"


def _correo_fallback(lead: dict, plantilla: str) -> tuple[str, str]:
    """Copy fija por si no hay ANTHROPIC_API_KEY o el modelo falla."""
    nombre = (lead.get("nombre") or "").split(" ")[0].title()
    saludo = f"Hola {nombre}" if nombre else "Hola"
    firma = "\n\nSaludos,\nIsrael Castro\ntodoconta.com"

    if plantilla == "seguimiento_1":
        pregunta = (
            "¿Me pasas tu WhatsApp y te mando dos horarios?"
            if not lead.get("telefono")
            else "¿Te late que lo veamos esta semana?"
        )
        cuerpo = (
            f"{saludo},\n\n"
            "Te escribí hace unos días y lo más probable es que se haya perdido "
            "entre todo lo que te llega.\n\n"
            "Te propongo algo corto: 20 minutos, cargas tu e.firma y descargamos "
            "en vivo los CFDI de uno de tus RFCs. Con tus datos, no con una demo "
            f"de juguete.\n\n{pregunta}{firma}"
        )
        return "¿Lo vemos 20 minutos con tus datos?", cuerpo

    if plantilla == "seguimiento_2":
        cuerpo = (
            f"{saludo},\n\n"
            "Te escribí un par de veces y no quiero seguir llenándote la bandeja, "
            "así que este es el último.\n\n"
            "Si más adelante te toca bajar CFDI en volumen, aquí sigo y me "
            "respondes este mismo correo.\n\n"
            f"¿Lo dejamos ahí por ahora?{firma}"
        )
        return "Te dejo de escribir (por ahora)", cuerpo

    if lead.get("fuente") == "abacus":
        cuerpo = (
            f"{saludo},\n\n"
            "Vi que pediste probar Abacus, el asistente fiscal por WhatsApp de "
            "TodoConta, y quería escribirte directo para que no se te quede a "
            "medias.\n\n"
            "Soy Israel, contador y el que construye TodoConta. Si aún no te "
            "llega el acceso o algo no jaló, respóndeme este correo y lo "
            "destrabamos hoy mismo.\n\n"
            f"¿Ya pudiste mandarle tu primera pregunta por WhatsApp?{firma}"
        )
        return "Tu prueba de Abacus — ¿ya quedó?", cuerpo

    origen = (
        "contestaste el diagnóstico en todoconta.com"
        if lead.get("fuente") == "diagnostico"
        else "dejaste tus datos en todoconta.com"
    )
    cuerpo = (
        f"{saludo},\n\n"
        f"Vi que {origen} y quería escribirte directo, sin bots de por medio.\n\n"
        "Soy Israel, contador y el que construye TodoConta. Me gustaría entender "
        "qué te trajo al sitio para decirte con honestidad si TodoConta te sirve "
        "o no (y si no, hacia dónde te conviene ir).\n\n"
        "¿Qué es lo que más tiempo te está comiendo hoy: descargar los CFDI del "
        f"SAT, o lo que viene después (validar, conciliar, reportar)?{firma}"
    )
    return "¿Te ayudo con eso que buscabas en TodoConta?", cuerpo


def _candidatos_primer_contacto(fuentes: list[str], max_edad: int) -> list[tuple[dict, str]]:
    corte = (datetime.now(timezone.utc) - timedelta(days=max_edad)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    leads = crm.sb_get(
        "crm_leads?select=id,email,nombre,telefono,fuente,etapa,created_at,notas"
        f"&etapa=eq.lead&consent_marketing=eq.true&fuente=in.({','.join(fuentes)})"
        f"&created_at=gte.{corte}&order=created_at.asc&limit=20"
    )
    # Candado: cualquier toque previo, respuesta o cierre manual descarta el
    # "primer" correo.
    return [
        (lead, "primer_contacto")
        for lead in leads
        if not _hay_contacto_previo(_eventos_sdr(lead["id"]))
    ]


def _candidatos_seguimiento(
    fuentes: list[str], dias: list[int], ventana: int
) -> list[tuple[dict, str]]:
    """Leads en `mql` a los que hoy les toca el toque 2 o 3."""
    corte = (datetime.now(timezone.utc) - timedelta(days=ventana + max(dias) + 1)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    leads = crm.sb_get(
        "crm_leads?select=id,email,nombre,telefono,fuente,etapa,created_at,notas"
        f"&etapa=eq.mql&consent_marketing=eq.true&fuente=in.({','.join(fuentes)})"
        f"&created_at=gte.{corte}&order=created_at.asc&limit=50"
    )
    ahora = datetime.now(timezone.utc)
    salida: list[tuple[dict, str]] = []
    for lead in leads:
        eventos = _eventos_sdr(lead["id"])
        if _detenido(eventos):
            continue
        toques = _toques_del_sdr(eventos)
        if not toques or len(toques) > len(dias):
            continue  # sin primer toque (etapa movida a mano) o secuencia terminada
        primero = _fecha(toques[0]["created_at"])
        edad = (ahora - primero).days
        if edad > ventana:
            continue  # secuencia vieja: no revive por un redeploy
        if edad < dias[len(toques) - 1]:
            continue  # todavía no le toca
        salida.append((lead, f"seguimiento_{len(toques)}"))
    return salida


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if os.environ.get("OPS_SDR_ENABLED", "0") != "1" and not dry_run:
        print("[sdr] apagado por OPS_SDR_ENABLED — no se hace nada")
        return 0

    max_dia = int(os.environ.get("OPS_SDR_MAX_DIA", "5"))
    max_edad = int(os.environ.get("SDR_MAX_EDAD_DIAS", "14"))
    ventana = int(os.environ.get("SDR_SEGUIMIENTO_VENTANA_DIAS", "30"))
    dias_seguimiento = [
        int(d.strip())
        for d in os.environ.get("SDR_SEGUIMIENTOS_DIAS", "3,7").split(",")
        if d.strip()
    ]
    estado = _estado_hoy()
    if estado["enviados"] >= max_dia:
        print(f"[sdr] límite diario alcanzado ({max_dia}) — hasta mañana")
        return 0

    fuentes = [
        f.strip()
        for f in os.environ.get("SDR_FUENTES", "abacus").split(",")
        if f.strip()
    ]

    # Primero los seguimientos: alguien que ya está en la conversación pesa más
    # que un lead nuevo cuando el cupo del día es corto.
    candidatos = _candidatos_seguimiento(fuentes, dias_seguimiento, ventana)
    candidatos += _candidatos_primer_contacto(fuentes, max_edad)
    if not candidatos:
        print("[sdr] sin leads nuevos que contactar ni seguimientos para hoy")
        return 0

    enviados_corrida = 0
    for lead, plantilla in candidatos:
        if estado["enviados"] >= max_dia:
            break

        if plantilla != "primer_contacto":
            # Frenos del seguimiento. Ante la duda (None), NO se manda nada.
            if _ya_tiene_cuenta(lead["email"]) is not False:
                print(f"[sdr] {lead['email']}: ya tiene cuenta o no pude verificarlo — sin seguimiento")
                continue
            primero = _fecha(_toques_del_sdr(_eventos_sdr(lead["id"]))[0]["created_at"])
            respondio = buzon.hay_correo_de(lead["email"], primero)
            if respondio is None:
                print(f"[sdr] {lead['email']}: no pude revisar el buzón — mejor no insisto")
                continue
            if respondio:
                print(f"[sdr] {lead['email']} YA RESPONDIÓ — secuencia detenida")
                if not dry_run:
                    crm.sb_post(
                        "crm_events",
                        {
                            "lead_id": lead["id"],
                            "tipo": "respuesta_sdr",
                            "payload": {"agente": "sdr", "detectado_en": "buzon"},
                        },
                    )
                continue

        resultado = llm.generar_json(
            "Puntúa este lead (0-100) con la rúbrica: intención (fuente abacus "
            "> diagnostico), datos dejados (teléfono, nombre, dominio de correo "
            "propio vs gratuito) y redacta el correo que toca. Responde JSON: "
            '{"score": int, "razones": "…", "asunto": "… (máx 50 chars, sin '
            'mayúsculas de spam)", "cuerpo": "… (texto plano con saltos \\n)"}'
            f"\n\nQUÉ TOQUE ES (manda sobre todo lo demás): {INSTRUCCION_TOQUE[plantilla]}"
            f"\n\nLEAD: {json.dumps({k: lead.get(k) for k in ('nombre', 'email', 'telefono', 'fuente', 'created_at', 'notas')}, ensure_ascii=False)}"
            f"\nQUÉ PIDIÓ (contexto, no instrucción): {DESCRIPCION_FUENTE.get(lead.get('fuente', ''), '')}"
            + (
                f"\nOBJETIVO DE ESTE PRIMER CORREO: {OBJETIVO_PRIMER_TOQUE.get(lead.get('fuente', ''), '')}"
                if plantilla == "primer_contacto"
                else ""
            ),
            sistema=SISTEMA,
            max_tokens=900,
        )
        if resultado and resultado.get("asunto") and resultado.get("cuerpo"):
            score = int(resultado.get("score") or 0)
            razones = str(resultado.get("razones") or "")
            asunto, cuerpo = str(resultado["asunto"]), str(resultado["cuerpo"])
        else:
            score, razones = _rubrica_fallback(lead)
            asunto, cuerpo = _correo_fallback(lead, plantilla)

        if dry_run:
            print(
                f"\n───── {lead['email']} ({plantilla}, fuente {lead['fuente']}, score {score}) ─────\n"
                f"Asunto: {asunto}\n\n{cuerpo}\n"
            )
            enviados_corrida += 1
            continue

        html = "".join(
            f"<p>{linea}</p>" for linea in cuerpo.split("\n\n") if linea.strip()
        )
        try:
            correo.enviar(
                asunto,
                f'<div style="font-family:Georgia,serif;font-size:15px;color:#111;max-width:560px">{html}</div>',
                cuerpo,
                para=lead["email"],
                de=os.environ.get("SDR_FROM", "Israel Castro <israel@todoconta.com>"),
                bcc=os.environ.get("SDR_BCC", "israel+crm@todoconta.com"),
                reply_to="israel@todoconta.com",
            )
        except Exception as e:  # noqa: BLE001
            print(f"[sdr] SES falló con {lead['email']}: {e} — se intentará en la próxima corrida")
            continue

        notas = (lead.get("notas") or "").strip()
        if plantilla == "primer_contacto":
            # Etapa → mql (el filtro etapa=eq.lead evita pisar avances paralelos).
            nota = f"[sdr {estado['fecha']}] score {score}: {razones}"
            crm.sb_patch(
                f"crm_leads?id=eq.{lead['id']}&etapa=eq.lead",
                {
                    "etapa": "mql",
                    "score": score,
                    "notas": f"{notas}\n{nota}".strip(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
        else:
            nota = f"[sdr {estado['fecha']}] {plantilla}: {asunto}"
            crm.sb_patch(
                f"crm_leads?id=eq.{lead['id']}",
                {
                    "notas": f"{notas}\n{nota}".strip(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )

        crm.sb_post(
            "crm_events",
            {
                "lead_id": lead["id"],
                "tipo": "email_enviado",
                "payload": {
                    "agente": "sdr",
                    "template": plantilla,
                    "asunto": asunto,
                    # El cuerpo COMPLETO: es el único registro de lo que se le
                    # prometió a esta persona (el BCC vive en otro buzón).
                    "cuerpo": cuerpo,
                    "score": score,
                },
            },
        )
        estado["enviados"] += 1
        enviados_corrida += 1
        print(f"[sdr] {plantilla} → {lead['email']} (score {score})")

    if not dry_run:
        try:
            ESTADO.write_text(json.dumps(estado))
        except Exception as e:  # noqa: BLE001
            print(f"[sdr] estado no guardado: {e}")
    print(f"[sdr] corrida terminada — {enviados_corrida} correo(s), {estado['enviados']}/{max_dia} hoy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""SDR inbound: primer contacto (y SOLO el primero) a leads que llenaron un
formulario de la landing.

Cada hora lee `crm_leads` con etapa=lead, consent_marketing=true y fuente en
SDR_FUENTES (opt-in estricto: gente que PIDIÓ algo — nunca suscriptores del
newsletter ni importados). Fuentes activas hoy: SOLO `abacus` (decisión
2026-07-17: `qualifier` se descartó — era la campaña de saldo a favor para
personas físicas, pausada y sin relación con el producto; si se retoma será
en sicastro.com). Cuando exista la página /diagnostico se agrega su fuente
aquí vía env, sin tocar código.

REGLA DE ORO del primer toque: responder a la intención REAL del lead, no
crearle una. El lead de `abacus` pidió probar el asistente por WhatsApp
(que ahora es parte de TodoConta, plan Anual con IA): el correo lo ayuda a
ACTIVAR su prueba — no le vende la app de entrada.

Por cada lead:

  1. Lo puntúa con Claude (rúbrica) y redacta un primer correo personal.
  2. Lo manda por SES como Israel (Reply-To israel@todoconta.com) con BCC a
     Israel para que vea todo lo que sale.
  3. Avanza la etapa a `mql`, guarda score/notas y registra el evento
     `email_enviado` — ese evento es el candado: jamás se contacta dos veces.

Israel cierra (responde, demo, WhatsApp). Este agente NO hace follow-ups.

Límites: OPS_SDR_MAX_DIA correos por día (default 5), leads con antigüedad
máxima SDR_MAX_EDAD_DIAS (default 14 — un lead viejo ya no es "speed to lead").

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

from lib import correo, crm, llm

ESTADO = Path("/data/sdr_estado.json")

DESCRIPCION_FUENTE = {
    "abacus": (
        "pidió probar Abacus, el asistente fiscal por WhatsApp que forma parte "
        "de TodoConta — su intención es probar el asistente; el objetivo del "
        "correo es ayudarle a ACTIVAR su prueba de WhatsApp (y quedar a la "
        "mano), NO venderle la app de escritorio de entrada"
    ),
    "diagnostico": (
        "contestó el diagnóstico en todoconta.com/diagnostico y PIDIÓ su plan "
        "personalizado (se le prometió: 'te lo mando mañana — qué automatizar "
        "primero y cuánto tiempo recuperas'). Sus respuestas vienen en `notas` "
        "(rol, RFCs, dolor, volumen, veredicto, tema del post que lo trajo). "
        "Este correo ES esa entrega: un mini-plan concreto para SU caso (por "
        "dónde empezar y qué gana), no un saludo genérico — puede extenderse "
        "hasta ~220 palabras"
    ),
}

SISTEMA = (
    "Eres el asistente comercial de Israel Castro, contador y creador de "
    "TodoConta (todoconta.com): app de escritorio que automatiza la descarga "
    "masiva de CFDI y documentos del SAT para contadores en México (prueba "
    "gratis 15 días; plan Anual $2,990 MXN; Anual con IA $4,990 MXN, que "
    "incluye a Abacus, el asistente fiscal por WhatsApp — Abacus es un feature "
    "del paquete TodoConta, no un producto aparte). Redactas el PRIMER correo "
    "a una persona que acaba de llenar un formulario en el sitio. La regla de "
    "oro: responde a la intención REAL de lo que la persona pidió (viene en el "
    "contexto de la fuente) — no le vendas otra cosa. Reglas de forma: español "
    "de México, tono personal de Israel (directo, servicial, cero plantilla "
    "corporativa), máximo 120 palabras, UNA sola pregunta concreta al final "
    "que invite a responder, sin listas de features, sin presión de venta, sin "
    "enlaces salvo que el contexto lo pida. Nunca digas «CIEC» (di «Contraseña "
    "del SAT»). Nunca inventes datos del lead."
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


def _correo_fallback(lead: dict) -> tuple[str, str]:
    nombre = (lead.get("nombre") or "").split(" ")[0]
    saludo = f"Hola {nombre}" if nombre else "Hola"
    if lead.get("fuente") == "abacus":
        cuerpo = (
            f"{saludo},\n\n"
            "Vi que pediste probar Abacus, el asistente fiscal por WhatsApp de "
            "TodoConta, y quería escribirte directo para que no se te quede a "
            "medias.\n\n"
            "Soy Israel, contador y el que construye TodoConta. Si aún no te "
            "llega el acceso o algo no jaló, respóndeme este correo y lo "
            "destrabamos hoy mismo.\n\n"
            "¿Ya pudiste mandarle tu primera pregunta por WhatsApp?\n\n"
            "Saludos,\nIsrael Castro\ntodoconta.com"
        )
        return "Tu prueba de Abacus — ¿ya quedó?", cuerpo
    contexto = DESCRIPCION_FUENTE.get(lead.get("fuente", ""), "dejaste tus datos en todoconta.com")
    cuerpo = (
        f"{saludo},\n\n"
        f"Vi que {contexto} y quería escribirte directo, sin bots de por medio.\n\n"
        "Soy Israel, contador y el que construye TodoConta. Me gustaría entender "
        "qué te trajo al sitio para decirte con honestidad si TodoConta te sirve "
        "o no (y si no, hacia dónde te conviene ir).\n\n"
        "¿Qué es lo que más tiempo te está comiendo hoy: descargar los CFDI del "
        "SAT, o lo que viene después (validar, conciliar, reportar)?\n\n"
        "Saludos,\nIsrael Castro\ntodoconta.com"
    )
    return "¿Te ayudo con eso que buscabas en TodoConta?", cuerpo


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if os.environ.get("OPS_SDR_ENABLED", "0") != "1" and not dry_run:
        print("[sdr] apagado por OPS_SDR_ENABLED — no se hace nada")
        return 0

    max_dia = int(os.environ.get("OPS_SDR_MAX_DIA", "5"))
    max_edad = int(os.environ.get("SDR_MAX_EDAD_DIAS", "14"))
    estado = _estado_hoy()
    if estado["enviados"] >= max_dia:
        print(f"[sdr] límite diario alcanzado ({max_dia}) — hasta mañana")
        return 0

    # Fuentes habilitadas (coma-separadas). Solo abacus por ahora; /diagnostico
    # se sumará por env cuando exista. qualifier queda fuera a propósito.
    fuentes = [
        f.strip()
        for f in os.environ.get("SDR_FUENTES", "abacus").split(",")
        if f.strip()
    ]
    corte = (datetime.now(timezone.utc) - timedelta(days=max_edad)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )
    leads = crm.sb_get(
        "crm_leads?select=id,email,nombre,telefono,fuente,etapa,created_at,notas"
        f"&etapa=eq.lead&consent_marketing=eq.true&fuente=in.({','.join(fuentes)})"
        f"&created_at=gte.{corte}&order=created_at.asc&limit=20"
    )
    if not leads:
        print("[sdr] sin leads nuevos que contactar")
        return 0

    enviados_corrida = 0
    for lead in leads:
        if estado["enviados"] >= max_dia:
            break
        # Candado anti-duplicado: cualquier contacto previo del SDR descarta.
        previos = crm.sb_get(
            f"crm_events?select=id&lead_id=eq.{lead['id']}"
            "&tipo=in.(email_enviado,respuesta_sdr)&limit=1"
        )
        if previos:
            continue

        resultado = llm.generar_json(
            "Puntúa este lead (0-100) con la rúbrica: intención (fuente abacus "
            "> qualifier), datos dejados (teléfono, nombre, dominio de correo "
            "propio vs gratuito) y redacta su primer correo. Responde JSON: "
            '{"score": int, "razones": "…", "asunto": "… (máx 50 chars, sin '
            'mayúsculas de spam)", "cuerpo": "… (texto plano con saltos \\n)"}'
            f"\n\nLEAD: {json.dumps({k: lead.get(k) for k in ('nombre', 'email', 'telefono', 'fuente', 'created_at', 'notas')}, ensure_ascii=False)}"
            f"\nCONTEXTO DE LA FUENTE: {DESCRIPCION_FUENTE.get(lead.get('fuente', ''), '')}",
            sistema=SISTEMA,
            max_tokens=900,
        )
        if resultado and resultado.get("asunto") and resultado.get("cuerpo"):
            score = int(resultado.get("score") or 0)
            razones = str(resultado.get("razones") or "")
            asunto, cuerpo = str(resultado["asunto"]), str(resultado["cuerpo"])
        else:
            score, razones = _rubrica_fallback(lead)
            asunto, cuerpo = _correo_fallback(lead)

        if dry_run:
            print(
                f"\n───── {lead['email']} (fuente {lead['fuente']}, score {score}) ─────\n"
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
                bcc=os.environ.get("SDR_BCC", "israel.castro@gmail.com"),
                reply_to="israel@todoconta.com",
            )
        except Exception as e:  # noqa: BLE001
            print(f"[sdr] SES falló con {lead['email']}: {e} — se intentará en la próxima corrida")
            continue

        # Etapa → mql (el filtro etapa=eq.lead evita pisar avances paralelos).
        nota = f"[sdr {estado['fecha']}] score {score}: {razones}"
        notas = (lead.get("notas") or "").strip()
        crm.sb_patch(
            f"crm_leads?id=eq.{lead['id']}&etapa=eq.lead",
            {
                "etapa": "mql",
                "score": score,
                "notas": f"{notas}\n{nota}".strip(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        crm.sb_post(
            "crm_events",
            {
                "lead_id": lead["id"],
                "tipo": "email_enviado",
                "payload": {"agente": "sdr", "template": "primer_contacto", "asunto": asunto, "score": score},
            },
        )
        estado["enviados"] += 1
        enviados_corrida += 1
        print(f"[sdr] contactado {lead['email']} (score {score})")

    if not dry_run:
        try:
            ESTADO.write_text(json.dumps(estado))
        except Exception as e:  # noqa: BLE001
            print(f"[sdr] estado no guardado: {e}")
    print(f"[sdr] corrida terminada — {enviados_corrida} correo(s), {estado['enviados']}/{max_dia} hoy")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

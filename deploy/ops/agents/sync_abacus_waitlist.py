"""Sync de la waitlist de Abacus (Notion) → `crm_leads`.

**El hueco que cierra.** El flujo real de Abacus es: formulario → Notion → un
script en el workspace de OpenClaw (`abacus/scripts/process_waitlist.py`)
autoriza el número en la allowlist, manda la bienvenida por SES y suscribe a la
lista de Sendy. Ese script NUNCA escribió al CRM: al 2026-07-26 había 114
personas activas en la lista `abacus` de Sendy y CERO leads con `fuente=abacus`
en el CRM. El SDR llevaba semanas esperando leads que no llegaban, y el reporte
semanal reportaba `crm_nuevos_7d_abacus: 0` como si nadie pidiera Abacus.

**Por qué solo esta mitad vive aquí.** La autorización escribe
`/root/.openclaw/openclaw.json` — el archivo de configuración de OpenClaw, que
corre en el host, fuera de Docker. Meter ese archivo en este contenedor
rompería dos reglas del contenedor (no toca /root ni el host) y arriesgaría
corromper la allowlist por escrituras concurrentes con OpenClaw. Así que la
autorización sigue donde está y AQUÍ vive el registro en el CRM, leyendo la
misma fuente de verdad (la base de Notion). Los dos son idempotentes y ninguno
depende del otro.

Qué hace por cada página de la waitlist con correo:

  - upsert en `crm_leads` por email con `fuente=abacus`, nombre y teléfono;
  - **teléfono en E.164 canónico** (`+52` + 10 dígitos). OpenClaw guarda
    `+521…` porque su allowlist de WhatsApp lo necesita así; el CRM guarda la
    forma canónica para que el número sirva igual desde cualquier canal y
    coincida con lo que captura el formulario del diagnóstico;
  - `etapa` según el Estado de Notion, **sin nunca retroceder** (un lead que ya
    es `cliente` en el CRM no vuelve a `lead` porque Notion tarde en moverse);
  - `created_at` = fecha de creación de la página en Notion, para que el SDR
    respete su ventana de 14 días y no trate como nuevo a alguien de marzo.

Uso:
    python agents/sync_abacus_waitlist.py            # corre (si está encendido)
    python agents/sync_abacus_waitlist.py --dry-run  # imprime, no escribe

Kill switch: OPS_WAITLIST_ENABLED != "1" → no hace nada (default APAGADO).
Requiere: NOTION_API_KEY (+ NOTION_ABACUS_DB_ID si cambia la base) y las envs
de Supabase que ya usa lib/crm.py.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote

from lib import crm, notion

DB_ID_DEFAULT = "3293c008-312e-8169-bc00-f3001910e3aa"

# Estado de Notion → etapa del CRM. Lo que Notion no sabe, no lo pisa.
ETAPA_POR_ESTADO = {
    "": "lead",
    "Lista de espera": "lead",
    "Trial activo": "trial",
    "Trial vencido": "perdido",
    "Suscripción activa": "cliente",
    "Cliente": "cliente",
    "Suscripción cancelada": "perdido",
}
# Orden de avance (perdido queda fuera: es información terminal que Notion sí
# conoce mejor que el CRM, así que esa sí se aplica siempre).
AVANCE = ["lead", "mql", "trial", "activado", "cliente"]

TITULOS = r"^(c\.?p\.?|l\.?c\.?|l\.?d\.?|l\.?c\.?p\.?|mtr\.?|dr\.?|dra\.?|ing\.?|lic\.?)\s+"


def primer_nombre(completo: str) -> str:
    """"C.P. Juan Pérez" → "Juan" (mismo criterio que el script de OpenClaw)."""
    if not completo:
        return ""
    limpio = re.sub(TITULOS, "", completo.strip(), flags=re.IGNORECASE).strip()
    partes = limpio.split()
    return partes[0].capitalize() if partes else ""


def telefono_e164(crudo: str) -> str | None:
    """E.164 canónico de México: +52 + 10 dígitos.

    OpenClaw normaliza a `+521…` (la convención vieja que su allowlist de
    WhatsApp todavía usa). Aquí se guarda SIN ese 1: es la forma canónica y la
    misma que produce el formulario del diagnóstico, así que un mismo teléfono
    no queda escrito de dos maneras según por dónde entró la persona.
    """
    digitos = re.sub(r"\D", "", crudo or "")
    if not digitos:
        return None
    if digitos.startswith("52"):
        digitos = digitos[2:]
    if len(digitos) == 11 and digitos.startswith("1"):
        digitos = digitos[1:]
    return f"+52{digitos}" if len(digitos) == 10 else None


def _etapa_final(actual: str | None, nueva: str) -> str | None:
    """Etapa a escribir, o None si no hay que tocarla."""
    if actual == nueva:
        return None
    if not actual:
        return nueva
    if nueva == "perdido":
        return nueva
    if actual == "perdido":
        return None  # ya se dio por perdido: que lo revise un humano
    try:
        return nueva if AVANCE.index(nueva) > AVANCE.index(actual) else None
    except ValueError:
        return None


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if os.environ.get("OPS_WAITLIST_ENABLED", "0") != "1" and not dry_run:
        print("[waitlist] apagado por OPS_WAITLIST_ENABLED — no se hace nada")
        return 0
    if not os.environ.get("NOTION_API_KEY"):
        print("[waitlist] falta NOTION_API_KEY")
        return 1

    db_id = os.environ.get("NOTION_ABACUS_DB_ID", DB_ID_DEFAULT)
    try:
        paginas = notion.consultar_bd(db_id)
    except Exception as e:  # noqa: BLE001
        print(f"[waitlist] Notion no respondió: {e}")
        return 1

    ahora = datetime.now(timezone.utc).isoformat()
    nuevos = actualizados = sin_correo = iguales = 0

    for pagina in paginas:
        email = notion.propiedad(pagina, "Email").lower().strip()
        if not email or "@" not in email:
            sin_correo += 1
            continue

        estado = notion.propiedad(pagina, "Estado")
        etapa_notion = ETAPA_POR_ESTADO.get(estado, "lead")
        nombre = notion.propiedad(pagina, "Primer Nombre") or primer_nombre(
            notion.propiedad(pagina, "Nombre")
        )
        telefono = telefono_e164(notion.propiedad(pagina, "WhatsApp"))
        creado = pagina.get("created_time") or ahora

        try:
            existentes = crm.sb_get(
                f"crm_leads?email=eq.{quote(email)}&select=id,nombre,telefono,etapa,notas,created_at"
            )
        except Exception as e:  # noqa: BLE001
            print(f"[waitlist] Supabase falló con {email}: {e}")
            continue

        if not existentes:
            fila = {
                "email": email,
                "nombre": nombre or None,
                "telefono": telefono,
                "fuente": "abacus",
                "etapa": etapa_notion,
                "consent_marketing": True,
                "consent_at": creado,
                "created_at": creado,
                "updated_at": ahora,
                "notas": f"[waitlist abacus] Estado en Notion: {estado or 'sin estado'}",
            }
            print(f"  + {email:38s} {nombre or '(sin nombre)':12s} {telefono or '(sin tel)':14s} etapa={etapa_notion}")
            nuevos += 1
            if not dry_run:
                try:
                    crm.sb_post("crm_leads", fila)
                except Exception as e:  # noqa: BLE001
                    print(f"    ⚠️  no se pudo crear: {e}")
            continue

        lead = existentes[0]
        cambios: dict = {}
        # Solo se COMPLETA lo que falta; nunca se pisa dato bueno del CRM.
        if nombre and not (lead.get("nombre") or "").strip():
            cambios["nombre"] = nombre
        if telefono and not (lead.get("telefono") or "").strip():
            cambios["telefono"] = telefono
        # Notion tiene la fecha REAL en que la persona levantó la mano. Si el CRM
        # trae una posterior, es que la inventó otra vía (p. ej. la fecha en que
        # el script la empujó a Sendy) y hace pasar por nuevo a un lead viejo:
        # eso mete a gente al SDR con el copy equivocado. Manda Notion.
        if (lead.get("created_at") or "") > creado:
            cambios["created_at"] = creado
        etapa = _etapa_final(lead.get("etapa"), etapa_notion)
        if etapa:
            cambios["etapa"] = etapa
        if not cambios:
            iguales += 1
            continue

        cambios["updated_at"] = ahora
        print(f"  ~ {email:38s} {cambios}")
        actualizados += 1
        if not dry_run:
            try:
                crm.sb_patch(f"crm_leads?id=eq.{lead['id']}", cambios)
            except Exception as e:  # noqa: BLE001
                print(f"    ⚠️  no se pudo actualizar: {e}")

    print(
        f"[waitlist] {'(dry-run) ' if dry_run else ''}{len(paginas)} páginas · "
        f"{nuevos} nuevos · {actualizados} completados · {iguales} sin cambios · "
        f"{sin_correo} sin correo"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

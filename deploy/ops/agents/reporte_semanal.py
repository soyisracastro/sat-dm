"""Reporte semanal de métricas del ecosistema de ventas → correo a Israel.

Junta números de Supabase (usuarios/planes/CRM), Stripe (suscripciones/ARR) y
Sendy (listas de email), calcula deltas contra el snapshot de la semana pasada
(/data/ultimo_reporte.json), pide una narrativa breve a Claude y manda todo por
SES. Cada fuente se degrada sola: el reporte SIEMPRE sale.

Uso:
    python agents/reporte_semanal.py            # manda el correo
    python agents/reporte_semanal.py --dry-run  # imprime a stdout, no manda

Kill switch: OPS_REPORTE_ENABLED != "1" → no hace nada.
"""

from __future__ import annotations

import html
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from lib import correo, fuentes, llm

SNAPSHOT = Path("/data/ultimo_reporte.json")


def _deltas(actual: dict, previo: dict, prefijo: str = "") -> dict[str, str]:
    """Delta legible por métrica numérica compartida entre snapshots."""
    out: dict[str, str] = {}
    for k, v in actual.items():
        ruta = f"{prefijo}{k}"
        if isinstance(v, dict):
            out.update(_deltas(v, previo.get(k, {}) if isinstance(previo, dict) else {}, f"{ruta}."))
        elif isinstance(v, (int, float)) and isinstance(previo, dict):
            ant = previo.get(k)
            if isinstance(ant, (int, float)):
                d = v - ant
                out[ruta] = f"{'+' if d >= 0 else ''}{d:g}"
    return out


def _tabla_html(datos: dict, deltas: dict[str, str], prefijo: str = "") -> str:
    filas = []
    for k, v in datos.items():
        ruta = f"{prefijo}{k}"
        if isinstance(v, dict):
            filas.append(
                f'<tr><td colspan="3" style="padding:10px 8px 4px;font-weight:700">{html.escape(k)}</td></tr>'
            )
            filas.append(_tabla_html(v, deltas, f"{ruta}."))
        else:
            delta = deltas.get(ruta, "")
            filas.append(
                f'<tr><td style="padding:3px 8px;color:#52514e">{html.escape(str(k))}</td>'
                f'<td style="padding:3px 8px;text-align:right;font-variant-numeric:tabular-nums">{html.escape(str(v))}</td>'
                f'<td style="padding:3px 8px;text-align:right;color:#898781">{html.escape(delta)}</td></tr>'
            )
    return "".join(filas)


def main() -> int:
    dry_run = "--dry-run" in sys.argv
    if os.environ.get("OPS_REPORTE_ENABLED", "1") != "1" and not dry_run:
        print("[reporte] apagado por OPS_REPORTE_ENABLED — no se hace nada")
        return 0

    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    datos = {
        "supabase": fuentes.metricas_supabase(),
        "stripe": fuentes.metricas_stripe(),
        "sendy": fuentes.metricas_sendy(),
    }

    previo: dict = {}
    if SNAPSHOT.exists():
        try:
            previo = json.loads(SNAPSHOT.read_text()).get("datos", {})
        except Exception:  # noqa: BLE001
            pass
    deltas = _deltas(datos, previo)

    narrativa = llm.narrar(
        "Eres el analista de métricas de TodoConta (app de descarga masiva del SAT "
        "para contadores en México; oferta: plan anual $2,990 y anual con IA $4,990 MXN). "
        "Con el siguiente JSON de métricas de la semana (y deltas vs la semana pasada), "
        "escribe en español: (1) un resumen ejecutivo de 3-4 oraciones, (2) la señal más "
        "importante de la semana, y (3) tres acciones concretas sugeridas para la próxima "
        "semana. Sé directo, sin relleno, sin inventar números que no estén en el JSON.\n\n"
        f"MÉTRICAS: {json.dumps(datos, ensure_ascii=False)}\n\n"
        f"DELTAS 7d: {json.dumps(deltas, ensure_ascii=False)}"
    )

    texto = (
        f"Reporte semanal TodoConta — {hoy}\n\n"
        + (narrativa + "\n\n" if narrativa else "")
        + json.dumps(datos, indent=2, ensure_ascii=False)
    )
    narrativa_html = (
        f'<div style="white-space:pre-wrap;margin:0 0 18px">{html.escape(narrativa)}</div>'
        if narrativa
        else ""
    )
    cuerpo_html = f"""
    <div style="font-family:system-ui,-apple-system,'Segoe UI',sans-serif;max-width:640px;margin:0 auto;color:#0b0b0b">
      <h2 style="letter-spacing:-0.02em">Reporte semanal — {hoy}</h2>
      {narrativa_html}
      <table style="border-collapse:collapse;width:100%;font-size:14px">
        <tr><th align="left" style="padding:3px 8px;color:#898781;font-weight:600">Métrica</th>
            <th align="right" style="padding:3px 8px;color:#898781;font-weight:600">Valor</th>
            <th align="right" style="padding:3px 8px;color:#898781;font-weight:600">Δ 7d</th></tr>
        {_tabla_html(datos, deltas)}
      </table>
      <p style="color:#898781;font-size:12px;margin-top:18px">
        Generado por el agente de operaciones (deploy/ops) en el VPS.
      </p>
    </div>
    """

    if dry_run:
        print(texto)
        return 0

    correo.enviar(f"📊 TodoConta — reporte semanal {hoy}", cuerpo_html, texto)
    try:
        SNAPSHOT.write_text(
            json.dumps({"fecha": hoy, "datos": datos}, ensure_ascii=False)
        )
    except Exception as e:  # noqa: BLE001
        print(f"[reporte] snapshot no guardado: {e}")
    print(f"[reporte] enviado ({hoy})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

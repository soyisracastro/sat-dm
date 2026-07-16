"""Fuentes de datos del reporte semanal (Supabase, Stripe, Sendy).

Cada función devuelve un dict con números o, si algo falla, una clave
"error" — el reporte SIEMPRE sale, aunque una fuente esté caída.
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from typing import Any

import requests

TIMEOUT = 15


def _hace_dias(dias: int) -> str:
    # Formato Z (sin "+00:00"): el "+" sin encodear se interpreta como espacio
    # en el query string de PostgREST y el filtro revienta con 400.
    return (datetime.now(timezone.utc) - timedelta(days=dias)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# ---------------------------------------------------------------------------
# Supabase (REST, service role) — usuarios, planes, CRM
# ---------------------------------------------------------------------------


def _supabase_count(path: str) -> int:
    """HEAD con Prefer: count=exact → total de filas que matchean el filtro."""
    base = os.environ["TODOCONTA_SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    resp = requests.head(
        f"{base}/rest/v1/{path}",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "count=exact",
            "Range": "0-0",
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    # content-range: "0-0/154" o "*/154"
    return int(resp.headers.get("content-range", "/0").split("/")[-1])


def metricas_supabase() -> dict[str, Any]:
    try:
        semana = _hace_dias(7)
        datos: dict[str, Any] = {
            "usuarios_total": _supabase_count("profiles?select=id"),
            "fundadores": _supabase_count("profiles?select=id&is_founder=eq.true"),
            "premium_activos": _supabase_count(
                "profiles?select=id&subscription_tier=eq.premium&subscription_status=eq.active"
            ),
            "plan_ia": _supabase_count(
                "profiles?select=id&subscription_plan=eq.desktop_ia"
            ),
            "trials_nuevos_7d": _supabase_count(
                f"profiles?select=id&desktop_trial_started_at=gte.{semana}"
            ),
        }
        # CRM (migración 034) — puede no existir todavía; se degrada solo.
        try:
            datos["crm_leads_total"] = _supabase_count("crm_leads?select=id")
            datos["crm_leads_nuevos_7d"] = _supabase_count(
                f"crm_leads?select=id&created_at=gte.{semana}"
            )
            for fuente in ("qualifier", "abacus", "newsletter", "registro_app"):
                datos[f"crm_nuevos_7d_{fuente}"] = _supabase_count(
                    f"crm_leads?select=id&created_at=gte.{semana}&fuente=eq.{fuente}"
                )
            datos["crm_activados_7d"] = _supabase_count(
                f"crm_events?select=id&tipo=eq.primera_descarga&created_at=gte.{semana}"
            )
            datos["crm_pagos_7d"] = _supabase_count(
                f"crm_events?select=id&tipo=eq.pago&created_at=gte.{semana}"
            )
        except Exception as e:  # noqa: BLE001
            datos["crm_error"] = f"CRM no disponible aún: {e}"
        return datos
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Stripe (restricted key de SOLO LECTURA)
# ---------------------------------------------------------------------------


def metricas_stripe() -> dict[str, Any]:
    key = os.environ.get("STRIPE_RESTRICTED_KEY")
    if not key:
        return {"skip": "sin STRIPE_RESTRICTED_KEY"}
    try:
        subs: list[dict] = []
        params = {"status": "active", "limit": "100"}
        while True:
            resp = requests.get(
                "https://api.stripe.com/v1/subscriptions",
                params=params,
                auth=(key, ""),
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            payload = resp.json()
            subs.extend(payload.get("data", []))
            if not payload.get("has_more") or not subs:
                break
            params["starting_after"] = subs[-1]["id"]

        arr_centavos = 0
        nuevas_7d = 0
        corte = datetime.now(timezone.utc) - timedelta(days=7)
        for s in subs:
            item = (s.get("items", {}).get("data") or [{}])[0]
            price = item.get("price") or {}
            monto = price.get("unit_amount") or 0
            intervalo = (price.get("recurring") or {}).get("interval")
            if intervalo == "year":
                arr_centavos += monto
            elif intervalo == "month":
                arr_centavos += monto * 12
            if datetime.fromtimestamp(s.get("created", 0), tz=timezone.utc) > corte:
                nuevas_7d += 1

        return {
            "suscripciones_activas": len(subs),
            "arr_mxn": round(arr_centavos / 100),
            "mrr_mxn": round(arr_centavos / 100 / 12),
            "altas_7d": nuevas_7d,
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Sendy (MariaDB, usuario read-only)
# ---------------------------------------------------------------------------

LISTAS_CLAVE = [
    "columna-13",
    "substack",
    "Usuarios App",
    "abacus",
    "Founders",
    "todoconta_proyecto",
    "cfdi",
]


def metricas_sendy() -> dict[str, Any]:
    host = os.environ.get("SENDY_DB_HOST")
    if not host:
        return {"skip": "sin SENDY_DB_HOST"}
    try:
        import pymysql

        conn = pymysql.connect(
            host=host,
            user=os.environ["SENDY_DB_USER"],
            password=os.environ["SENDY_DB_PASSWORD"],
            database=os.environ.get("SENDY_DB_NAME", "sendy"),
            connect_timeout=10,
            read_timeout=20,
        )
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT l.name,
                           COUNT(s.id) AS subs,
                           SUM(CASE WHEN s.unsubscribed=0 AND s.bounced=0
                                     AND s.complaint=0 AND s.confirmed=1
                                    THEN 1 ELSE 0 END) AS activos
                    FROM lists l LEFT JOIN subscribers s ON s.list = l.id
                    GROUP BY l.id, l.name
                    """
                )
                filas = cur.fetchall()
        finally:
            conn.close()

        listas = {nombre: int(activos or 0) for nombre, _subs, activos in filas}
        total_activos = sum(listas.values())
        return {
            "total_activos_todas_listas": total_activos,
            "listas": {n: listas.get(n, 0) for n in LISTAS_CLAVE},
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

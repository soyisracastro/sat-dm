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

# Listas que Israel quiere ver SIEMPRE, existan o no movimientos esa semana.
# Van por NOMBRE, no por id: el desglose agrupa por nombre. Verificado que no
# hay nombres duplicados en la instalación; si algún día se repite uno, el dict
# se pisaría y una de las dos desaparecería del reporte sin avisar.
LISTAS_CLAVE = [
    "Newsletter Blog (contadores)",  # lead magnet del blog (la más grande)
    "substack",
    "Usuarios App",
    "abacus",
    "Founders",
    "todoconta_proyecto",
    "cfdi",
    "clients-airtable",
    "Recursos gratis - Casos prácticos IA",  # imán de los 3 flujos híbridos
    # soycontador.ai (brand 5). Nacen en cero y ESO es justo lo que hay que
    # mirar: son listas nuevas y el reporte es donde se ve si arrancan o no.
    "soycontador.ai - Newsletter",
    "soycontador.ai - Ebook IA para contadores",
    "soycontador.ai - Jueves de ContadorIA",
]

# Además de las clave, las N listas más grandes: así el desglose no se queda
# ciego cuando nace una lista nueva y nadie actualiza LISTAS_CLAVE.
TOP_LISTAS = 10


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

                # Salud de los autoresponders. No basta con "hace N días que no
                # manda": si nadie se suscribió, no mandar es lo correcto. Lo que
                # delata una falla es que HAYA confirmaciones y NO haya envíos,
                # así que traemos las dos mitades y que el análisis las compare.
                # Contexto: en julio 2026 el sidecar corría scheduled.php pero no
                # autoresponders.php y dos semanas de bienvenidas no salieron —
                # nadie se enteró porque nada lo miraba. Esto es ese vigilante.
                cur.execute("SELECT MAX(sent), COUNT(*) FROM ares_deliveries")
                ultimo_envio, total_envios = cur.fetchone()

                cur.execute(
                    """
                    SELECT COUNT(*) FROM ares_deliveries
                    WHERE sent >= UNIX_TIMESTAMP() - 7*86400
                    """
                )
                envios_7d = cur.fetchone()[0]

                # Confirmaciones de la semana SOLO en listas que tienen un
                # autoresponder inmediato encendido: son las que debieron
                # disparar un envío. join_date se estampa al confirmar.
                cur.execute(
                    """
                    SELECT COUNT(*) FROM subscribers s
                    WHERE s.confirmed = 1
                      AND s.join_date >= UNIX_TIMESTAMP() - 7*86400
                      AND s.list IN (
                          SELECT a.list FROM ares a
                          JOIN ares_emails e ON e.ares_id = a.id
                          WHERE e.enabled = 1 AND e.time_condition = 'immediately'
                      )
                    """
                )
                confirmados_7d = cur.fetchone()[0]
        finally:
            conn.close()

        listas = {nombre: int(activos or 0) for nombre, _subs, activos in filas}
        total_activos = sum(listas.values())

        # Clave que SIGUEN existiendo + las más grandes, ordenadas por tamaño.
        # Una lista clave borrada en Sendy se OMITE (no se reporta como 0): si la
        # dejamos en 0 el delta la lee como caída masiva y dispara una falsa
        # alarma — pasó con "columna-13" (−2,960) el 2026-07-20.
        top = sorted(listas, key=lambda n: listas[n], reverse=True)[:TOP_LISTAS]
        mostrar = [n for n in LISTAS_CLAVE if n in listas]
        mostrar += [n for n in top if n not in mostrar and listas[n] > 0]
        ausentes = [n for n in LISTAS_CLAVE if n not in listas]

        salida: dict[str, Any] = {
            "total_activos_todas_listas": total_activos,
            "listas": {
                n: listas[n] for n in sorted(mostrar, key=lambda n: listas[n], reverse=True)
            },
        }
        if ausentes:
            salida["listas_clave_ausentes"] = ", ".join(ausentes)

        ahora = datetime.now(timezone.utc).timestamp()
        dias_sin_enviar = (
            round((ahora - float(ultimo_envio)) / 86400, 1) if ultimo_envio else None
        )
        salida["autoresponders"] = {
            "ultimo_envio": (
                datetime.fromtimestamp(float(ultimo_envio), tz=timezone.utc).strftime(
                    "%Y-%m-%d %H:%M UTC"
                )
                if ultimo_envio
                else "nunca"
            ),
            "dias_sin_enviar": dias_sin_enviar,
            "envios_7d": int(envios_7d or 0),
            "confirmados_7d_en_listas_con_autoresponder": int(confirmados_7d or 0),
            # La bandera es la comparación, no el tiempo: gente que confirmó y
            # ningún envío significa que el cron de autoresponders no corrió.
            "posible_falla": bool(confirmados_7d and not envios_7d),
            "total_historico": int(total_envios or 0),
        }
        return salida
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}

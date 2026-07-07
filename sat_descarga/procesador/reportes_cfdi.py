"""
Reportes agregados sobre la tabla `cfdis` del procesador.

Aprovecha SQL (SUM/COUNT/GROUP BY) en lugar de iterar listas en Python — un
orden de magnitud más rápido para corpus de miles de CFDIs.

Reportes incluidos:
- `stats_generales`: 3 cards superiores (comprobantes, monto, impuestos).
- `totales_por_mes`: agregado mes×monto/impuestos.
- `top_contrapartes`: top N emisores y receptores por monto.
- `integridad`: CFDIs con warnings.
"""

from __future__ import annotations

from typing import Any, Optional

from .db import CfdiFiltros, ProcesadorDB, _construir_where, _row_to_dict


def stats_generales(db: ProcesadorDB, filtros: Optional[CfdiFiltros] = None) -> dict:
    """KPIs para las stats cards de la UI."""
    where, params = _construir_where(filtros)
    sql = f"""
        SELECT
            COUNT(*) AS total_comprobantes,
            COALESCE(SUM(total), 0) AS monto_total,
            COALESCE(SUM(iva_trasladado), 0) AS iva_trasladado,
            COALESCE(SUM(ieps_trasladado), 0) AS ieps_trasladado,
            COALESCE(SUM(iva_retenido), 0) AS iva_retenido,
            COALESCE(SUM(isr_retenido), 0) AS isr_retenido,
            SUM(CASE WHEN warnings_json != '[]' THEN 1 ELSE 0 END) AS con_errores
        FROM cfdis
        {where}
    """
    with db.cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        # Conteo por tipo (respeta filtros)
        cur.execute(
            f"SELECT tipo, COUNT(*) AS n FROM cfdis {where} GROUP BY tipo",
            params,
        )
        por_tipo = {r["tipo"]: r["n"] for r in cur.fetchall()}
        # Total "global" = todo el buffer de LA EMPRESA sin filtros de UI —
        # útil para que la UI decida si el buffer está realmente vacío
        # (vs un filtro restrictivo que oculta todo).
        where_g, params_g = _construir_where({"mi_rfc": (filtros or {}).get("mi_rfc")})
        cur.execute(f"SELECT COUNT(*) FROM cfdis {where_g}", params_g)
        total_global = cur.fetchone()[0]
    return {
        "total_comprobantes": row["total_comprobantes"] or 0,
        "total_global": total_global,
        "monto_total": float(row["monto_total"] or 0.0),
        "iva_trasladado": float(row["iva_trasladado"] or 0.0),
        "ieps_trasladado": float(row["ieps_trasladado"] or 0.0),
        "iva_retenido": float(row["iva_retenido"] or 0.0),
        "isr_retenido": float(row["isr_retenido"] or 0.0),
        "con_errores": row["con_errores"] or 0,
        "por_tipo": por_tipo,
    }


def totales_por_mes(db: ProcesadorDB, filtros: Optional[CfdiFiltros] = None) -> list[dict]:
    """
    Una fila por mes (formato `YYYY-MM`) con sub_total, iva trasladado/retenido,
    isr retenido y total. Ordenado descendente (mes más reciente primero).
    """
    where, params = _construir_where(filtros)
    sql = f"""
        SELECT
            SUBSTR(fecha, 1, 7) AS mes,
            COUNT(*) AS comprobantes,
            COALESCE(SUM(sub_total), 0) AS sub_total,
            COALESCE(SUM(iva_trasladado), 0) AS iva_trasladado,
            COALESCE(SUM(ieps_trasladado), 0) AS ieps_trasladado,
            COALESCE(SUM(iva_retenido), 0) AS iva_retenido,
            COALESCE(SUM(isr_retenido), 0) AS isr_retenido,
            COALESCE(SUM(total), 0) AS total
        FROM cfdis
        {where}
        GROUP BY mes
        ORDER BY mes DESC
    """
    with db.cursor() as cur:
        cur.execute(sql, params)
        return [
            {
                "mes": r["mes"],
                "comprobantes": r["comprobantes"],
                "sub_total": float(r["sub_total"]),
                "iva_trasladado": float(r["iva_trasladado"]),
                "ieps_trasladado": float(r["ieps_trasladado"]),
                "iva_retenido": float(r["iva_retenido"]),
                "isr_retenido": float(r["isr_retenido"]),
                "total": float(r["total"]),
            }
            for r in cur.fetchall()
        ]


def top_contrapartes(
    db: ProcesadorDB,
    filtros: Optional[CfdiFiltros] = None,
    n: int = 10,
) -> dict[str, list[dict]]:
    """Top N emisores y receptores por monto acumulado."""
    where, params = _construir_where(filtros)

    sql_em = f"""
        SELECT emisor_rfc, MAX(emisor_nombre) AS nombre,
               COUNT(*) AS comprobantes, COALESCE(SUM(total), 0) AS monto
        FROM cfdis
        {where + (' AND ' if where else 'WHERE ')} emisor_rfc != ''
        GROUP BY emisor_rfc
        ORDER BY monto DESC
        LIMIT ?
    """
    sql_re = f"""
        SELECT receptor_rfc, MAX(receptor_nombre) AS nombre,
               COUNT(*) AS comprobantes, COALESCE(SUM(total), 0) AS monto
        FROM cfdis
        {where + (' AND ' if where else 'WHERE ')} receptor_rfc != ''
        GROUP BY receptor_rfc
        ORDER BY monto DESC
        LIMIT ?
    """
    with db.cursor() as cur:
        cur.execute(sql_em, (*params, n))
        emisores = [
            {
                "rfc": r["emisor_rfc"],
                "nombre": r["nombre"] or "",
                "comprobantes": r["comprobantes"],
                "monto": float(r["monto"]),
            }
            for r in cur.fetchall()
        ]
        cur.execute(sql_re, (*params, n))
        receptores = [
            {
                "rfc": r["receptor_rfc"],
                "nombre": r["nombre"] or "",
                "comprobantes": r["comprobantes"],
                "monto": float(r["monto"]),
            }
            for r in cur.fetchall()
        ]
    return {"emisores": emisores, "receptores": receptores}


def integridad(
    db: ProcesadorDB,
    filtros: Optional[CfdiFiltros] = None,
    limit: int = 200,
) -> list[dict]:
    """Lista de CFDIs con warnings (uuid + cabecera + warnings)."""
    where, params = _construir_where(filtros)
    where_extra = (
        "warnings_json != '[]' AND warnings_json IS NOT NULL"
    )
    if where:
        sql_where = f"{where} AND {where_extra}"
    else:
        sql_where = f"WHERE {where_extra}"
    sql = f"""
        SELECT uuid, tipo, fecha, serie, folio,
               emisor_rfc, emisor_nombre, receptor_rfc, receptor_nombre,
               total, warnings_json
        FROM cfdis
        {sql_where}
        ORDER BY fecha DESC
        LIMIT ?
    """
    import json
    with db.cursor() as cur:
        cur.execute(sql, (*params, limit))
        out = []
        for r in cur.fetchall():
            try:
                warnings = json.loads(r["warnings_json"] or "[]")
            except json.JSONDecodeError:
                warnings = []
            out.append(
                {
                    "uuid": r["uuid"],
                    "tipo": r["tipo"],
                    "fecha": r["fecha"],
                    "serie": r["serie"],
                    "folio": r["folio"],
                    "emisor_rfc": r["emisor_rfc"],
                    "emisor_nombre": r["emisor_nombre"],
                    "receptor_rfc": r["receptor_rfc"],
                    "receptor_nombre": r["receptor_nombre"],
                    "total": float(r["total"] or 0.0),
                    "warnings": warnings,
                }
            )
        return out

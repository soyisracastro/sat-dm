"""
Reportes del procesador de Pagos.

Todo SQL puro sobre las tablas `cfdis` + `pagos_relaciones` (migración 004).
Sin iterar listas Python, sin parsear `raw_json` — los reportes son queries
con índices que escalan a miles de complementos sin esfuerzo.

Conceptos:
- **Factura PPD**: CFDI tipo I con `metodo_pago = 'PPD'`.
- **Complemento de pago**: CFDI tipo P. Tiene N `documentos_relacionados`
  (cada uno una fila en `pagos_relaciones`).
- **Status PPD**: derivado de `total - SUM(docto_imp_pagado)` con tolerancia
  de 0.02 (mismo `INTEGRIDAD_TOLERANCE` que validaciones).
- **Extemporáneo**: complemento emitido después del día 5 del mes siguiente
  a su FechaPago.
- **Huérfano**: complemento cuyo `docto_uuid` no está cargado en `cfdis`.
- **Incidencia PUE**: complemento referencia un PPD pero el PPD (o el
  doctoRelacionado) viene con `metodo_pago = 'PUE'` → riesgo fiscal por
  duplicidad ante SAT.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from .catalogos import INTEGRIDAD_TOLERANCE
from .db import ProcesadorDB, normalizar_mi_rfc


# ---------------------------------------------------------------------------
# Filtros (espejo del shape de la UI)
# ---------------------------------------------------------------------------


def _construir_where_ppd(filtros: Optional[dict]) -> tuple[str, list]:
    """Construye WHERE para queries sobre `cfdis` filtradas a facturas PPD."""
    clauses = ["cfdis.tipo = 'I'", "cfdis.metodo_pago = 'PPD'"]
    params: list[Any] = []

    if not filtros:
        return " AND ".join(clauses), params

    # Dueño del buffer (empresa activa) — acota todo el reporte.
    mi_rfc = filtros.get("mi_rfc")
    if mi_rfc:
        clauses.append("cfdis.mi_rfc = ?")
        params.append(normalizar_mi_rfc(mi_rfc))

    desde = filtros.get("desde")
    hasta = filtros.get("hasta")
    if desde:
        clauses.append("cfdis.fecha >= ?")
        params.append(desde)
    if hasta:
        clauses.append("cfdis.fecha <= ?")
        params.append(f"{hasta}T23:59:59")

    busqueda = filtros.get("busqueda")
    if busqueda:
        like = f"%{busqueda.lower()}%"
        clauses.append(
            "(LOWER(cfdis.emisor_nombre) LIKE ? OR LOWER(cfdis.receptor_nombre) LIKE ? "
            "OR LOWER(cfdis.emisor_rfc) LIKE ? OR LOWER(cfdis.receptor_rfc) LIKE ? "
            "OR LOWER(cfdis.uuid) LIKE ? OR LOWER(cfdis.folio) LIKE ?)"
        )
        params.extend([like] * 6)

    return " AND ".join(clauses), params


# Helper SQL: límite extemporáneo (día 5, 23:59:59 del mes siguiente a FechaPago).
_LIMITE_EXTEMP_SQL = (
    "datetime(date(p.cfdi_pago_fecha_pago, 'start of month', '+1 month', '+4 days'),"
    " '23:59:59')"
)


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def stats_pagos(db: ProcesadorDB, filtros: Optional[dict] = None) -> dict:
    """KPIs para las cards del procesador de Pagos (acotados a la empresa)."""
    # El dueño es obligatorio: las queries crudas de esta función no pasan
    # por `_construir_where_ppd` y sin él mezclarían empresas.
    mi_rfc = normalizar_mi_rfc((filtros or {}).get("mi_rfc"))
    where, params = _construir_where_ppd(filtros)
    tol = INTEGRIDAD_TOLERANCE

    # 1) Por cada factura PPD: total pagado + status derivado.
    sql_ppd = f"""
        SELECT
            cfdis.uuid AS uuid,
            cfdis.total AS total,
            COALESCE(SUM(p.docto_imp_pagado), 0) AS total_pagado
        FROM cfdis
        LEFT JOIN pagos_relaciones p
            ON p.docto_uuid = cfdis.uuid AND p.mi_rfc = cfdis.mi_rfc
        WHERE {where}
        GROUP BY cfdis.uuid
    """
    with db.cursor() as cur:
        cur.execute(sql_ppd, params)
        rows = cur.fetchall()

    total_ppd = len(rows)
    sin_complemento = 0
    pagos_parciales = 0
    pagos_completos = 0
    sobrantes = 0
    monto_total_sin_pagar = 0.0

    for r in rows:
        tot = float(r["total"] or 0.0)
        pag = float(r["total_pagado"] or 0.0)
        diff = tot - pag
        if pag <= tol:
            sin_complemento += 1
            monto_total_sin_pagar += tot
        elif diff > tol:
            pagos_parciales += 1
            monto_total_sin_pagar += diff
        elif diff < -tol:
            sobrantes += 1
        else:
            pagos_completos += 1

    # 2) Conteos de tipo P (complementos) y problemas — de LA empresa.
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) AS n FROM cfdis WHERE tipo = 'P' AND mi_rfc = ?",
            (mi_rfc,),
        )
        total_pagos = cur.fetchone()["n"]

        # Huérfanos: el docto_uuid NO existe como tipo I cargado (en esta empresa).
        cur.execute(
            """
            SELECT COUNT(DISTINCT p.cfdi_pago_uuid) AS n
            FROM pagos_relaciones p
            WHERE p.mi_rfc = ?
              AND NOT EXISTS (
                SELECT 1 FROM cfdis c
                WHERE c.uuid = p.docto_uuid AND c.mi_rfc = p.mi_rfc AND c.tipo = 'I'
            )
            """,
            (mi_rfc,),
        )
        pagos_huerfanos = cur.fetchone()["n"]

        # Incidencias PUE: el docto_uuid existe pero su metodo_pago es PUE,
        # o el doctoRelacionado vino marcado como PUE.
        cur.execute(
            """
            SELECT COUNT(*) AS n
            FROM pagos_relaciones p
            LEFT JOIN cfdis c ON c.uuid = p.docto_uuid AND c.mi_rfc = p.mi_rfc
            WHERE p.mi_rfc = ?
              AND ((p.docto_metodo_pago = 'PUE') OR (c.metodo_pago = 'PUE'))
            """,
            (mi_rfc,),
        )
        incidencias_pue = cur.fetchone()["n"]

        # Complementos extemporáneos.
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT p.cfdi_pago_uuid) AS n,
                   COALESCE(SUM(c.total), 0) AS monto
            FROM pagos_relaciones p
            JOIN cfdis c ON c.uuid = p.cfdi_pago_uuid AND c.mi_rfc = p.mi_rfc
            WHERE p.mi_rfc = ? AND c.fecha > {_LIMITE_EXTEMP_SQL}
            """,
            (mi_rfc,),
        )
        ext_row = cur.fetchone()
        complementos_extemporaneos = ext_row["n"]
        monto_extemporaneos = float(ext_row["monto"] or 0.0)

        # Total "global" PPD = de la empresa, sin filtros de UI — para
        # detectar buffer vacío en la UI.
        cur.execute(
            "SELECT COUNT(*) FROM cfdis "
            "WHERE tipo = 'I' AND metodo_pago = 'PPD' AND mi_rfc = ?",
            (mi_rfc,),
        )
        total_global_ppd = cur.fetchone()[0]

    porcentaje_conciliados = (
        round(100.0 * (total_ppd - sin_complemento) / total_ppd, 1)
        if total_ppd > 0
        else 0.0
    )

    return {
        "total_ingresos_ppd": total_ppd,
        "total_global_ppd": total_global_ppd,
        "sin_complemento": sin_complemento,
        "pagos_parciales": pagos_parciales,
        "pagos_completos": pagos_completos,
        "sobrantes": sobrantes,
        "monto_total_sin_pagar": round(monto_total_sin_pagar, 2),
        "total_pagos": total_pagos,
        "pagos_huerfanos": pagos_huerfanos,
        "incidencias_pue": incidencias_pue,
        "porcentaje_conciliados": porcentaje_conciliados,
        "complementos_extemporaneos": complementos_extemporaneos,
        "monto_complementos_extemporaneos": round(monto_extemporaneos, 2),
    }


# ---------------------------------------------------------------------------
# Facturas PPD con status
# ---------------------------------------------------------------------------


def _status_de(total: float, total_pagado: float) -> str:
    diff = total - total_pagado
    tol = INTEGRIDAD_TOLERANCE
    if total_pagado <= tol:
        return "sin_complemento"
    if abs(diff) <= tol:
        return "pagado_completo"
    if diff < -tol:
        return "sobrante"
    return "pago_parcial"


def facturas_ppd(
    db: ProcesadorDB,
    filtros: Optional[dict] = None,
    status_in: Optional[list[str]] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """
    Lista paginada de facturas PPD con status calculado. Filtros opcionales
    por status (post-cálculo, dado que es derivado).
    """
    where, params = _construir_where_ppd(filtros)
    sql = f"""
        SELECT
            cfdis.uuid,
            cfdis.fecha,
            cfdis.serie,
            cfdis.folio,
            cfdis.emisor_rfc,
            cfdis.emisor_nombre,
            cfdis.receptor_rfc,
            cfdis.receptor_nombre,
            cfdis.total,
            cfdis.moneda,
            cfdis.estado_sat,
            COALESCE(SUM(p.docto_imp_pagado), 0) AS total_pagado,
            COUNT(DISTINCT p.cfdi_pago_uuid) AS num_pagos
        FROM cfdis
        LEFT JOIN pagos_relaciones p
            ON p.docto_uuid = cfdis.uuid AND p.mi_rfc = cfdis.mi_rfc
        WHERE {where}
        GROUP BY cfdis.uuid
        ORDER BY cfdis.fecha DESC, cfdis.uuid
    """
    with db.cursor() as cur:
        cur.execute(sql, params)
        rows = cur.fetchall()

    items = []
    for r in rows:
        tot = float(r["total"] or 0.0)
        pag = float(r["total_pagado"] or 0.0)
        status = _status_de(tot, pag)
        if status_in and status not in status_in:
            continue
        warnings = []
        if status == "sobrante":
            warnings.append(f"Sobrante de ${pag - tot:,.2f}")
        items.append(
            {
                "uuid": r["uuid"],
                "fecha": r["fecha"],
                "serie": r["serie"],
                "folio": r["folio"],
                "emisor_rfc": r["emisor_rfc"],
                "emisor_nombre": r["emisor_nombre"],
                "receptor_rfc": r["receptor_rfc"],
                "receptor_nombre": r["receptor_nombre"],
                "total": tot,
                "total_pagado": pag,
                "saldo_pendiente": round(max(tot - pag, 0.0), 2),
                "num_pagos": r["num_pagos"],
                "moneda": r["moneda"],
                "estado_sat": r["estado_sat"],
                "status": status,
                "warnings": warnings,
            }
        )

    total = len(items)
    offset = max(0, (page - 1) * page_size)
    paginadas = items[offset : offset + page_size]
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": paginadas,
    }


# ---------------------------------------------------------------------------
# Drilldown: pagos relacionados a una factura PPD
# ---------------------------------------------------------------------------


def detalle_pagos_de_ppd(db: ProcesadorDB, ppd_uuid: str, mi_rfc: str) -> list[dict]:
    """Lista de pagos asociados a una factura PPD (de una empresa), ordenados
    por parcialidad. El uuid ya no identifica una fila única — el mismo CFDI
    puede vivir bajo dos empresas del catálogo."""
    sql = """
        SELECT
            p.cfdi_pago_uuid,
            c.fecha AS fecha_emision_complemento,
            p.cfdi_pago_fecha_pago,
            p.cfdi_pago_forma,
            p.docto_num_parcialidad,
            p.docto_imp_saldo_ant,
            p.docto_imp_pagado,
            p.docto_imp_saldo_insoluto,
            p.docto_moneda,
            c.emisor_rfc AS pago_emisor_rfc,
            c.emisor_nombre AS pago_emisor_nombre
        FROM pagos_relaciones p
        JOIN cfdis c ON c.uuid = p.cfdi_pago_uuid AND c.mi_rfc = p.mi_rfc
        WHERE p.docto_uuid = ? AND p.mi_rfc = ?
        ORDER BY p.docto_num_parcialidad, p.cfdi_pago_fecha_pago
    """
    with db.cursor() as cur:
        cur.execute(sql, (ppd_uuid, normalizar_mi_rfc(mi_rfc)))
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Análisis de fechas: complementos extemporáneos
# ---------------------------------------------------------------------------


def analisis_fechas(db: ProcesadorDB, filtros: Optional[dict] = None) -> list[dict]:
    """
    Lista de complementos emitidos después del día 5 del mes siguiente al
    FechaPago. Devuelve por cada complemento la diferencia en días.
    """
    mi_rfc = normalizar_mi_rfc((filtros or {}).get("mi_rfc"))
    sql = f"""
        SELECT
            p.cfdi_pago_uuid,
            c.fecha AS fecha_emision_complemento,
            p.cfdi_pago_fecha_pago,
            c.emisor_rfc,
            c.emisor_nombre,
            c.total AS monto_complemento,
            {_LIMITE_EXTEMP_SQL} AS limite,
            CAST(julianday(c.fecha) - julianday({_LIMITE_EXTEMP_SQL}) AS INTEGER) AS dias_retraso,
            p.docto_uuid AS factura_uuid,
            (SELECT folio FROM cfdis
             WHERE uuid = p.docto_uuid AND mi_rfc = p.mi_rfc) AS factura_folio
        FROM pagos_relaciones p
        JOIN cfdis c ON c.uuid = p.cfdi_pago_uuid AND c.mi_rfc = p.mi_rfc
        WHERE p.mi_rfc = ? AND c.fecha > {_LIMITE_EXTEMP_SQL}
        ORDER BY dias_retraso DESC, c.fecha DESC
    """
    with db.cursor() as cur:
        cur.execute(sql, (mi_rfc,))
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Pagos huérfanos
# ---------------------------------------------------------------------------


def pagos_huerfanos(db: ProcesadorDB, filtros: Optional[dict] = None) -> list[dict]:
    """
    Complementos cuyo `docto_uuid` no existe en `cfdis` (PPD nunca cargado
    bajo esta empresa). Para cada complemento huérfano lista los UUIDs
    documentos referenciados.
    """
    mi_rfc = normalizar_mi_rfc((filtros or {}).get("mi_rfc"))
    sql = """
        SELECT
            c.uuid AS cfdi_pago_uuid,
            c.fecha AS fecha_emision,
            c.emisor_rfc,
            c.emisor_nombre,
            c.total AS monto,
            GROUP_CONCAT(p.docto_uuid, '|') AS documentos_referenciados
        FROM cfdis c
        JOIN pagos_relaciones p
            ON p.cfdi_pago_uuid = c.uuid AND p.mi_rfc = c.mi_rfc
        WHERE c.tipo = 'P'
          AND c.mi_rfc = ?
          AND NOT EXISTS (
              SELECT 1 FROM cfdis ppd
              WHERE ppd.uuid = p.docto_uuid AND ppd.mi_rfc = p.mi_rfc
                AND ppd.tipo = 'I'
          )
        GROUP BY c.uuid
        ORDER BY c.fecha DESC
    """
    with db.cursor() as cur:
        cur.execute(sql, (mi_rfc,))
        return [dict(r) for r in cur.fetchall()]


# ---------------------------------------------------------------------------
# Incidencias PUE+complemento (riesgo fiscal)
# ---------------------------------------------------------------------------


def incidencias_pue(db: ProcesadorDB, filtros: Optional[dict] = None) -> list[dict]:
    """
    Complementos referenciando facturas con MetodoPago=PUE. SAT considera
    el ingreso "ya pagado en un acto" en el momento de la emisión PUE; emitir
    un complemento adicional duplica el ingreso ante el SAT.
    """
    mi_rfc = normalizar_mi_rfc((filtros or {}).get("mi_rfc"))
    sql = """
        SELECT
            ppd.uuid AS factura_uuid,
            ppd.fecha AS factura_fecha,
            ppd.emisor_rfc,
            ppd.emisor_nombre,
            ppd.total AS factura_total,
            ppd.metodo_pago AS factura_metodo_pago,
            p.cfdi_pago_uuid AS complemento_uuid,
            p.cfdi_pago_fecha_pago,
            p.docto_imp_pagado AS monto_pagado,
            p.docto_metodo_pago AS docto_metodo_pago
        FROM pagos_relaciones p
        LEFT JOIN cfdis ppd ON ppd.uuid = p.docto_uuid AND ppd.mi_rfc = p.mi_rfc
        WHERE p.mi_rfc = ?
          AND (p.docto_metodo_pago = 'PUE' OR ppd.metodo_pago = 'PUE')
        ORDER BY ppd.fecha DESC, p.cfdi_pago_fecha_pago DESC
    """
    with db.cursor() as cur:
        cur.execute(sql, (mi_rfc,))
        out = []
        for r in cur.fetchall():
            d = dict(r)
            d["descripcion_riesgo"] = (
                "Factura emitida con MetodoPago=PUE (pago en un acto, ingreso ya "
                "reportado al SAT). Emitir un complemento de pago referenciándola "
                "duplica el ingreso ante el SAT. Si la factura es realmente PPD, "
                "cancelar y reemitir; si es PUE, cancelar el complemento."
            )
            out.append(d)
        return out

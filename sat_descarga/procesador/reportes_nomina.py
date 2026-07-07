"""
Reportes del procesador de Nómina.

Mayormente SQL puro sobre `cfdis + nomina_recibos + nomina_conceptos`
(migración 005). El reporte de Deducibilidad agrupa por empleado-mes en
Python con dicts porque el cálculo de ISR por bracket no se expresa bien en
SQL puro.

Conceptos:
- **Recibo**: 1 fila en `nomina_recibos` (1:1 con CFDI tipo N).
- **Concepto**: 1 fila en `nomina_conceptos` (N:1 al recibo, clase ∈ Percepcion/Deduccion/OtroPago).
- **ISR teórico**: `calcular_isr_bruto(gravado_mes, year)` - SPE aplicable.
  Replicamos el comportamiento del web app de todoconta — sin prorrateo para
  periodos parciales; en su lugar emitimos `advertencia_periodo` cuando la
  periodicidad es semanal/catorcenal/quincenal y solo se detecta una porción
  del mes (ver memoria post-PR para prorrateo correcto Art. 96 LISR).
- **Conciliación IMSS**: SBC × tasas agregadas (patronal 18.75%, obrera 6.25%).
"""

from __future__ import annotations

from typing import Any, Optional

from .catalogos import PERIODICIDAD_PAGO
from .constants_nomina import (
    IMSS_TASA_AGREGADA_OBRERA,
    IMSS_TASA_AGREGADA_PATRONAL,
    PERIODOS_ESPERADOS_POR_MES,
    SBC_TOPE_DIARIO,
    calcular_isr_bruto,
    calcular_spe,
    get_limite_spe,
    get_tarifa_year_label,
)
from .db import ProcesadorDB, normalizar_mi_rfc


# ---------------------------------------------------------------------------
# Filtros (espejo del shape de la UI)
# ---------------------------------------------------------------------------


def _construir_where_nomina(filtros: Optional[dict]) -> tuple[str, list]:
    """
    Construye la cláusula WHERE para queries que hacen JOIN entre
    `nomina_recibos` y `cfdis`. Devuelve un string que arranca con "WHERE"
    o vacío.
    """
    clauses: list[str] = []
    params: list[Any] = []

    if not filtros:
        return "", params

    # Dueño del buffer (empresa activa) — acota todo el reporte.
    mi_rfc = filtros.get("mi_rfc")
    if mi_rfc:
        clauses.append("cfdis.mi_rfc = ?")
        params.append(normalizar_mi_rfc(mi_rfc))

    desde = filtros.get("desde")
    hasta = filtros.get("hasta")
    if desde:
        clauses.append("nomina_recibos.fecha_pago >= ?")
        params.append(desde)
    if hasta:
        clauses.append("nomina_recibos.fecha_pago <= ?")
        # `fecha_pago` viene como ISO YYYY-MM-DD del SAT; comparación lex funciona.
        params.append(f"{hasta}T23:59:59")

    tipo_nomina = filtros.get("tipo_nomina")
    if tipo_nomina in ("O", "E"):
        clauses.append("nomina_recibos.tipo_nomina = ?")
        params.append(tipo_nomina)

    periodicidad = filtros.get("periodicidad") or filtros.get("periodicidad_pago")
    if periodicidad:
        clauses.append("nomina_recibos.periodicidad_pago = ?")
        params.append(periodicidad)

    busqueda = filtros.get("busqueda")
    if busqueda:
        like = f"%{busqueda.lower()}%"
        clauses.append(
            "(LOWER(cfdis.emisor_nombre) LIKE ? OR LOWER(cfdis.receptor_nombre) LIKE ? "
            "OR LOWER(cfdis.emisor_rfc) LIKE ? OR LOWER(cfdis.receptor_rfc) LIKE ? "
            "OR LOWER(cfdis.uuid) LIKE ? OR LOWER(nomina_recibos.nss) LIKE ? "
            "OR LOWER(nomina_recibos.curp) LIKE ? OR LOWER(nomina_recibos.num_empleado) LIKE ?)"
        )
        params.extend([like] * 8)

    if filtros.get("solo_con_errores"):
        clauses.append("cfdis.warnings_json != '[]' AND cfdis.warnings_json IS NOT NULL")

    if not clauses:
        return "", params
    return "WHERE " + " AND ".join(clauses), params


# ---------------------------------------------------------------------------
# Helpers de fechas
# ---------------------------------------------------------------------------


def _extraer_anio_y_mes(fecha_iso: str) -> tuple[Optional[int], Optional[int]]:
    """De 'YYYY-MM-DD' o 'YYYY-MM-DDTHH:MM:SS' devuelve (año, mes)."""
    if not fecha_iso or len(fecha_iso) < 7:
        return None, None
    try:
        year = int(fecha_iso[0:4])
        month = int(fecha_iso[5:7])
        if 2000 <= year <= 2100 and 1 <= month <= 12:
            return year, month
    except (ValueError, TypeError):
        pass
    return None, None


def _clave_mes(fecha_iso: str) -> str:
    y, m = _extraer_anio_y_mes(fecha_iso)
    if y is None or m is None:
        return "unknown"
    return f"{y:04d}-{m:02d}"


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


def stats_nomina(db: ProcesadorDB, filtros: Optional[dict] = None) -> dict:
    """KPIs para las cards del procesador de Nómina (acotados a la empresa)."""
    # El dueño es obligatorio: el conteo global de esta función no pasa por
    # `_construir_where_nomina` y sin él mezclaría empresas.
    mi_rfc = normalizar_mi_rfc((filtros or {}).get("mi_rfc"))
    where, params = _construir_where_nomina(filtros)

    sql_recibos = f"""
        SELECT
            COUNT(*) AS total_recibos,
            COUNT(DISTINCT cfdis.receptor_rfc) AS total_empleados,
            COALESCE(SUM(CASE WHEN nomina_recibos.tipo_nomina = 'O' THEN 1 ELSE 0 END), 0) AS ord,
            COALESCE(SUM(CASE WHEN nomina_recibos.tipo_nomina = 'E' THEN 1 ELSE 0 END), 0) AS ext,
            COALESCE(SUM(nomina_recibos.total_percepciones), 0) AS total_percepciones,
            COALESCE(SUM(nomina_recibos.total_deducciones), 0) AS total_deducciones,
            COALESCE(SUM(nomina_recibos.total_otros_pagos), 0) AS total_otros_pagos
        FROM nomina_recibos
        JOIN cfdis ON cfdis.uuid = nomina_recibos.cfdi_uuid
                  AND cfdis.mi_rfc = nomina_recibos.mi_rfc
        {where}
    """
    sql_conceptos = f"""
        SELECT COUNT(*) AS total_conceptos
        FROM nomina_conceptos
        JOIN nomina_recibos ON nomina_recibos.cfdi_uuid = nomina_conceptos.cfdi_uuid
                           AND nomina_recibos.mi_rfc = nomina_conceptos.mi_rfc
        JOIN cfdis ON cfdis.uuid = nomina_recibos.cfdi_uuid
                  AND cfdis.mi_rfc = nomina_recibos.mi_rfc
        {where}
    """
    sql_con_errores = f"""
        SELECT COUNT(DISTINCT cfdis.uuid) AS c
        FROM cfdis
        JOIN nomina_recibos ON nomina_recibos.cfdi_uuid = cfdis.uuid
                           AND nomina_recibos.mi_rfc = cfdis.mi_rfc
        {where if where else ""}
        {"AND" if where else "WHERE"} cfdis.warnings_json != '[]'
                                  AND cfdis.warnings_json IS NOT NULL
    """

    with db.cursor() as cur:
        cur.execute(sql_recibos, params)
        r = cur.fetchone()
        cur.execute(sql_conceptos, params)
        c = cur.fetchone()
        cur.execute(sql_con_errores, params)
        e = cur.fetchone()
        # "Global" = todos los recibos de LA EMPRESA sin filtros de UI —
        # para el empty-state de la UI.
        cur.execute(
            "SELECT COUNT(*) FROM nomina_recibos WHERE mi_rfc = ?",
            (mi_rfc,),
        )
        global_count = cur.fetchone()[0]

    total_percepciones = float(r["total_percepciones"] or 0.0)
    total_deducciones = float(r["total_deducciones"] or 0.0)
    total_otros_pagos = float(r["total_otros_pagos"] or 0.0)

    return {
        "total_recibos": int(r["total_recibos"] or 0),
        "total_global_recibos": int(global_count or 0),
        "total_empleados": int(r["total_empleados"] or 0),
        "total_conceptos": int(c["total_conceptos"] or 0),
        "nominas_ordinarias": int(r["ord"] or 0),
        "nominas_extraordinarias": int(r["ext"] or 0),
        "total_percepciones": total_percepciones,
        "total_deducciones": total_deducciones,
        "total_otros_pagos": total_otros_pagos,
        "neto_a_pagar": total_percepciones - total_deducciones + total_otros_pagos,
        "conceptos_con_errores": int(e["c"] or 0),
    }


# ---------------------------------------------------------------------------
# Listar recibos (1 fila por CFDI tipo N)
# ---------------------------------------------------------------------------


def listar_recibos(
    db: ProcesadorDB,
    filtros: Optional[dict] = None,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """Devuelve recibos paginados con datos del trabajador y totales."""
    where, params = _construir_where_nomina(filtros)
    offset = max(0, (page - 1) * page_size)

    sql_count = f"""
        SELECT COUNT(*) FROM nomina_recibos
        JOIN cfdis ON cfdis.uuid = nomina_recibos.cfdi_uuid
                  AND cfdis.mi_rfc = nomina_recibos.mi_rfc
        {where}
    """
    sql_items = f"""
        SELECT
            cfdis.uuid AS cfdi_uuid,
            cfdis.fecha AS fecha,
            cfdis.emisor_rfc, cfdis.emisor_nombre,
            cfdis.receptor_rfc, cfdis.receptor_nombre,
            cfdis.estado_sat, cfdis.warnings_json,
            nomina_recibos.*
        FROM nomina_recibos
        JOIN cfdis ON cfdis.uuid = nomina_recibos.cfdi_uuid
                  AND cfdis.mi_rfc = nomina_recibos.mi_rfc
        {where}
        ORDER BY nomina_recibos.fecha_pago DESC, cfdis.uuid
        LIMIT ? OFFSET ?
    """

    with db.cursor() as cur:
        cur.execute(sql_count, params)
        total = cur.fetchone()[0]
        cur.execute(sql_items, (*params, page_size, offset))
        rows = cur.fetchall()

    items = []
    import json as _json
    for r in rows:
        d = dict(r)
        try:
            warnings = _json.loads(d.get("warnings_json") or "[]")
        except (ValueError, TypeError):
            warnings = []
        d.pop("warnings_json", None)
        d["warnings"] = warnings
        d["neto"] = (
            float(d.get("total_percepciones") or 0.0)
            - float(d.get("total_deducciones") or 0.0)
            + float(d.get("total_otros_pagos") or 0.0)
        )
        items.append(d)

    return {"total": total, "page": page, "page_size": page_size, "items": items}


# ---------------------------------------------------------------------------
# Drilldown: conceptos de un recibo
# ---------------------------------------------------------------------------


_ORDEN_CLASE = {"Percepcion": 0, "Deduccion": 1, "OtroPago": 2}


def conceptos_de_recibo(db: ProcesadorDB, cfdi_uuid: str, mi_rfc: str) -> list[dict]:
    """Devuelve los conceptos del recibo (de una empresa) ordenados por clase
    y tipo. El uuid ya no identifica una fila única — el mismo CFDI puede
    vivir bajo dos empresas del catálogo."""
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT clase, tipo_concepto, clave_interna, concepto,
                   importe_gravado, importe_exento, importe, subsidio_causado
            FROM nomina_conceptos
            WHERE cfdi_uuid = ? AND mi_rfc = ?
            """,
            (cfdi_uuid, normalizar_mi_rfc(mi_rfc)),
        )
        rows = [dict(r) for r in cur.fetchall()]

    rows.sort(key=lambda r: (_ORDEN_CLASE.get(r["clase"], 9), r["tipo_concepto"] or ""))
    return rows


# ---------------------------------------------------------------------------
# Helpers comunes a los reportes (carga de records aplanados)
# ---------------------------------------------------------------------------


def _cargar_records(db: ProcesadorDB, filtros: Optional[dict]) -> list[dict]:
    """
    Carga todos los conceptos del scope con todos los campos del recibo y
    cabecera del CFDI necesarios para los reportes. Devuelve "records"
    espejo del shape `NominaRecord` de todoconta — 1 record por concepto.
    """
    where, params = _construir_where_nomina(filtros)
    sql = f"""
        SELECT
            cfdis.uuid AS cfdi_uuid,
            cfdis.fecha AS fecha,
            cfdis.receptor_rfc, cfdis.receptor_nombre,
            nomina_recibos.curp, nomina_recibos.nss, nomina_recibos.num_empleado,
            nomina_recibos.tipo_nomina, nomina_recibos.fecha_pago,
            nomina_recibos.periodicidad_pago, nomina_recibos.num_dias_pagados,
            nomina_recibos.salario_base_cot_apor, nomina_recibos.salario_diario_integrado,
            nomina_recibos.tipo_regimen, nomina_recibos.riesgo_trabajo,
            nomina_conceptos.clase, nomina_conceptos.tipo_concepto,
            nomina_conceptos.concepto,
            nomina_conceptos.importe_gravado, nomina_conceptos.importe_exento,
            nomina_conceptos.importe, nomina_conceptos.subsidio_causado
        FROM nomina_conceptos
        JOIN nomina_recibos ON nomina_recibos.cfdi_uuid = nomina_conceptos.cfdi_uuid
                           AND nomina_recibos.mi_rfc = nomina_conceptos.mi_rfc
        JOIN cfdis ON cfdis.uuid = nomina_recibos.cfdi_uuid
                  AND cfdis.mi_rfc = nomina_recibos.mi_rfc
        {where}
    """
    with db.cursor() as cur:
        cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]


def _rango_fechas(records: list[dict]) -> tuple[str, str]:
    fechas = sorted({r["fecha_pago"] for r in records if r.get("fecha_pago")})
    if not fechas:
        return "", ""
    return fechas[0], fechas[-1]


# ---------------------------------------------------------------------------
# Reporte 1 — Deductibilidad fiscal
# ---------------------------------------------------------------------------


def _detectar_periodo_incompleto(periodicidad: str, uuids_unicos: int) -> Optional[str]:
    esperado = PERIODOS_ESPERADOS_POR_MES.get(periodicidad)
    if esperado and uuids_unicos < esperado[0]:
        return (
            f"Periodo posiblemente incompleto: {uuids_unicos} de {esperado[0]} "
            f"{esperado[1]} detectadas"
        )
    return None


def reporte_deducibilidad(
    db: ProcesadorDB, filtros: Optional[dict] = None
) -> dict:
    """ISR teórico vs retenido, agrupando por empleado y mes."""
    records = _cargar_records(db, filtros)
    if not records:
        return _deducibilidad_vacia()

    periodo_inicio, periodo_fin = _rango_fechas(records)

    # Año detectado desde la última fecha_pago del scope.
    anio_detectado, _ = _extraer_anio_y_mes(periodo_fin)
    if anio_detectado is None:
        import datetime as _dt
        anio_detectado = _dt.datetime.now().year

    # Totales globales (sobre todos los records).
    percepciones = [r for r in records if r["clase"] == "Percepcion"]
    deducciones = [r for r in records if r["clase"] == "Deduccion"]

    total_percepciones = sum(
        (r["importe_gravado"] or 0.0) + (r["importe_exento"] or 0.0)
        for r in percepciones
    )
    percepciones_gravadas = sum(r["importe_gravado"] or 0.0 for r in percepciones)
    percepciones_exentas = sum(r["importe_exento"] or 0.0 for r in percepciones)

    seguro_social = sum(
        r["importe"] or 0.0 for r in deducciones if r["tipo_concepto"] == "001"
    )
    isr_retenido = sum(
        r["importe"] or 0.0 for r in deducciones if r["tipo_concepto"] == "002"
    )
    aportaciones_retiro_cesantia = sum(
        r["importe"] or 0.0 for r in deducciones if r["tipo_concepto"] == "003"
    )
    otros_deducciones = sum(
        r["importe"] or 0.0
        for r in deducciones
        if r["tipo_concepto"] not in ("001", "002", "003")
    )
    total_deducciones = sum(r["importe"] or 0.0 for r in deducciones)
    salario_neto = total_percepciones - total_deducciones

    # Agrupar por empleado (RFC) y por mes.
    empleados: dict[str, list[dict]] = {}
    for rec in records:
        rfc = rec["receptor_rfc"] or ""
        empleados.setdefault(rfc, []).append(rec)

    desglose: list[dict] = []
    advertencias: list[str] = []
    isr_teorico_total = 0.0
    isr_bruto_total = 0.0
    subsidio_total = 0.0

    for rfc, emp_records in empleados.items():
        # Agrupar por mes para calcular ISR mensual.
        meses: dict[str, list[dict]] = {}
        for rec in emp_records:
            k = _clave_mes(rec["fecha_pago"])
            meses.setdefault(k, []).append(rec)

        isr_teorico_emp = 0.0
        isr_bruto_emp = 0.0
        subsidio_emp = 0.0

        for mes_records in meses.values():
            percepciones_mes = [
                r for r in mes_records if r["clase"] == "Percepcion"
            ]
            gravado_mes = sum(r["importe_gravado"] or 0.0 for r in percepciones_mes)
            mes_num = _extraer_anio_y_mes(percepciones_mes[0]["fecha_pago"])[1] if percepciones_mes else 2
            mes_num = mes_num or 2

            isr_bruto_mes = calcular_isr_bruto(gravado_mes, anio_detectado)
            limite_spe = get_limite_spe(anio_detectado)
            aplica_spe = gravado_mes <= limite_spe
            spe_mes = calcular_spe(gravado_mes, anio_detectado, mes_num) if aplica_spe else 0.0
            isr_teorico_mes = max(0.0, isr_bruto_mes - spe_mes)

            isr_teorico_emp += isr_teorico_mes
            isr_bruto_emp += isr_bruto_mes
            subsidio_emp += spe_mes

        # Datos del empleado.
        nombre_emp = next(
            (r.get("receptor_nombre") for r in emp_records if r.get("receptor_nombre")),
            rfc,
        ) or rfc
        percepciones_emp = [r for r in emp_records if r["clase"] == "Percepcion"]
        gravado_emp = sum(r["importe_gravado"] or 0.0 for r in percepciones_emp)
        isr_retenido_emp = sum(
            r["importe"] or 0.0
            for r in emp_records
            if r["clase"] == "Deduccion" and r["tipo_concepto"] == "002"
        )
        periodicidad = next(
            (r.get("periodicidad_pago") for r in emp_records if r.get("periodicidad_pago")),
            "99",
        )
        uuids_unicos = len({r["cfdi_uuid"] for r in emp_records})
        meses_detectados = len(meses)

        advertencia: Optional[str]
        if meses_detectados > 1:
            advertencia = f"{meses_detectados} meses detectados. ISR calculado por mes."
        else:
            advertencia = _detectar_periodo_incompleto(periodicidad, uuids_unicos)

        if advertencia:
            advertencias.append(f"{nombre_emp}: {advertencia}")

        isr_teorico_total += isr_teorico_emp
        isr_bruto_total += isr_bruto_emp
        subsidio_total += subsidio_emp

        desglose.append({
            "rfc": rfc,
            "nombre": nombre_emp,
            "percepciones_gravadas": gravado_emp,
            "isr_retenido": isr_retenido_emp,
            "isr_teorico": isr_teorico_emp,
            "diferencia": isr_retenido_emp - isr_teorico_emp,
            "periodicidad": PERIODICIDAD_PAGO.get(periodicidad, periodicidad),
            "periodos_detectados": uuids_unicos,
            "meses_detectados": meses_detectados,
            "advertencia_periodo": advertencia,
        })

    desglose.sort(key=lambda d: (d["nombre"] or "").lower())

    isr_diferencia = isr_retenido - isr_teorico_total

    alguno_aplica_spe = any(
        d["percepciones_gravadas"] <= get_limite_spe(anio_detectado) for d in desglose
    )

    # Recomendaciones (heurísticas, espejo del referente).
    recomendaciones: list[str] = []
    if isr_diferencia > 100:
        recomendaciones.append(
            f"ISR retenido ({isr_retenido:.2f}) es mayor al calculado "
            f"({isr_teorico_total:.2f}). Posible sobrepago."
        )
    elif isr_diferencia < -100:
        recomendaciones.append(
            f"ISR retenido ({isr_retenido:.2f}) es menor al calculado "
            f"({isr_teorico_total:.2f}). Revisar retenciones."
        )

    if total_percepciones > 0 and percepciones_exentas > total_percepciones * 0.3:
        recomendaciones.append(
            f"Percepciones exentas son "
            f"{(percepciones_exentas / total_percepciones) * 100:.1f}% del total."
        )

    if seguro_social == 0:
        recomendaciones.append(
            "No hay aportaciones de Seguro Social. Verificar nómina."
        )

    if len(desglose) > 1:
        recomendaciones.append(
            f"Se analizaron {len(desglose)} trabajadores. "
            "El ISR teórico se calculó individualmente para cada uno."
        )

    # Adecuación
    if isr_diferencia > 500:
        adecuacion = "SOBREPAGO"
    elif isr_diferencia < -500:
        adecuacion = "SUBRETENCION"
    else:
        adecuacion = "NORMAL"

    proporcion_gravado = (
        (percepciones_gravadas / total_percepciones * 100.0)
        if total_percepciones > 0
        else 0.0
    )
    tasa_deduccion = (
        (total_deducciones / total_percepciones * 100.0)
        if total_percepciones > 0
        else 0.0
    )

    return {
        "reporte": "deducibilidad",
        "periodo_inicio": periodo_inicio,
        "periodo_fin": periodo_fin,
        "total_percepciones": total_percepciones,
        "percepciones_gravadas": percepciones_gravadas,
        "percepciones_exentas": percepciones_exentas,
        "total_deducciones": total_deducciones,
        "seguro_social": seguro_social,
        "isr_retenido": isr_retenido,
        "aportaciones_retiro_cesantia": aportaciones_retiro_cesantia,
        "otros_deducciones": otros_deducciones,
        "salario_neto": salario_neto,
        "isr_analisis": {
            "year_detected": anio_detectado,
            "tarifa_label": get_tarifa_year_label(anio_detectado),
            "isr_bruto": isr_bruto_total,
            "subsidio_aplicado": subsidio_total,
            "isr_teorico": isr_teorico_total,
            "isr_diferencia": isr_diferencia,
            "limite_spe": get_limite_spe(anio_detectado),
            "aplica_spe": alguno_aplica_spe,
        },
        "empleados_analizados": len(desglose),
        "desglose_por_empleado": desglose,
        "advertencias_periodo": advertencias,
        "recomendaciones": recomendaciones,
        "detalle_analisis": {
            "cumplimiento_retenciones": (
                "Cumple correctamente"
                if abs(isr_diferencia) < 100
                else "Revisar retenciones"
            ),
            "adecuacion_fiscal": adecuacion,
            "observaciones": [
                f"ISR diferencia: {isr_diferencia:.2f}",
                f"Proporción gravado/total: {proporcion_gravado:.1f}%",
                f"Tasa de deducción: {tasa_deduccion:.1f}%",
            ],
        },
    }


def _deducibilidad_vacia() -> dict:
    import datetime as _dt
    year = _dt.datetime.now().year
    return {
        "reporte": "deducibilidad",
        "periodo_inicio": "",
        "periodo_fin": "",
        "total_percepciones": 0.0,
        "percepciones_gravadas": 0.0,
        "percepciones_exentas": 0.0,
        "total_deducciones": 0.0,
        "seguro_social": 0.0,
        "isr_retenido": 0.0,
        "aportaciones_retiro_cesantia": 0.0,
        "otros_deducciones": 0.0,
        "salario_neto": 0.0,
        "isr_analisis": {
            "year_detected": year,
            "tarifa_label": get_tarifa_year_label(year),
            "isr_bruto": 0.0,
            "subsidio_aplicado": 0.0,
            "isr_teorico": 0.0,
            "isr_diferencia": 0.0,
            "limite_spe": get_limite_spe(year),
            "aplica_spe": False,
        },
        "empleados_analizados": 0,
        "desglose_por_empleado": [],
        "advertencias_periodo": [],
        "recomendaciones": [],
        "detalle_analisis": {
            "cumplimiento_retenciones": "",
            "adecuacion_fiscal": "N/A",
            "observaciones": [],
        },
    }


# ---------------------------------------------------------------------------
# Reporte 2 — Conciliación IMSS
# ---------------------------------------------------------------------------


def reporte_imss(db: ProcesadorDB, filtros: Optional[dict] = None) -> dict:
    """SBC, SDI, aportaciones patronal/obrero, alertas."""
    records = _cargar_records(db, filtros)
    if not records:
        return _imss_vacio()

    periodo_inicio, periodo_fin = _rango_fechas(records)

    # Agrupar por empleado (NSS si hay, sino RFC).
    empleados: dict[str, list[dict]] = {}
    for rec in records:
        key = rec.get("nss") or rec.get("receptor_rfc") or ""
        empleados.setdefault(key, []).append(rec)

    registros = []
    empleados_sin_nss: list[str] = []
    sbc_fuera_limites: list[str] = []
    dias_anomalous: list[str] = []

    for key, recs in empleados.items():
        first = recs[0]
        observaciones: list[str] = []

        nss = first.get("nss") or ""
        rfc = first.get("receptor_rfc") or ""

        if not nss:
            observaciones.append("Sin NSS registrado")
            empleados_sin_nss.append(rfc)

        sbc = float(first.get("salario_base_cot_apor") or 0.0)
        if sbc > SBC_TOPE_DIARIO:
            observaciones.append(
                f"SBC {sbc:.2f} excede tope {SBC_TOPE_DIARIO:.2f}"
            )
            sbc_fuera_limites.append(rfc)

        dias = float(first.get("num_dias_pagados") or 0.0)
        if dias > 31:
            observaciones.append(f"Días pagados anómalo: {dias}")
            dias_anomalous.append(rfc)

        aportaciones_patronal = sbc * IMSS_TASA_AGREGADA_PATRONAL
        aportaciones_obrero = sbc * IMSS_TASA_AGREGADA_OBRERA
        seguro_social = sum(
            r["importe"] or 0.0
            for r in recs
            if r["clase"] == "Deduccion" and r["tipo_concepto"] == "001"
        )

        fechas_registro = sorted({r["fecha_pago"] for r in recs if r.get("fecha_pago")})

        registros.append({
            "rfc": rfc,
            "nss": nss or "SIN REGISTRO",
            "nombre": first.get("receptor_nombre") or "",
            "fechas_registro": fechas_registro,
            "salario_base_cot_apor": sbc,
            "salario_diario_integrado": float(first.get("salario_diario_integrado") or 0.0),
            "dias_trabajados": dias,
            "aportaciones_patronal": aportaciones_patronal,
            "aportaciones_obrero": aportaciones_obrero,
            "seguro_social": seguro_social,
            "tipo_regimen": first.get("tipo_regimen") or "",
            "riesgo_trabajo": first.get("riesgo_trabajo") or "",
            "observaciones": observaciones,
        })

    registros.sort(key=lambda r: (r["nombre"] or r["rfc"]).lower())

    totales = {
        "suma_sbc": sum(r["salario_base_cot_apor"] for r in registros),
        "suma_dias": sum(r["dias_trabajados"] for r in registros),
        "suma_aportaciones_patronal": sum(r["aportaciones_patronal"] for r in registros),
        "suma_aportaciones_obrero": sum(r["aportaciones_obrero"] for r in registros),
        "suma_seguro_social": sum(r["seguro_social"] for r in registros),
    }

    return {
        "reporte": "imss",
        "periodo_inicio": periodo_inicio,
        "periodo_fin": periodo_fin,
        "total_empleados": len(registros),
        "registros": registros,
        "totales": totales,
        "alertas": {
            "empleados_sin_nss": empleados_sin_nss,
            "sbc_fuera_limites": sbc_fuera_limites,
            "dias_anomalous": dias_anomalous,
        },
    }


def _imss_vacio() -> dict:
    return {
        "reporte": "imss",
        "periodo_inicio": "",
        "periodo_fin": "",
        "total_empleados": 0,
        "registros": [],
        "totales": {
            "suma_sbc": 0.0,
            "suma_dias": 0.0,
            "suma_aportaciones_patronal": 0.0,
            "suma_aportaciones_obrero": 0.0,
            "suma_seguro_social": 0.0,
        },
        "alertas": {
            "empleados_sin_nss": [],
            "sbc_fuera_limites": [],
            "dias_anomalous": [],
        },
    }


# ---------------------------------------------------------------------------
# Reporte 3 — Periodo vs Periodo
# ---------------------------------------------------------------------------


def _metricas_periodo(records: list[dict]) -> dict:
    rfcs = {r["receptor_rfc"] for r in records if r.get("receptor_rfc")}
    percepciones = sum(
        (r["importe_gravado"] or 0.0) + (r["importe_exento"] or 0.0)
        for r in records
        if r["clase"] == "Percepcion"
    )
    deducciones = sum(
        r["importe"] or 0.0 for r in records if r["clase"] == "Deduccion"
    )
    fechas = sorted({r["fecha_pago"] for r in records if r.get("fecha_pago")})
    inicio = fechas[0] if fechas else ""
    fin = fechas[-1] if fechas else ""
    return {
        "inicio": inicio,
        "fin": fin,
        "total_empleados": len(rfcs),
        "total_percepciones": percepciones,
        "total_deducciones": deducciones,
        "promedio_por_empleado": (percepciones / len(rfcs)) if rfcs else 0.0,
        "_rfcs": rfcs,
        "_conceptos": {r["tipo_concepto"] for r in records if r.get("tipo_concepto")},
    }


def reporte_periodo_vs_periodo(
    db: ProcesadorDB, filtros: Optional[dict] = None
) -> dict:
    """Auto-detecta los dos meses más recientes y los compara."""
    records = _cargar_records(db, filtros)
    if not records:
        return _periodo_insuficiente("No hay recibos en el buffer.")

    # Separar records por mes (YYYY-MM).
    por_mes: dict[str, list[dict]] = {}
    for rec in records:
        k = _clave_mes(rec.get("fecha_pago") or "")
        if k == "unknown":
            continue
        por_mes.setdefault(k, []).append(rec)

    meses_ordenados = sorted(por_mes.keys(), reverse=True)
    if len(meses_ordenados) < 2:
        return _periodo_insuficiente(
            "Se requieren al menos dos meses cargados para comparar."
        )

    actual_key = meses_ordenados[0]
    previo_key = meses_ordenados[1]
    records_actual = por_mes[actual_key]
    records_previo = por_mes[previo_key]

    m_actual = _metricas_periodo(records_actual)
    m_previo = _metricas_periodo(records_previo)

    empleados_var = m_actual["total_empleados"] - m_previo["total_empleados"]
    percepciones_var = m_actual["total_percepciones"] - m_previo["total_percepciones"]
    deducciones_var = m_actual["total_deducciones"] - m_previo["total_deducciones"]

    pct = lambda var, base: (var / base * 100.0) if base > 0 else 0.0
    empleados_var_pct = pct(empleados_var, m_previo["total_empleados"])
    percepciones_var_pct = pct(percepciones_var, m_previo["total_percepciones"])
    deducciones_var_pct = pct(deducciones_var, m_previo["total_deducciones"])

    empleados_nuevos = sorted(m_actual["_rfcs"] - m_previo["_rfcs"])
    empleados_eliminados = sorted(m_previo["_rfcs"] - m_actual["_rfcs"])
    conceptos_nuevos = sorted(m_actual["_conceptos"] - m_previo["_conceptos"])
    conceptos_eliminados = sorted(m_previo["_conceptos"] - m_actual["_conceptos"])

    if empleados_var_pct > 5:
        tendencia = "CRECIMIENTO"
    elif empleados_var_pct < -5:
        tendencia = "CONTRACCION"
    else:
        tendencia = "ESTABLE"

    observaciones: list[str] = []
    if empleados_var != 0:
        signo = "+" if empleados_var > 0 else ""
        observaciones.append(
            f"Variación de personal: {signo}{empleados_var} "
            f"({empleados_var_pct:.1f}%)"
        )
    if percepciones_var_pct > 10:
        observaciones.append(
            f"Incremento significativo de percepciones: {percepciones_var_pct:.1f}%"
        )
    elif percepciones_var_pct < -5:
        observaciones.append(
            f"Disminución de percepciones: {percepciones_var_pct:.1f}%"
        )
    if empleados_nuevos:
        observaciones.append(f"{len(empleados_nuevos)} empleado(s) nuevo(s)")
    if empleados_eliminados:
        observaciones.append(
            f"{len(empleados_eliminados)} empleado(s) dado(s) de baja"
        )

    # Limpiar campos internos del shape devuelto.
    for d in (m_previo, m_actual):
        d.pop("_rfcs", None)
        d.pop("_conceptos", None)

    return {
        "reporte": "periodo-vs-periodo",
        "insuficiente": False,
        "mensaje_insuficiente": None,
        "periodo_previo": m_previo,
        "periodo_actual": m_actual,
        "variaciones": {
            "empleados_variacion": empleados_var,
            "empleados_variacion_pct": empleados_var_pct,
            "percepciones_variacion": percepciones_var,
            "percepciones_variacion_pct": percepciones_var_pct,
            "deducciones_variacion": deducciones_var,
            "deducciones_variacion_pct": deducciones_var_pct,
            "empleados_nuevos": empleados_nuevos,
            "empleados_eliminados": empleados_eliminados,
            "conceptos_nuevos": conceptos_nuevos,
            "conceptos_eliminados": conceptos_eliminados,
        },
        "analisis_detallado": {
            "tendencia": tendencia,
            "observaciones": observaciones,
        },
    }


def _periodo_insuficiente(mensaje: str) -> dict:
    return {
        "reporte": "periodo-vs-periodo",
        "insuficiente": True,
        "mensaje_insuficiente": mensaje,
        "periodo_previo": None,
        "periodo_actual": None,
        "variaciones": None,
        "analisis_detallado": None,
    }

"""Calculadora de carga patronal (costo real de un empleado).

Port de ``calculadora-carga-patronal/calculations.ts`` (paridad centavo a
centavo). Reutiliza ``sbc.calcular_sbc`` e ``isr.calcular_isr_periodo``.

NOTA (TO-DO documentado): la web simplifica dos fórmulas IMSS y aquí se portan
tal cual para validar el port contra la web:
- La cuota fija de Enfermedad y Maternidad se calcula como 20.40% sobre
  min(SBC, 3 UMA); la LSS (Art. 106 fr. I) la define como 20.40% de la UMA.
- Infonavit se promedia como SBC × 5% × 0.5; el real es 5% sobre base bimestral.
Corregir en AMBOS lados (web + desktop) en el mismo ciclo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .comunes import (
    DIAS_MES_PROMEDIO,
    PRIMAS_RIESGO,
    dias_vacaciones,
    redondear,
    tasa_isn_estado,
)
from .indicadores import get_indicadores
from .isr import calcular_isr_periodo
from .sbc import SBCInput, calcular_sbc


@dataclass(frozen=True)
class CargaPatronalInput:
    salario: float
    tipo_salario: str  # "diario" | "mensual"
    antiguedad_anios: int
    clase_riesgo: str = "I"  # I-V
    prima_riesgo_trabajo: float | None = None  # % (ej. 0.54355); default: prima media de la clase
    codigo_estado: str = "CDMX"
    tasa_impuesto_estatal: float | None = None  # decimal (0.03); default: tasa del estado
    incluir_aguinaldo_mensual: bool = True
    incluir_vacaciones_mensual: bool = True
    prestaciones_adicionales: list[dict] = field(default_factory=list)  # {nombre, monto, tipo}
    anio: int = 2026


def determinar_tasa_cyv(sbc: float, anio: int = 2026) -> float:
    """Tasa patronal de Cesantía y Vejez según el SBC en múltiplos de UMA."""
    ind = get_indicadores(anio)
    if ind.imss is None:
        raise ValueError(f"Cuotas IMSS {anio} no disponibles en indicadores.")
    sbc_en_umas = sbc / ind.uma_diaria
    rangos = ind.imss.cesantia_vejez
    for rango in rangos:
        if rango.max_umas is None:
            if sbc_en_umas >= rango.min_umas:
                return rango.tasa
        elif rango.min_umas <= sbc_en_umas <= rango.max_umas:
            return rango.tasa
    return rangos[-1].tasa


def calcular_cuotas_imss(
    sbc: float, prima_riesgo_trabajo: float, anio: int = 2026
) -> dict:
    """Cuotas patronales IMSS diarias sobre el SBC (redondeadas por concepto)."""
    ind = get_indicadores(anio)
    if ind.imss is None:
        raise ValueError(f"Cuotas IMSS {anio} no disponibles en indicadores.")
    imss = ind.imss

    # Enfermedad y Maternidad: 20.40% + 0.70% hasta 3 UMA, 1.10% sobre el excedente
    tope_3_umas = ind.uma_diaria * 3
    sbc_base = min(sbc, tope_3_umas)
    sbc_excedente = max(0.0, sbc - tope_3_umas)
    enfermedad_maternidad = (
        sbc_base * (imss.enfermedad_maternidad_fija + imss.prestaciones_en_dinero)
        + sbc_excedente * imss.enfermedad_maternidad_excedente
    )

    invalidez_vida = sbc * imss.invalidez_vida
    cesantia_vejez = sbc * determinar_tasa_cyv(sbc, anio)
    guarderias = sbc * imss.guarderias
    riesgos_trabajo = sbc * (prima_riesgo_trabajo / 100)

    total = enfermedad_maternidad + invalidez_vida + cesantia_vejez + guarderias + riesgos_trabajo

    return {
        "enfermedad_maternidad": redondear(enfermedad_maternidad),
        "invalidez_vida": redondear(invalidez_vida),
        "cesantia_vejez": redondear(cesantia_vejez),
        "guarderias": redondear(guarderias),
        "riesgos_trabajo": redondear(riesgos_trabajo),
        "total": redondear(total),
    }


def calcular_carga_patronal(inp: CargaPatronalInput) -> dict:
    if inp.salario <= 0:
        raise ValueError("El salario debe ser mayor a 0.")

    ind = get_indicadores(inp.anio)
    if ind.imss is None:
        raise ValueError(f"Cuotas IMSS {inp.anio} no disponibles en indicadores.")

    prima_riesgo = (
        inp.prima_riesgo_trabajo
        if inp.prima_riesgo_trabajo is not None
        else PRIMAS_RIESGO.get(inp.clase_riesgo, PRIMAS_RIESGO["I"]) * 100
    )
    tasa_estatal = (
        inp.tasa_impuesto_estatal
        if inp.tasa_impuesto_estatal is not None
        else tasa_isn_estado(inp.codigo_estado)
    )

    # 1. Salario diario / mensual (paridad web: diario = mensual/30, pero
    #    mensual desde diario usa 30.4)
    salario_diario = inp.salario / 30 if inp.tipo_salario == "mensual" else inp.salario
    salario_mensual = inp.salario if inp.tipo_salario == "mensual" else salario_diario * DIAS_MES_PROMEDIO
    salario_anual = salario_mensual * 12

    # 2. SBC
    sbc_res = calcular_sbc(
        SBCInput(
            salario=salario_diario,
            tipo_salario="diario",
            antiguedad_anios=inp.antiguedad_anios,
            anio=inp.anio,
        )
    )
    sbc = sbc_res["sbc_diario"]
    sbc_mensual = sbc * DIAS_MES_PROMEDIO

    # 3. Cuotas IMSS patronales
    cuotas_imss = calcular_cuotas_imss(sbc, prima_riesgo, inp.anio)

    # 4. Infonavit (5% bimestral promediado mensual — ver nota del módulo)
    infonavit_mensual = redondear(sbc * ind.imss.infonavit * 0.5)

    # 5. Impuesto estatal sobre nómina
    impuesto_estatal = redondear(salario_mensual * tasa_estatal)

    # 6-7. Prorrateos de aguinaldo y prima vacacional
    aguinaldo_prorrateo = (
        redondear((15 * salario_diario) / 12) if inp.incluir_aguinaldo_mensual else 0.0
    )
    vacaciones_prorrateo = (
        redondear((dias_vacaciones(inp.antiguedad_anios) * 0.25 * salario_diario) / 12)
        if inp.incluir_vacaciones_mensual
        else 0.0
    )

    # 8. Prestaciones adicionales
    prestaciones_mensuales = sum(
        (p["monto"] / 12 if p.get("tipo") == "anual" else p["monto"])
        for p in inp.prestaciones_adicionales
    )

    # 9. ISR del empleado (para mostrar el neto)
    isr_empleado = calcular_isr_periodo(salario_mensual, inp.anio)["isr_final"]
    salario_neto = salario_mensual - isr_empleado

    # 10. Totales
    carga_patronal_mensual = (
        cuotas_imss["total"]
        + infonavit_mensual
        + impuesto_estatal
        + aguinaldo_prorrateo
        + vacaciones_prorrateo
        + prestaciones_mensuales
    )
    costo_total_mensual = salario_mensual + carga_patronal_mensual
    costo_total_anual = costo_total_mensual * 12

    # 11. Desglose concepto por concepto
    conceptos = [
        {
            "nombre": "Salario Base",
            "descripcion": "Salario bruto mensual del trabajador",
            "monto_mensual": salario_mensual,
            "monto_anual": salario_anual,
            "categoria": "salario",
        },
    ]
    if inp.incluir_aguinaldo_mensual:
        conceptos.append(
            {
                "nombre": "Aguinaldo Prorrateo",
                "descripcion": "15 días de aguinaldo divididos en 12 meses",
                "monto_mensual": aguinaldo_prorrateo,
                "monto_anual": aguinaldo_prorrateo * 12,
                "categoria": "salario",
            }
        )
    if inp.incluir_vacaciones_mensual:
        conceptos.append(
            {
                "nombre": "Prima Vacacional Prorrateo",
                "descripcion": "Prima vacacional (25%) dividida en 12 meses",
                "monto_mensual": vacaciones_prorrateo,
                "monto_anual": vacaciones_prorrateo * 12,
                "categoria": "salario",
            }
        )
    conceptos += [
        {
            "nombre": "Enfermedad y Maternidad",
            "descripcion": "Cuota patronal IMSS enfermedad y maternidad",
            "monto_mensual": cuotas_imss["enfermedad_maternidad"],
            "monto_anual": cuotas_imss["enfermedad_maternidad"] * 12,
            "categoria": "imss",
        },
        {
            "nombre": "Invalidez y Vida",
            "descripcion": "Cuota patronal IMSS invalidez y vida",
            "monto_mensual": cuotas_imss["invalidez_vida"],
            "monto_anual": cuotas_imss["invalidez_vida"] * 12,
            "categoria": "imss",
        },
        {
            "nombre": "Cesantía y Vejez",
            "descripcion": "Cuota patronal IMSS cesantía en edad avanzada y vejez",
            "monto_mensual": cuotas_imss["cesantia_vejez"],
            "monto_anual": cuotas_imss["cesantia_vejez"] * 12,
            "categoria": "imss",
        },
        {
            "nombre": "Guarderías",
            "descripcion": "Cuota patronal IMSS guarderías y prestaciones sociales",
            "monto_mensual": cuotas_imss["guarderias"],
            "monto_anual": cuotas_imss["guarderias"] * 12,
            "categoria": "imss",
        },
        {
            "nombre": "Riesgos de Trabajo",
            "descripcion": "Prima de riesgo de trabajo según clase",
            "monto_mensual": cuotas_imss["riesgos_trabajo"],
            "monto_anual": cuotas_imss["riesgos_trabajo"] * 12,
            "categoria": "imss",
        },
        {
            "nombre": "Infonavit",
            "descripcion": "Aportación Infonavit (5% bimestral, promediado mensual)",
            "monto_mensual": infonavit_mensual,
            "monto_anual": infonavit_mensual * 12,
            "categoria": "infonavit",
        },
        {
            "nombre": "Impuesto Estatal sobre Nómina",
            "descripcion": f"Impuesto estatal sobre nómina ({tasa_estatal * 100:.2f}%)",
            "monto_mensual": impuesto_estatal,
            "monto_anual": impuesto_estatal * 12,
            "categoria": "impuesto",
        },
    ]
    conceptos += [
        {
            "nombre": p["nombre"],
            "descripcion": "Prestación adicional",
            "monto_mensual": p["monto"] / 12 if p.get("tipo") == "anual" else p["monto"],
            "monto_anual": p["monto"] if p.get("tipo") == "anual" else p["monto"] * 12,
            "categoria": "prestacion",
        }
        for p in inp.prestaciones_adicionales
    ]

    return {
        "salario_diario": redondear(salario_diario),
        "salario_mensual": redondear(salario_mensual),
        "salario_anual": redondear(salario_anual),
        "sbc": redondear(sbc),
        "sbc_mensual": redondear(sbc_mensual),
        "cuotas_imss": cuotas_imss,
        "infonavit": redondear(infonavit_mensual),
        "impuesto_estatal": redondear(impuesto_estatal),
        "aguinaldo_prorrateo": redondear(aguinaldo_prorrateo),
        "vacaciones_prorrateo": redondear(vacaciones_prorrateo),
        "prestaciones_adicionales": redondear(prestaciones_mensuales),
        "isr_empleado": redondear(isr_empleado),
        "salario_neto": redondear(salario_neto),
        "carga_patronal_mensual": redondear(carga_patronal_mensual),
        "costo_total_mensual": redondear(costo_total_mensual),
        "costo_total_anual": redondear(costo_total_anual),
        "prima_riesgo_aplicada": prima_riesgo,
        "tasa_estatal_aplicada": tasa_estatal,
        "desglose": {
            "conceptos": conceptos,
            "total_salarios": salario_mensual + aguinaldo_prorrateo + vacaciones_prorrateo,
            "total_carga_patronal": carga_patronal_mensual,
            "costo_total": costo_total_mensual,
        },
    }

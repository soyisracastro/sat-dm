"""Calculadora de finiquito (LFT Arts. 76-80, 87; LISR Arts. 93, 96).

Port de ``calculadora-finiquito/calculations.ts`` (paridad centavo a centavo).
Conceptos: salario devengado del mes + aguinaldo proporcional (exento 30 UMA) +
vacaciones proporcionales + prima vacacional (exenta 15 UMA); ISR Art. 96 sobre
el total gravado.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from .comunes import (
    DIAS_AGUINALDO_MINIMO,
    DIAS_ANIO,
    EXENCION_AGUINALDO_UMA,
    EXENCION_PRIMA_VACACIONAL_UMA,
    PRIMA_VACACIONAL_MINIMA,
    dias_vacaciones,
)
from .indicadores import get_indicadores
from .isr import calcular_isr_periodo


@dataclass(frozen=True)
class FiniquitoInput:
    salario: float
    tipo_salario: str  # "diario" | "mensual"
    fecha_ingreso: date
    fecha_baja: date
    dias_aguinaldo: int = DIAS_AGUINALDO_MINIMO
    prima_vacacional: float = PRIMA_VACACIONAL_MINIMA
    anio: int = 2026


def calcular_antiguedad(fecha_ingreso: date, fecha_baja: date) -> dict:
    """Antigüedad en años/meses/días exactos (paridad con la web).

    ``anios_completos`` (para la tabla de vacaciones): mínimo 1; suma un año si
    la fracción es de 6 meses o más.
    """
    if fecha_baja <= fecha_ingreso:
        return {
            "anios": 0,
            "meses": 0,
            "dias": 0,
            "anios_completos": 0,
            "total_dias": 0,
            "texto": "0 años, 0 meses, 0 días",
        }

    total_dias = (fecha_baja - fecha_ingreso).days

    anios = fecha_baja.year - fecha_ingreso.year
    meses = fecha_baja.month - fecha_ingreso.month
    dias = fecha_baja.day - fecha_ingreso.day

    if dias < 0:
        meses -= 1
        # días del mes anterior al de la baja
        mes_anterior = fecha_baja.month - 1 or 12
        anio_mes_anterior = fecha_baja.year if fecha_baja.month > 1 else fecha_baja.year - 1
        dias += calendar.monthrange(anio_mes_anterior, mes_anterior)[1]

    if meses < 0:
        anios -= 1
        meses += 12

    anios_completos = max(1, anios + (1 if meses >= 6 else 0))

    texto = (
        f"{anios} año{'s' if anios != 1 else ''}, "
        f"{meses} mes{'es' if meses != 1 else ''}, "
        f"{dias} día{'s' if dias != 1 else ''}"
    )

    return {
        "anios": anios,
        "meses": meses,
        "dias": dias,
        "anios_completos": anios_completos,
        "total_dias": total_dias,
        "texto": texto,
    }


def _dias_trabajados_anio(fecha_ingreso: date, fecha_baja: date) -> int:
    """Días trabajados en el año de la baja, incluyendo el día de la baja."""
    inicio_anio = date(fecha_baja.year, 1, 1)
    inicio = fecha_ingreso if fecha_ingreso > inicio_anio else inicio_anio
    return (fecha_baja - inicio).days + 1


def _resultado_vacio(inp: FiniquitoInput, exencion_aguinaldo: float, exencion_prima: float) -> dict:
    return {
        "salario_diario": 0.0,
        "salario_mensual": 0.0,
        "antiguedad": {
            "anios": 0, "meses": 0, "dias": 0,
            "anios_completos": 1, "total_dias": 0,
            "texto": "0 años, 0 meses, 0 días",
        },
        "salario_devengado": {"dias": 0, "monto_por_dia": 0.0, "monto": 0.0},
        "aguinaldo_proporcional": {
            "dias_correspondientes": 0.0,
            "dias_aguinaldo_anual": inp.dias_aguinaldo,
            "dias_trabajados_anio": 0,
            "monto": 0.0,
            "exencion": exencion_aguinaldo,
            "gravado": 0.0,
            "exento": 0.0,
        },
        "vacaciones_proporcionales": {
            "dias_vacaciones_anuales": 12,
            "dias_correspondientes": 0.0,
            "dias_trabajados_anio": 0,
            "monto_por_dia": 0.0,
            "monto": 0.0,
        },
        "prima_vacacional": {
            "porcentaje": inp.prima_vacacional,
            "base_vacaciones": 0.0,
            "monto": 0.0,
            "exencion": exencion_prima,
            "gravado": 0.0,
            "exento": 0.0,
        },
        "fiscal": {
            "gravado_salario": 0.0,
            "gravado_vacaciones": 0.0,
            "gravado_aguinaldo": 0.0,
            "exento_aguinaldo": 0.0,
            "gravado_prima_vacacional": 0.0,
            "exento_prima_vacacional": 0.0,
            "total_gravado": 0.0,
            "total_exento": 0.0,
            "isr_retenido": 0.0,
        },
        "subtotal_bruto": 0.0,
        "total_isr": 0.0,
        "total_neto": 0.0,
    }


def calcular_finiquito(inp: FiniquitoInput) -> dict:
    ind = get_indicadores(inp.anio)
    exencion_aguinaldo = ind.uma_diaria * EXENCION_AGUINALDO_UMA
    exencion_prima = ind.uma_diaria * EXENCION_PRIMA_VACACIONAL_UMA

    if inp.salario <= 0 or inp.fecha_baja <= inp.fecha_ingreso:
        return _resultado_vacio(inp, exencion_aguinaldo, exencion_prima)

    salario_diario = inp.salario / 30 if inp.tipo_salario == "mensual" else inp.salario
    salario_mensual = inp.salario if inp.tipo_salario == "mensual" else inp.salario * 30

    antiguedad = calcular_antiguedad(inp.fecha_ingreso, inp.fecha_baja)
    dias_vac_anuales = dias_vacaciones(antiguedad["anios_completos"])
    dias_trabajados = _dias_trabajados_anio(inp.fecha_ingreso, inp.fecha_baja)

    # 1. Salario devengado (días del mes hasta la baja)
    dias_devengados = inp.fecha_baja.day
    salario_devengado = {
        "dias": dias_devengados,
        "monto_por_dia": salario_diario,
        "monto": dias_devengados * salario_diario,
    }

    # 2. Aguinaldo proporcional (exento hasta 30 UMA)
    dias_corresp_aguinaldo = (dias_trabajados / DIAS_ANIO) * inp.dias_aguinaldo
    monto_aguinaldo = dias_corresp_aguinaldo * salario_diario
    aguinaldo = {
        "dias_correspondientes": dias_corresp_aguinaldo,
        "dias_aguinaldo_anual": inp.dias_aguinaldo,
        "dias_trabajados_anio": dias_trabajados,
        "monto": monto_aguinaldo,
        "exencion": exencion_aguinaldo,
        "gravado": max(0.0, monto_aguinaldo - exencion_aguinaldo),
        "exento": min(monto_aguinaldo, exencion_aguinaldo),
    }

    # 3. Vacaciones proporcionales (100% gravables)
    dias_corresp_vac = (dias_trabajados / DIAS_ANIO) * dias_vac_anuales
    monto_vacaciones = dias_corresp_vac * salario_diario
    vacaciones = {
        "dias_vacaciones_anuales": dias_vac_anuales,
        "dias_correspondientes": dias_corresp_vac,
        "dias_trabajados_anio": dias_trabajados,
        "monto_por_dia": salario_diario,
        "monto": monto_vacaciones,
    }

    # 4. Prima vacacional (exenta hasta 15 UMA)
    monto_prima = monto_vacaciones * inp.prima_vacacional
    prima = {
        "porcentaje": inp.prima_vacacional,
        "base_vacaciones": monto_vacaciones,
        "monto": monto_prima,
        "exencion": exencion_prima,
        "gravado": max(0.0, monto_prima - exencion_prima),
        "exento": min(monto_prima, exencion_prima),
    }

    # 5. ISR (Art. 96 sobre el total gravado)
    total_gravado = (
        salario_devengado["monto"] + monto_vacaciones + aguinaldo["gravado"] + prima["gravado"]
    )
    total_exento = aguinaldo["exento"] + prima["exento"]
    isr = calcular_isr_periodo(total_gravado, inp.anio)

    fiscal = {
        "gravado_salario": salario_devengado["monto"],
        "gravado_vacaciones": monto_vacaciones,
        "gravado_aguinaldo": aguinaldo["gravado"],
        "exento_aguinaldo": aguinaldo["exento"],
        "gravado_prima_vacacional": prima["gravado"],
        "exento_prima_vacacional": prima["exento"],
        "total_gravado": total_gravado,
        "total_exento": total_exento,
        "isr_retenido": isr["isr_final"],
    }

    subtotal_bruto = (
        salario_devengado["monto"] + monto_aguinaldo + monto_vacaciones + monto_prima
    )

    return {
        "salario_diario": salario_diario,
        "salario_mensual": salario_mensual,
        "antiguedad": antiguedad,
        "salario_devengado": salario_devengado,
        "aguinaldo_proporcional": aguinaldo,
        "vacaciones_proporcionales": vacaciones,
        "prima_vacacional": prima,
        "fiscal": fiscal,
        "subtotal_bruto": subtotal_bruto,
        "total_isr": fiscal["isr_retenido"],
        "total_neto": subtotal_bruto - fiscal["isr_retenido"],
    }

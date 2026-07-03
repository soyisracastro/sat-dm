"""Calculadora de Salario Base de Cotización (SBC) — factor de integración.

Port de ``calculadora-sbc/calculations.ts``. Integra aguinaldo (Art. 87 LFT),
vacaciones según antigüedad (reforma 2023) y prima vacacional (Art. 80 LFT);
tope de 25 UMA (Art. 28 LSS).

Nota de paridad: esta calculadora convierte mensual↔diario con factor 30 (no
30.4), igual que la web.
"""

from __future__ import annotations

from dataclasses import dataclass

from .comunes import (
    DIAS_AGUINALDO_MINIMO,
    DIAS_ANIO,
    PRIMA_VACACIONAL_MINIMA,
    dias_vacaciones,
)
from .indicadores import get_indicadores


@dataclass(frozen=True)
class SBCInput:
    salario: float
    tipo_salario: str  # "diario" | "mensual"
    antiguedad_anios: int
    dias_aguinaldo: int = DIAS_AGUINALDO_MINIMO
    prima_vacacional: float = PRIMA_VACACIONAL_MINIMA
    anio: int = 2026


def calcular_factor_integracion(
    dias_aguinaldo: int, dias_vac: int, prima_vacacional: float
) -> float:
    """Factor = 1 + aguinaldo/365 + (vacaciones × prima)/365."""
    return 1 + dias_aguinaldo / DIAS_ANIO + (dias_vac * prima_vacacional) / DIAS_ANIO


def calcular_sbc(inp: SBCInput) -> dict:
    salario_diario = inp.salario / 30 if inp.tipo_salario == "mensual" else inp.salario

    dias_vac = dias_vacaciones(inp.antiguedad_anios)
    factor = calcular_factor_integracion(inp.dias_aguinaldo, dias_vac, inp.prima_vacacional)

    sbc_diario = salario_diario * factor

    tope_sbc = get_indicadores(inp.anio).tope_sbc_diario
    excede_tope = sbc_diario > tope_sbc
    if excede_tope:
        sbc_diario = tope_sbc

    integracion_aguinaldo = (salario_diario * inp.dias_aguinaldo) / DIAS_ANIO
    integracion_prima = (salario_diario * dias_vac * inp.prima_vacacional) / DIAS_ANIO

    return {
        "salario_diario_base": salario_diario,
        "factor_integracion": factor,
        "sbc_diario": sbc_diario,
        "sbc_mensual": sbc_diario * 30,
        "tope_sbc": tope_sbc,
        "excede_tope": excede_tope,
        "desglose": {
            "salario_base": {"dias": DIAS_ANIO, "integracion_diaria": salario_diario},
            "aguinaldo": {"dias": inp.dias_aguinaldo, "integracion_diaria": integracion_aguinaldo},
            "prima_vacacional": {
                "dias_vacaciones": dias_vac,
                "porcentaje": inp.prima_vacacional * 100,
                "integracion_diaria": integracion_prima,
            },
            "total_integrado": salario_diario + integracion_aguinaldo + integracion_prima,
        },
    }

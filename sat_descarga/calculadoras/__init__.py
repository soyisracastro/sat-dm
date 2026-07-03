"""Calculadoras fiscales y laborales (México).

Cálculo puro (sin FastAPI/Pydantic — importable con las dependencias core).
Los indicadores por año (UMA, SMG, tarifas ISR, SPE, cuotas IMSS) viven en
``indicadores.py``; agregar un año nuevo no toca los módulos de cálculo.

Uso:
    from sat_descarga.calculadoras import (
        AguinaldoInput, calcular_aguinaldo,
        SBCInput, calcular_sbc,
        FiniquitoInput, calcular_finiquito,
        LiquidacionInput, calcular_liquidacion,
        CargaPatronalInput, calcular_carga_patronal,
        EmpresaPTU, TrabajadorPTU, calcular_ptu,
        calcular_isr_periodo,
    )
"""

from .aguinaldo import AguinaldoInput, calcular_aguinaldo
from .carga_patronal import CargaPatronalInput, calcular_carga_patronal
from .comunes import (
    DIAS_ANIO,
    DIAS_MES_PROMEDIO,
    DESCRIPCION_CLASES_RIESGO,
    ESTADOS_ISN,
    PERIODICIDADES,
    PRIMAS_RIESGO,
    TIPOS_TERMINACION,
    dias_vacaciones,
    redondear,
)
from .finiquito import FiniquitoInput, calcular_finiquito
from .indicadores import INDICADORES, UMA_SMG_HISTORICO, IndicadoresAnio, get_indicadores
from .isr import calcular_isr_periodo, calcular_spe, isr_diferencial, tasa_efectiva_art174
from .liquidacion import LiquidacionInput, calcular_liquidacion
from .ptu import EmpresaPTU, TrabajadorPTU, calcular_ptu
from .sbc import SBCInput, calcular_sbc

__all__ = [
    "AguinaldoInput",
    "calcular_aguinaldo",
    "CargaPatronalInput",
    "calcular_carga_patronal",
    "FiniquitoInput",
    "calcular_finiquito",
    "LiquidacionInput",
    "calcular_liquidacion",
    "EmpresaPTU",
    "TrabajadorPTU",
    "calcular_ptu",
    "SBCInput",
    "calcular_sbc",
    "calcular_isr_periodo",
    "calcular_spe",
    "isr_diferencial",
    "tasa_efectiva_art174",
    "INDICADORES",
    "UMA_SMG_HISTORICO",
    "IndicadoresAnio",
    "get_indicadores",
    "DIAS_ANIO",
    "DIAS_MES_PROMEDIO",
    "PERIODICIDADES",
    "PRIMAS_RIESGO",
    "DESCRIPCION_CLASES_RIESGO",
    "ESTADOS_ISN",
    "TIPOS_TERMINACION",
    "dias_vacaciones",
    "redondear",
]

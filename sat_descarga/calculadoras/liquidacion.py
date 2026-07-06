"""Calculadora de liquidación (finiquito + indemnización).

Port de ``calculadora-liquidacion/calculations.ts`` (paridad centavo a centavo).
Indemnización según tipo de terminación: 3 meses (Art. 48 LFT), 20 días por año
(Art. 50 LFT), prima de antigüedad (Art. 162 LFT, tope 2×SMG); exención de 90
UMA por año de servicio (Art. 93 fr. XIII LISR) e ISR con tasa efectiva
(Art. 95 LISR).

Nota de paridad: el finiquito interno de esta calculadora difiere del módulo
``finiquito.py`` en el conteo de días trabajados del año (aquí NO suma el día
de la baja) y en la antigüedad (aquí no fuerza mínimo 1 año y el corte es
"> 6 meses" en vez de ">= 6"). Se porta tal cual la web; unificar después
requiere cambiar ambos lados.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date

from .comunes import (
    ANIOS_MINIMOS_RENUNCIA_PRIMA,
    DIAS_AGUINALDO_MINIMO,
    DIAS_ANIO,
    DIAS_POR_ANIO_ART50,
    EXENCION_AGUINALDO_UMA,
    EXENCION_PRIMA_VACACIONAL_UMA,
    EXENCION_SEPARACION_UMA_POR_ANIO,
    MESES_INDEMNIZACION_CONSTITUCIONAL,
    PRIMA_ANTIGUEDAD_DIAS_POR_ANIO,
    PRIMA_VACACIONAL_MINIMA,
    TIPOS_TERMINACION,
    TOPE_PRIMA_ANTIGUEDAD_SMG,
    aplica_prima_antiguedad,
    aplica_veinte_dias,
    dias_vacaciones,
)
from .indicadores import get_indicadores
from .isr import calcular_isr_periodo


@dataclass(frozen=True)
class LiquidacionInput:
    salario: float
    tipo_salario: str  # "diario" | "mensual"
    fecha_ingreso: date
    fecha_baja: date
    tipo_terminacion: str  # clave de TIPOS_TERMINACION
    es_zona_fronteriza: bool = False
    dias_aguinaldo: int = DIAS_AGUINALDO_MINIMO
    prima_vacacional: float = PRIMA_VACACIONAL_MINIMA
    ultimo_sueldo_mensual: float | None = None
    anio: int = 2026


def calcular_antiguedad(fecha_ingreso: date, fecha_baja: date) -> dict:
    """Antigüedad para liquidación: fracción > 6 meses cuenta como año completo."""
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
        mes_anterior = fecha_baja.month - 1 or 12
        anio_mes_anterior = fecha_baja.year if fecha_baja.month > 1 else fecha_baja.year - 1
        dias += calendar.monthrange(anio_mes_anterior, mes_anterior)[1]

    if meses < 0:
        anios -= 1
        meses += 12

    anios_completos = anios
    if meses > 6 or (meses == 6 and dias > 0):
        anios_completos += 1

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


def calcular_sdi(
    salario_diario: float,
    antiguedad_anios: int,
    dias_aguinaldo: int = DIAS_AGUINALDO_MINIMO,
    prima_vacacional: float = PRIMA_VACACIONAL_MINIMA,
) -> dict:
    """Salario diario integrado para la indemnización."""
    dias_vac = dias_vacaciones(antiguedad_anios)
    factor = 1 + dias_aguinaldo / DIAS_ANIO + (dias_vac * prima_vacacional) / DIAS_ANIO
    return {"sdi": salario_diario * factor, "factor": factor}


def _calcular_finiquito_interno(
    salario_diario: float,
    fecha_ingreso: date,
    fecha_baja: date,
    dias_aguinaldo: int,
    prima_vacacional: float,
    exencion_aguinaldo: float,
    exencion_prima: float,
) -> dict:
    antiguedad = calcular_antiguedad(fecha_ingreso, fecha_baja)
    dias_vac_anuales = dias_vacaciones(antiguedad["anios_completos"] or 1)

    inicio_anio = date(fecha_baja.year, 1, 1)
    inicio = fecha_ingreso if fecha_ingreso > inicio_anio else inicio_anio
    dias_trabajados_anio = (fecha_baja - inicio).days  # sin +1 (paridad web)

    dias_devengados = fecha_baja.day
    salario_devengado = {
        "dias": dias_devengados,
        "monto_por_dia": salario_diario,
        "monto": dias_devengados * salario_diario,
    }

    dias_corresp_aguinaldo = (dias_trabajados_anio / DIAS_ANIO) * dias_aguinaldo
    monto_aguinaldo = dias_corresp_aguinaldo * salario_diario
    aguinaldo = {
        "dias_correspondientes": dias_corresp_aguinaldo,
        "dias_aguinaldo_anual": dias_aguinaldo,
        "monto": monto_aguinaldo,
        "exencion": exencion_aguinaldo,
        "gravado": max(0.0, monto_aguinaldo - exencion_aguinaldo),
        "exento": min(monto_aguinaldo, exencion_aguinaldo),
    }

    dias_corresp_vac = (dias_trabajados_anio / DIAS_ANIO) * dias_vac_anuales
    monto_vacaciones = dias_corresp_vac * salario_diario
    vacaciones = {
        "dias_vacaciones_anuales": dias_vac_anuales,
        "dias_correspondientes": dias_corresp_vac,
        "monto_por_dia": salario_diario,
        "monto": monto_vacaciones,
    }

    monto_prima = monto_vacaciones * prima_vacacional
    prima = {
        "porcentaje": prima_vacacional,
        "monto": monto_prima,
        "exencion": exencion_prima,
        "gravado": max(0.0, monto_prima - exencion_prima),
        "exento": min(monto_prima, exencion_prima),
    }

    subtotal = salario_devengado["monto"] + monto_aguinaldo + monto_vacaciones + monto_prima
    total_gravado = (
        salario_devengado["monto"] + monto_vacaciones + aguinaldo["gravado"] + prima["gravado"]
    )
    total_exento = aguinaldo["exento"] + prima["exento"]

    return {
        "salario_devengado": salario_devengado,
        "aguinaldo_proporcional": aguinaldo,
        "vacaciones_proporcionales": vacaciones,
        "prima_vacacional": prima,
        "subtotal": subtotal,
        "total_gravado": total_gravado,
        "total_exento": total_exento,
    }


def _calcular_prima_antiguedad(
    salario_diario: float,
    anios_servicio: int,
    es_zona_fronteriza: bool,
    tipo_terminacion: str,
    smg_general: float,
    smg_frontera: float,
) -> dict:
    aplica = aplica_prima_antiguedad(tipo_terminacion, anios_servicio)
    smg = smg_frontera if es_zona_fronteriza else smg_general
    salario_tope = smg * TOPE_PRIMA_ANTIGUEDAD_SMG
    salario_aplicable = min(salario_diario, salario_tope)

    if not aplica:
        es_renuncia = tipo_terminacion == "RENUNCIA_VOLUNTARIA"
        return {
            "monto": 0.0,
            "aplica": False,
            "salario_tope": salario_tope,
            "salario_aplicable": 0.0,
            "fundamento_legal": "Artículo 162 LFT",
            "razon_no_aplica": (
                f"Renuncia voluntaria con menos de {ANIOS_MINIMOS_RENUNCIA_PRIMA} años de antigüedad"
                if es_renuncia
                else "No aplica para este tipo de terminación"
            ),
        }

    return {
        "monto": salario_aplicable * PRIMA_ANTIGUEDAD_DIAS_POR_ANIO * anios_servicio,
        "aplica": True,
        "salario_tope": salario_tope,
        "salario_aplicable": salario_aplicable,
        "fundamento_legal": "Artículo 162 LFT",
        "razon_no_aplica": None,
    }


def _calcular_indemnizacion(
    sdi: float,
    salario_diario: float,
    antiguedad: dict,
    tipo_terminacion: str,
    es_zona_fronteriza: bool,
    exencion_separacion_por_anio: float,
    smg_general: float,
    smg_frontera: float,
) -> dict | None:
    info = TIPOS_TERMINACION[tipo_terminacion]
    aplica_tres_meses = info["tres_meses"]
    aplica_veinte = aplica_veinte_dias(tipo_terminacion)
    aplica_prima = aplica_prima_antiguedad(tipo_terminacion, antiguedad["anios_completos"])

    if tipo_terminacion == "RENUNCIA_VOLUNTARIA" and not aplica_prima:
        return None

    # 1. Tres meses constitucionales (Art. 48)
    dias_tres_meses = MESES_INDEMNIZACION_CONSTITUCIONAL * 30  # 90 días
    monto_tres_meses = sdi * dias_tres_meses if aplica_tres_meses else 0.0
    tres_meses = {
        "dias_sdi": dias_tres_meses,
        "salario_diario_integrado": sdi,
        "monto": monto_tres_meses,
        "aplica": aplica_tres_meses,
        "fundamento_legal": "Artículo 48 LFT",
    }

    # 2. Veinte días por año (Art. 50)
    monto_veinte = (
        sdi * DIAS_POR_ANIO_ART50 * antiguedad["anios_completos"] if aplica_veinte else 0.0
    )
    veinte_dias = {
        "anios_completos": antiguedad["anios_completos"],
        "dias_por_anio": DIAS_POR_ANIO_ART50,
        "salario_diario_integrado": sdi,
        "monto": monto_veinte,
        "aplica": aplica_veinte,
        "fundamento_legal": "Artículo 50 fracción II LFT",
        "razon_no_aplica": (
            None
            if aplica_veinte
            else "Solo aplica cuando el trabajador demanda reinstalación y el patrón se "
            "niega, o en rescisión Art. 51 o terminación colectiva"
        ),
    }

    # 3. Prima de antigüedad (Art. 162)
    prima_res = _calcular_prima_antiguedad(
        salario_diario,
        antiguedad["anios_completos"],
        es_zona_fronteriza,
        tipo_terminacion,
        smg_general,
        smg_frontera,
    )
    prima_antiguedad = {
        "anios_servicio": antiguedad["anios_completos"],
        "dias_por_anio": PRIMA_ANTIGUEDAD_DIAS_POR_ANIO,
        "salario_diario": salario_diario,
        **prima_res,
    }

    subtotal = monto_tres_meses + monto_veinte + prima_res["monto"]
    exencion = exencion_separacion_por_anio * antiguedad["anios_completos"]

    return {
        "tres_meses_constitucional": tres_meses,
        "veinte_dias_por_anio": veinte_dias,
        "prima_antiguedad": prima_antiguedad,
        "subtotal": subtotal,
        "exencion": exencion,
        "gravado": max(0.0, subtotal - exencion),
        "exento": min(subtotal, exencion),
    }


def _calcular_isr_liquidacion(
    finiquito: dict,
    indemnizacion: dict | None,
    antiguedad_anios: int,
    ultimo_sueldo_mensual: float,
    anio: int,
    exencion_separacion_por_anio: float,
) -> dict:
    # 1. ISR del finiquito (Art. 96 estándar)
    isr_finiquito = calcular_isr_periodo(finiquito["total_gravado"], anio)

    # 2. ISR de la indemnización (Art. 95: tasa efectiva del último sueldo)
    indemnizacion_fiscal = {
        "total_bruto": 0.0,
        "exencion_90_uma": 0.0,
        "base_gravable": 0.0,
        "ultimo_sueldo_mensual": ultimo_sueldo_mensual,
        "isr_ultimo_sueldo": 0.0,
        "tasa_efectiva": 0.0,
        "usa_tasa_efectiva": False,
        "isr": 0.0,
    }

    if indemnizacion and indemnizacion["subtotal"] > 0:
        exencion = exencion_separacion_por_anio * antiguedad_anios
        gravado = max(0.0, indemnizacion["subtotal"] - exencion)

        isr_ultimo_sueldo = calcular_isr_periodo(ultimo_sueldo_mensual, anio)
        tasa_efectiva = (
            (isr_ultimo_sueldo["isr_final"] / ultimo_sueldo_mensual) * 100
            if ultimo_sueldo_mensual > 0
            else 0.0
        )

        usa_tasa_efectiva = indemnizacion["subtotal"] >= ultimo_sueldo_mensual

        isr_indemnizacion = 0.0
        if gravado > 0:
            if usa_tasa_efectiva:
                isr_indemnizacion = gravado * (tasa_efectiva / 100)
            else:
                # Tarifa directa, sin SPE (pagos por separación no llevan subsidio)
                isr_indemnizacion = calcular_isr_periodo(gravado, anio, es_asimilado=True)["isr_final"]

        indemnizacion_fiscal = {
            "total_bruto": indemnizacion["subtotal"],
            "exencion_90_uma": exencion,
            "base_gravable": gravado,
            "ultimo_sueldo_mensual": ultimo_sueldo_mensual,
            "isr_ultimo_sueldo": isr_ultimo_sueldo["isr_final"],
            "tasa_efectiva": tasa_efectiva,
            "usa_tasa_efectiva": usa_tasa_efectiva,
            "isr": isr_indemnizacion,
        }

    total_gravado = finiquito["total_gravado"] + indemnizacion_fiscal["base_gravable"]
    total_exento = finiquito["total_exento"] + (indemnizacion["exento"] if indemnizacion else 0.0)
    total_isr = isr_finiquito["isr_final"] + indemnizacion_fiscal["isr"]

    return {
        "finiquito": {
            "base_gravable": finiquito["total_gravado"],
            "isr": isr_finiquito["isr_final"],
        },
        "indemnizacion": indemnizacion_fiscal,
        "total_gravado": total_gravado,
        "total_exento": total_exento,
        "total_isr": total_isr,
    }


def calcular_liquidacion(inp: LiquidacionInput) -> dict:
    ind = get_indicadores(inp.anio)
    exencion_aguinaldo = ind.uma_diaria * EXENCION_AGUINALDO_UMA
    exencion_prima = ind.uma_diaria * EXENCION_PRIMA_VACACIONAL_UMA
    exencion_separacion = ind.uma_diaria * EXENCION_SEPARACION_UMA_POR_ANIO

    if inp.salario <= 0 or inp.fecha_baja <= inp.fecha_ingreso:
        raise ValueError("Datos inválidos: salario debe ser > 0 y fecha de baja posterior al ingreso.")

    salario_diario = inp.salario / 30 if inp.tipo_salario == "mensual" else inp.salario
    salario_mensual = inp.salario if inp.tipo_salario == "mensual" else inp.salario * 30
    ultimo_sueldo_mensual = inp.ultimo_sueldo_mensual or salario_mensual

    antiguedad = calcular_antiguedad(inp.fecha_ingreso, inp.fecha_baja)

    sdi_res = calcular_sdi(
        salario_diario,
        antiguedad["anios_completos"] or 1,
        inp.dias_aguinaldo,
        inp.prima_vacacional,
    )

    finiquito = _calcular_finiquito_interno(
        salario_diario,
        inp.fecha_ingreso,
        inp.fecha_baja,
        inp.dias_aguinaldo,
        inp.prima_vacacional,
        exencion_aguinaldo,
        exencion_prima,
    )

    indemnizacion = _calcular_indemnizacion(
        sdi_res["sdi"],
        salario_diario,
        antiguedad,
        inp.tipo_terminacion,
        inp.es_zona_fronteriza,
        exencion_separacion,
        ind.smg_general,
        ind.smg_frontera,
    )

    fiscal = _calcular_isr_liquidacion(
        finiquito,
        indemnizacion,
        antiguedad["anios_completos"],
        ultimo_sueldo_mensual,
        inp.anio,
        exencion_separacion,
    )

    total_bruto = finiquito["subtotal"] + (indemnizacion["subtotal"] if indemnizacion else 0.0)
    total_isr = fiscal["total_isr"]

    info = TIPOS_TERMINACION[inp.tipo_terminacion]

    return {
        "salario_diario": salario_diario,
        "salario_mensual": salario_mensual,
        "salario_diario_integrado": sdi_res["sdi"],
        "factor_integracion": sdi_res["factor"],
        "antiguedad": antiguedad,
        "finiquito": finiquito,
        "indemnizacion": indemnizacion,
        "fiscal": fiscal,
        "total_bruto": total_bruto,
        "total_isr": total_isr,
        "total_neto": total_bruto - total_isr,
        "aplica_indemnizacion": indemnizacion is not None,
        "aplica_tres_meses": info["tres_meses"],
        "aplica_veinte_dias": aplica_veinte_dias(inp.tipo_terminacion),
        "aplica_prima_antiguedad": aplica_prima_antiguedad(
            inp.tipo_terminacion, antiguedad["anios_completos"]
        ),
        "tipo_terminacion": inp.tipo_terminacion,
    }

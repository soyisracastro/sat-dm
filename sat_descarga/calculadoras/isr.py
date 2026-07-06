"""ISR de sueldos y salarios (Art. 96 LISR) + subsidio para el empleo.

Módulo compartido por todas las calculadoras. Port de
``todoconta-apps/apps/web/src/lib/shared/isr/`` con soporte multi-año vía
``indicadores.py``. Los resultados son dicts JSON-serializables que replican la
interfaz TS (``ISRResult``) en snake_case.
"""

from __future__ import annotations

from .comunes import (
    DIAS_ANIO,
    DIAS_MES_PROMEDIO,
    DIAS_PERIODICIDAD,
    FACTORES_PERIODICIDAD,
)
from .indicadores import TramoISR, get_indicadores


def tarifa_por_periodicidad(anio: int, periodicidad: str) -> tuple[TramoISR, ...]:
    """Escala la tarifa mensual del Anexo 8 a la periodicidad dada.

    Límites y cuota fija se multiplican por el factor (días/30.4); los
    porcentajes no cambian.
    """
    ind = get_indicadores(anio)
    if ind.tarifa_isr_mensual is None:
        raise ValueError(f"Tarifa ISR mensual {anio} no disponible en indicadores.")
    factor = FACTORES_PERIODICIDAD[periodicidad]
    return tuple(
        TramoISR(
            limite_inferior=t.limite_inferior * factor,
            limite_superior=t.limite_superior * factor if t.limite_superior is not None else None,
            cuota_fija=t.cuota_fija * factor,
            porcentaje_excedente=t.porcentaje_excedente,
        )
        for t in ind.tarifa_isr_mensual
    )


def _buscar_tramo(ingreso: float, tarifas: tuple[TramoISR, ...]) -> TramoISR | None:
    """Tramo aplicable por rangos [inferior, superior] (paridad con la web)."""
    if ingreso <= 0:
        return None
    for tramo in tarifas:
        if tramo.limite_superior is None:
            if ingreso >= tramo.limite_inferior:
                return tramo
        elif tramo.limite_inferior <= ingreso <= tramo.limite_superior:
            return tramo
    return None


def calcular_spe(
    ingreso_gravado: float,
    anio: int = 2026,
    mes: int = 2,
    periodicidad: str = "mensual",
) -> float:
    """Subsidio para el empleo del período (0 si no aplica).

    - Esquema "uma" (2025+): monto fijo mensual escalado por periodicidad, solo
      si el ingreso no excede el tope (también escalado).
    - Esquema "tabla" (hasta 2024): lookup con el ingreso mensualizado y monto
      escalado por periodicidad.
    """
    if ingreso_gravado <= 0:
        return 0.0
    spe = get_indicadores(anio).spe
    if spe is None:
        return 0.0
    factor = FACTORES_PERIODICIDAD[periodicidad]

    if spe.esquema == "uma":
        if ingreso_gravado > spe.limite_ingresos_mensual * factor:
            return 0.0
        monto = spe.monto_mensual_enero if mes == 1 else spe.monto_mensual_resto
        return monto * factor

    ingreso_mensual = ingreso_gravado / factor
    for rango in spe.tabla:
        if rango.limite_inferior <= ingreso_mensual <= rango.limite_superior:
            return rango.subsidio_mensual * factor
    return 0.0


def validar_salario_minimo(
    ingreso_gravado: float,
    anio: int = 2026,
    periodicidad: str = "mensual",
    es_zona_fronteriza: bool = False,
    contexto: str | None = None,
) -> None:
    """Rechaza (``ValueError``) un salario por debajo del mínimo del período.

    Pagar por debajo del salario mínimo es ilegal (Art. 90 LFT) y quien percibe
    exactamente el mínimo no es sujeto de retención (Art. 96 último párrafo
    LISR), así que un "salario" menor al SMG no es base válida de cálculo. El
    umbral depende de la zona: general o Zona Libre de la Frontera Norte
    (ZLFN), cuyo mínimo es mayor.

    ``contexto`` cierra el mensaje según la calculadora (default: retención de
    ISR). Aplica SOLO a calculadoras cuyo input es un salario real (ISR de
    sueldos, SBC); NO se usa en las bases internas de aguinaldo/finiquito/PTU
    (ahí el gravado puede ser legítimamente menor) ni en asimilados a salarios
    (no son salario según la LFT y el mínimo no les aplica).
    """
    ind = get_indicadores(anio)
    smg_diario = ind.smg_frontera if es_zona_fronteriza else ind.smg_general
    dias = DIAS_PERIODICIDAD[periodicidad]
    umbral = smg_diario * dias
    if ingreso_gravado < umbral:
        zona = (
            "de la Zona Libre de la Frontera Norte" if es_zona_fronteriza else "general"
        )
        equivalencia = (
            f" (${umbral:,.2f} = ${smg_diario:,.2f} diarios × {dias:g} días)"
            if dias != 1
            else f" (${smg_diario:,.2f} diarios)"
        )
        cierre = contexto or (
            "No procede calcular retención de ISR sobre un salario por debajo del "
            "mínimo legal (Art. 90 LFT; Art. 96 último párrafo LISR)."
        )
        raise ValueError(
            f"El ingreso del período (${ingreso_gravado:,.2f}) es menor al salario "
            f"mínimo {zona}{equivalencia}. {cierre}"
        )


def _resultado_vacio(periodicidad: str) -> dict:
    return {
        "ingreso_bruto": 0.0,
        "base_gravable": 0.0,
        "isr_bruto": 0.0,
        "subsidio_aplicado": 0.0,
        "isr_final": 0.0,
        "tasa_efectiva": 0.0,
        "ingreso_neto": 0.0,
        "periodicidad": periodicidad,
        "desglose": {
            "limite_inferior": 0.0,
            "excedente_limite_inferior": 0.0,
            "tasa_marginal": 0.0,
            "impuesto_marginal": 0.0,
            "cuota_fija": 0.0,
            "isr_antes_subsidio": 0.0,
            "subsidio": 0.0,
            "isr_final": 0.0,
            "rango_tarifa": {
                "limite_inferior": 0.0,
                "limite_superior": None,
                "cuota_fija": 0.0,
                "porcentaje_sobre_excedente": 0.0,
            },
        },
    }


def calcular_isr_periodo(
    ingreso_gravado: float,
    anio: int = 2026,
    periodicidad: str = "mensual",
    es_asimilado: bool = False,
    mes: int = 2,
) -> dict:
    """ISR del período (Art. 96 LISR) con subsidio para el empleo.

    1. Excedente = ingreso − límite inferior del tramo
    2. Impuesto marginal = excedente × % sobre excedente
    3. ISR bruto = impuesto marginal + cuota fija
    4. SPE (solo asalariados dentro del tope; asimilados nunca)
    5. ISR final = max(0, ISR bruto − SPE)
    """
    if ingreso_gravado <= 0:
        return _resultado_vacio(periodicidad)

    tarifas = tarifa_por_periodicidad(anio, periodicidad)
    tramo = _buscar_tramo(ingreso_gravado, tarifas)
    if tramo is None:
        return _resultado_vacio(periodicidad)

    excedente = ingreso_gravado - tramo.limite_inferior
    impuesto_marginal = excedente * tramo.porcentaje_excedente
    isr_bruto = impuesto_marginal + tramo.cuota_fija

    subsidio = 0.0 if es_asimilado else calcular_spe(ingreso_gravado, anio, mes, periodicidad)

    isr_final = max(0.0, isr_bruto - subsidio)
    ingreso_neto = ingreso_gravado - isr_final
    tasa_efectiva = (isr_final / ingreso_gravado) * 100

    return {
        "ingreso_bruto": ingreso_gravado,
        "base_gravable": ingreso_gravado,
        "isr_bruto": isr_bruto,
        "subsidio_aplicado": subsidio,
        "isr_final": isr_final,
        "tasa_efectiva": tasa_efectiva,
        "ingreso_neto": ingreso_neto,
        "periodicidad": periodicidad,
        "desglose": {
            "limite_inferior": tramo.limite_inferior,
            "excedente_limite_inferior": excedente,
            "tasa_marginal": tramo.porcentaje_excedente,
            "impuesto_marginal": impuesto_marginal,
            "cuota_fija": tramo.cuota_fija,
            "isr_antes_subsidio": isr_bruto,
            "subsidio": subsidio,
            "isr_final": isr_final,
            "rango_tarifa": {
                "limite_inferior": tramo.limite_inferior,
                "limite_superior": tramo.limite_superior,
                "cuota_fija": tramo.cuota_fija,
                "porcentaje_sobre_excedente": tramo.porcentaje_excedente,
            },
        },
    }


def isr_final(ingreso_gravado: float, anio: int = 2026, es_asimilado: bool = False) -> float:
    """Atajo: solo el ISR final mensual (con SPE si aplica)."""
    return calcular_isr_periodo(ingreso_gravado, anio, "mensual", es_asimilado)["isr_final"]


def isr_tarifa_directa(base: float, anio: int = 2026) -> float:
    """ISR mensual por tarifa pura, SIN subsidio, con semántica de VLOOKUP.

    Réplica de la fórmula de la plantilla Excel de PTU:
    ``(base − LI) × % + cuota fija`` donde LI es el mayor límite inferior ≤ base
    (VLOOKUP aproximado). Para bases ≤ 0 devuelve 0.
    """
    if base <= 0:
        return 0.0
    ind = get_indicadores(anio)
    if ind.tarifa_isr_mensual is None:
        raise ValueError(f"Tarifa ISR mensual {anio} no disponible en indicadores.")
    aplicable = None
    for tramo in ind.tarifa_isr_mensual:
        if tramo.limite_inferior <= base:
            aplicable = tramo
        else:
            break
    if aplicable is None:
        return 0.0
    return (base - aplicable.limite_inferior) * aplicable.porcentaje_excedente + aplicable.cuota_fija


def isr_diferencial(base_extra: float, ordinario_mensual: float, anio: int = 2026) -> dict:
    """ISR de un pago extraordinario por el método directo (Art. 96 LISR).

    ISR = ISR(ordinario + extra) − ISR(ordinario), nunca negativo.
    Patrón compartido por aguinaldo y PTU (método "ley").
    """
    isr_total = isr_final(ordinario_mensual + base_extra, anio)
    isr_ordinario = isr_final(ordinario_mensual, anio)
    isr = max(0.0, isr_total - isr_ordinario)
    tasa = (isr / base_extra) * 100 if base_extra > 0 else 0.0
    return {"isr": isr, "tasa": tasa, "isr_total": isr_total, "isr_ordinario": isr_ordinario}


def tasa_efectiva_art174(gravado: float, ordinario_mensual: float, anio: int = 2026) -> dict:
    """ISR de un pago extraordinario por el método promediado (Art. 174 RLISR).

    1. Se mensualiza el gravado: (gravado / 365) × 30.4
    2. Tasa efectiva = [ISR(ordinario + mensualizado) − ISR(ordinario)] / mensualizado
    3. ISR = gravado × tasa efectiva
    """
    mensualizado = (gravado / DIAS_ANIO) * DIAS_MES_PROMEDIO
    isr_base = isr_final(ordinario_mensual + mensualizado, anio)
    isr_ordinario = isr_final(ordinario_mensual, anio)
    diferencia = max(0.0, isr_base - isr_ordinario)
    tasa_efectiva = diferencia / mensualizado if mensualizado > 0 else 0.0
    isr = gravado * tasa_efectiva
    return {
        "isr": isr,
        "tasa": tasa_efectiva * 100,
        "mensualizado": mensualizado,
        "isr_base": isr_base,
        "isr_ordinario": isr_ordinario,
        "diferencia": diferencia,
    }

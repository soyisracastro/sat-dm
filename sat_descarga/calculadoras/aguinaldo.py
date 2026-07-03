"""Calculadora de aguinaldo (Art. 87 LFT; exención Art. 93 fr. XIV LISR).

Port de ``calculadora-aguinaldo/calculations.ts`` (paridad centavo a centavo).
ISR por dos métodos: Art. 96 LISR (ley) y Art. 174 RLISR (reglamento), con
comparación y recomendación del menor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .comunes import (
    DIAS_ANIO,
    DIAS_MES_PROMEDIO,
    EXENCION_AGUINALDO_UMA,
    redondear,
)
from .indicadores import get_indicadores
from .isr import isr_diferencial, tasa_efectiva_art174


@dataclass(frozen=True)
class AguinaldoInput:
    salario: float
    tipo_salario: str  # "diario" | "mensual"
    fecha_ingreso: date
    dias_aguinaldo: int = 15
    fecha_calculo: date | None = None  # default: 20 de diciembre del ejercicio
    ingreso_ordinario_mensual: float | None = None
    metodo_isr: str = "ley"  # "ley" (Art. 96) | "reglamento" (Art. 174)
    anio: int = 2026


def _dias_trabajados_anio(fecha_ingreso: date, fecha_calculo: date) -> int:
    """Días trabajados en el año del cálculo (paridad con la web).

    Si el trabajador ingresó antes del año y el cálculo es en diciembre (pago
    estándar), se considera el año completo (365).
    """
    inicio_anio = date(fecha_calculo.year, 1, 1)
    if fecha_ingreso < inicio_anio and fecha_calculo.month == 12:
        return DIAS_ANIO
    inicio = fecha_ingreso if fecha_ingreso > inicio_anio else inicio_anio
    if inicio > fecha_calculo:
        return 0
    return min((fecha_calculo - inicio).days + 1, DIAS_ANIO)


def calcular_aguinaldo(inp: AguinaldoInput) -> dict:
    ind = get_indicadores(inp.anio)
    limite_exencion = ind.uma_diaria * EXENCION_AGUINALDO_UMA

    # 1. Salario diario
    salario_diario = inp.salario / DIAS_MES_PROMEDIO if inp.tipo_salario == "mensual" else inp.salario

    # 2. Días trabajados en el año
    fecha_calculo = inp.fecha_calculo or date(inp.anio, 12, 20)
    dias_trabajados = _dias_trabajados_anio(inp.fecha_ingreso, fecha_calculo)

    # 3. Días proporcionales de aguinaldo
    dias_proporcionales = (inp.dias_aguinaldo / DIAS_ANIO) * dias_trabajados

    # 4. Aguinaldo bruto
    aguinaldo_bruto = salario_diario * dias_proporcionales

    # 5. Parte exenta y gravada (30 UMA)
    parte_exenta = min(aguinaldo_bruto, limite_exencion)
    parte_gravada = max(0.0, aguinaldo_bruto - parte_exenta)

    # 6. ISR por ambos métodos (elige el solicitado; recomienda el menor)
    isr_retenido = 0.0
    tasa_efectiva_isr = 0.0
    comparacion = None

    ordinario = inp.ingreso_ordinario_mensual or (
        inp.salario if inp.tipo_salario == "mensual" else inp.salario * DIAS_MES_PROMEDIO
    )

    if parte_gravada > 0:
        res_ley = isr_diferencial(parte_gravada, ordinario, inp.anio)
        res_reglamento = tasa_efectiva_art174(parte_gravada, ordinario, inp.anio)

        if inp.metodo_isr == "reglamento":
            isr_retenido = res_reglamento["isr"]
            tasa_efectiva_isr = res_reglamento["tasa"]
        else:
            isr_retenido = res_ley["isr"]
            tasa_efectiva_isr = res_ley["tasa"]

        comparacion = {
            "metodo_ley": {
                "isr_calculado": redondear(res_ley["isr"]),
                "tasa_efectiva": redondear(res_ley["tasa"]),
            },
            "metodo_reglamento": {
                "isr_calculado": redondear(res_reglamento["isr"]),
                "tasa_efectiva": redondear(res_reglamento["tasa"]),
                "aguinaldo_mensualizado": redondear((parte_gravada / DIAS_ANIO) * DIAS_MES_PROMEDIO),
            },
            "diferencia": redondear(res_ley["isr"] - res_reglamento["isr"]),
            "metodo_recomendado": "reglamento" if res_reglamento["isr"] < res_ley["isr"] else "ley",
        }

    # 7. Aguinaldo neto
    aguinaldo_neto = aguinaldo_bruto - isr_retenido

    desglose = _generar_desglose(
        inp,
        salario_diario=salario_diario,
        dias_trabajados=dias_trabajados,
        aguinaldo_bruto=aguinaldo_bruto,
        parte_exenta=parte_exenta,
        parte_gravada=parte_gravada,
        isr_retenido=isr_retenido,
        ordinario=ordinario,
        fecha_calculo=fecha_calculo,
        uma_diaria=ind.uma_diaria,
        limite_exencion=limite_exencion,
    )

    return {
        "salario_diario": redondear(salario_diario),
        "dias_trabajados": dias_trabajados,
        "dias_aguinaldo_proporcionales": redondear(dias_proporcionales, 4),
        "aguinaldo_bruto": redondear(aguinaldo_bruto),
        "parte_exenta": redondear(parte_exenta),
        "parte_gravada": redondear(parte_gravada),
        "isr_retenido": redondear(isr_retenido),
        "tasa_efectiva_isr": redondear(tasa_efectiva_isr),
        "aguinaldo_neto": redondear(aguinaldo_neto),
        "desglose": desglose,
        "comparacion_metodos": comparacion,
    }


def _generar_desglose(
    inp: AguinaldoInput,
    *,
    salario_diario: float,
    dias_trabajados: int,
    aguinaldo_bruto: float,
    parte_exenta: float,
    parte_gravada: float,
    isr_retenido: float,
    ordinario: float,
    fecha_calculo: date,
    uma_diaria: float,
    limite_exencion: float,
) -> dict:
    metodo_label = "Art. 96 LISR" if inp.metodo_isr == "ley" else "Art. 174 RLISR"
    pasos = [
        {
            "numero": 1,
            "descripcion": "Determinar Salario Diario",
            "formula": "Salario Mensual / 30.4" if inp.tipo_salario == "mensual" else "Salario Diario Ingresado",
            "valores": {"Salario": inp.salario, "Factor": DIAS_MES_PROMEDIO},
            "resultado": redondear(salario_diario),
        },
        {
            "numero": 2,
            "descripcion": "Calcular Días Trabajados en el Año",
            "formula": "Días transcurridos entre la Fecha de Inicio y la Fecha de Corte",
            "valores": {
                "Fecha de Inicio": inp.fecha_ingreso.strftime("%d/%m/%Y"),
                "Fecha de Corte": fecha_calculo.strftime("%d/%m/%Y"),
            },
            "resultado": dias_trabajados,
        },
        {
            "numero": 3,
            "descripcion": "Calcular Aguinaldo Bruto",
            "formula": "(Salario Diario × Días de Aguinaldo / 365) × Días Trabajados",
            "valores": {
                "Salario Diario": redondear(salario_diario),
                "Días Aguinaldo": inp.dias_aguinaldo,
                "Días Trabajados": dias_trabajados,
            },
            "resultado": redondear(aguinaldo_bruto),
        },
        {
            "numero": 4,
            "descripcion": "Determinar Parte Exenta (30 UMAs)",
            "formula": "MIN(Aguinaldo Bruto, 30 × UMA)",
            "valores": {"UMA": uma_diaria, "Tope Exento": redondear(limite_exencion)},
            "resultado": redondear(parte_exenta),
        },
        {
            "numero": 5,
            "descripcion": "Calcular ISR Retenido",
            "formula": f"Método {metodo_label}",
            "valores": {
                "Parte Gravada": redondear(parte_gravada),
                **({"Ingreso Ordinario": redondear(ordinario)} if inp.metodo_isr == "reglamento" else {}),
            },
            "resultado": redondear(isr_retenido),
        },
        {
            "numero": 6,
            "descripcion": "Resultado Final: Aguinaldo Neto",
            "formula": "Aguinaldo Bruto - ISR",
            "valores": {"Bruto": redondear(aguinaldo_bruto), "ISR": redondear(isr_retenido)},
            "resultado": redondear(aguinaldo_bruto - isr_retenido),
        },
    ]
    return {
        "pasos": pasos,
        "parametros": {
            "uma_diaria": uma_diaria,
            "limite_exencion": redondear(limite_exencion),
            "ejercicio": inp.anio,
        },
    }

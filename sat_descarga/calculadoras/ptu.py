"""Calculadora de PTU — reparto de utilidades (LFT Arts. 117-131).

Implementa la lógica de la plantilla Excel de TodoConta
(``excel_templates/ptu/setup_template.py``), NO la de la calculadora web:

- **Año de pago = ejercicio + 1** (Art. 93 fr. XIV LISR): la exención (15 UMA o
  SMG) y la tarifa de ISR usan los valores del año en que se PAGA la PTU, no
  del ejercicio que generó las utilidades.
- **Tipo de persona** → fecha límite legal de pago (Moral 30/may, Física 29/jun
  del año de pago); si la fecha de pago la excede se emite advertencia.
- **Criterio de exención**: UMA (criterio SAT, default) o SMG (criterio
  PRODECON 2024: mayor exención, sin respaldo formal del SAT).
- **Trabajadores de confianza** (Art. 127 fr. II): su salario se topa al 120%
  del salario diario más alto de los trabajadores de planta; el factor de
  salarios usa min(percepción anual, tope × 365).
- **Reparto 50/50**: mitad por días trabajados, mitad por salarios devengados,
  sobre ``utilidad_fiscal × 10% + ptu_no_cobrada`` (la no cobrada prescribe en
  1 año y se suma al siguiente reparto).
- **Tope Art. 127 fr. VIII** (reforma 2021): max(3 meses de salario = salario
  diario × 91.2, promedio de la PTU de los últimos 3 años).
- **ISR por dos métodos**: Art. 96 LISR usa el ISR ordinario CAPTURADO (con
  subsidio); Art. 174 RLISR recalcula el ordinario SIN subsidio vía tarifa.
  Recomendado = menor ISR (mayor PTU neta).

El resultado incluye por trabajador los datos del recibo y del borrador de
pre-nómina (percepción 003-PTU, deducción 002-ISR, nómina extraordinaria) para
que el export solo tenga que renderizar.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .comunes import (
    DIAS_MINIMOS_EVENTUALES,
    DIAS_TOPE_TRES_MESES,
    EXENCION_PTU_DIAS,
    FACTOR_TOPE_CONFIANZA,
    PORCENTAJE_PTU,
    redondear,
)
from .indicadores import INDICADORES, UMA_SMG_HISTORICO
from .isr import isr_tarifa_directa


@dataclass(frozen=True)
class EmpresaPTU:
    utilidad_fiscal: float
    ejercicio: int  # año que generó las utilidades (se paga al año siguiente)
    nombre: str = ""
    rfc: str = ""
    ptu_no_cobrada: float = 0.0
    tipo_persona: str = "Moral"  # "Moral" | "Física"
    fecha_pago: date | None = None
    criterio_exencion: str = "UMA"  # "UMA" (SAT) | "SMG" (PRODECON)


@dataclass(frozen=True)
class TrabajadorPTU:
    nombre: str
    salario_diario: float
    dias_trabajados: float
    percepcion_anual: float
    rfc: str = ""
    curp: str = ""
    nss: str = ""
    fecha_inicio: date | None = None
    es_confianza: bool = False
    ptu_anio_1: float = 0.0  # PTU recibida hace 1 año
    ptu_anio_2: float = 0.0  # hace 2 años
    ptu_anio_3: float = 0.0  # hace 3 años
    ingreso_mensual_ordinario: float = 0.0
    isr_mensual_ordinario: float = 0.0


def _dias_mes_nombre(fecha: date) -> str:
    return fecha.strftime("%d/%m/%Y")


def calcular_ptu(empresa: EmpresaPTU, trabajadores: list[TrabajadorPTU]) -> dict:
    if empresa.utilidad_fiscal <= 0:
        raise ValueError("La utilidad fiscal debe ser mayor a 0.")
    if not trabajadores:
        raise ValueError("Se requiere al menos un trabajador.")

    anio_pago = empresa.ejercicio + 1
    soportados = sorted(
        a - 1
        for a, ind in INDICADORES.items()
        if ind.tarifa_isr_mensual is not None and a in UMA_SMG_HISTORICO
    )
    if anio_pago not in INDICADORES or INDICADORES[anio_pago].tarifa_isr_mensual is None:
        listado = ", ".join(str(a) for a in soportados)
        raise ValueError(
            f"El ejercicio {empresa.ejercicio} (año de pago {anio_pago}) no está "
            f"soportado; ejercicios soportados: {listado}."
        )
    uma_pago, smg_pago, smg_frontera_pago = UMA_SMG_HISTORICO[anio_pago]

    # Exención por trabajador: 15 × UMA o SMG del año de pago
    base_exencion = uma_pago if empresa.criterio_exencion == "UMA" else smg_pago
    exencion = base_exencion * EXENCION_PTU_DIAS

    # Fecha límite legal (Moral: 30/may; Física: 29/jun del año de pago)
    fecha_limite = (
        date(anio_pago, 5, 30) if empresa.tipo_persona == "Moral" else date(anio_pago, 6, 29)
    )

    advertencias: list[str] = []
    if empresa.fecha_pago and empresa.fecha_pago > fecha_limite:
        advertencias.append(
            f"La fecha de pago ({_dias_mes_nombre(empresa.fecha_pago)}) excede la fecha "
            f"límite legal ({_dias_mes_nombre(fecha_limite)}) para persona "
            f"{empresa.tipo_persona.lower()}."
        )

    # Bolsas de reparto
    ptu_generada = empresa.utilidad_fiscal * PORCENTAJE_PTU
    ptu_a_repartir = ptu_generada + empresa.ptu_no_cobrada
    bolsa_dias = ptu_a_repartir / 2
    bolsa_salarios = ptu_a_repartir / 2

    suma_dias = sum(t.dias_trabajados for t in trabajadores)
    suma_percepciones = sum(t.percepcion_anual for t in trabajadores)
    if suma_dias <= 0:
        raise ValueError("La suma de días trabajados debe ser mayor a 0.")
    if suma_percepciones <= 0:
        raise ValueError("La suma de percepciones anuales debe ser mayor a 0.")

    # Tope de confianza: 120% del salario diario más alto de planta
    salarios_planta = [t.salario_diario for t in trabajadores if not t.es_confianza]
    salario_max_planta = max(salarios_planta) if salarios_planta else 0.0
    tope_confianza = salario_max_planta * FACTOR_TOPE_CONFIANZA

    resultados = []
    for t in trabajadores:
        advertencias_t: list[str] = []
        if t.dias_trabajados < DIAS_MINIMOS_EVENTUALES:
            advertencias_t.append(
                f"Trabajó {t.dias_trabajados:.0f} días: los trabajadores eventuales "
                f"requieren mínimo {DIAS_MINIMOS_EVENTUALES} días para tener derecho a "
                "PTU (Art. 127 fr. VII LFT)."
            )

        # Reparto 50/50
        factor_dias = t.dias_trabajados / suma_dias
        ptu_dias = bolsa_dias * factor_dias

        if t.es_confianza and t.salario_diario > tope_confianza:
            percepcion_topada = min(t.percepcion_anual, tope_confianza * 365)
            factor_salarios = percepcion_topada / suma_percepciones
        else:
            factor_salarios = t.percepcion_anual / suma_percepciones
        ptu_salarios = bolsa_salarios * factor_salarios

        ptu_bruta = ptu_dias + ptu_salarios

        # Tope Art. 127 fr. VIII
        tope_tres_meses = t.salario_diario * DIAS_TOPE_TRES_MESES
        promedio_tres_anios = (t.ptu_anio_1 + t.ptu_anio_2 + t.ptu_anio_3) / 3
        monto_maximo = max(tope_tres_meses, promedio_tres_anios)
        ptu_real = min(ptu_bruta, monto_maximo)

        # Exención (año de pago)
        ptu_exenta = min(ptu_real, exencion)
        ptu_gravada = max(0.0, ptu_real - exencion)

        # ISR método Art. 96 LISR (con el ISR ordinario capturado)
        base_96 = t.ingreso_mensual_ordinario + ptu_gravada
        isr_total_96 = isr_tarifa_directa(base_96, anio_pago) if ptu_gravada > 0 else 0.0
        isr_ptu_96 = max(0.0, isr_total_96 - t.isr_mensual_ordinario) if ptu_gravada > 0 else 0.0
        ptu_neta_96 = ptu_real - isr_ptu_96

        # ISR método Art. 174 RLISR (ordinario recalculado SIN subsidio)
        prom_mensual_174 = (ptu_gravada / 365) * 30.4
        base_prom_174 = t.ingreso_mensual_ordinario + prom_mensual_174
        isr_base_prom = isr_tarifa_directa(base_prom_174, anio_pago) if ptu_gravada > 0 else 0.0
        isr_ord_sin_subsidio = (
            isr_tarifa_directa(t.ingreso_mensual_ordinario, anio_pago) if ptu_gravada > 0 else 0.0
        )
        diferencia_174 = isr_base_prom - isr_ord_sin_subsidio
        tasa_174 = diferencia_174 / prom_mensual_174 if prom_mensual_174 > 0 else 0.0
        isr_ptu_174 = ptu_gravada * tasa_174
        ptu_neta_174 = ptu_real - isr_ptu_174

        # Comparación y recomendación (menor ISR = mayor neta)
        metodo_recomendado = "art174" if isr_ptu_174 < isr_ptu_96 else "art96"
        isr_recomendado = min(isr_ptu_96, isr_ptu_174)
        ptu_neta_final = ptu_real - isr_recomendado

        resultados.append(
            {
                "nombre": t.nombre,
                "rfc": t.rfc,
                "curp": t.curp,
                "nss": t.nss,
                "salario_diario": t.salario_diario,
                "dias_trabajados": t.dias_trabajados,
                "percepcion_anual": t.percepcion_anual,
                "es_confianza": t.es_confianza,
                "salario_tope_confianza": redondear(tope_confianza) if t.es_confianza else None,
                "ingreso_mensual_ordinario": t.ingreso_mensual_ordinario,
                "isr_mensual_ordinario": t.isr_mensual_ordinario,
                "factor_dias": redondear(factor_dias, 6),
                "ptu_dias": redondear(ptu_dias),
                "factor_salarios": redondear(factor_salarios, 6),
                "ptu_salarios": redondear(ptu_salarios),
                "ptu_bruta": redondear(ptu_bruta),
                "tope_tres_meses": redondear(tope_tres_meses),
                "promedio_tres_anios": redondear(promedio_tres_anios),
                "monto_maximo": redondear(monto_maximo),
                "ptu_real": redondear(ptu_real),
                "exencion_aplicable": redondear(exencion),
                "ptu_exenta": redondear(ptu_exenta),
                "ptu_gravada": redondear(ptu_gravada),
                "art96": {
                    "base_gravable": redondear(base_96),
                    "isr_total": redondear(isr_total_96),
                    "isr_ordinario": redondear(t.isr_mensual_ordinario),
                    "isr_ptu": redondear(isr_ptu_96),
                    "ptu_neta": redondear(ptu_neta_96),
                },
                "art174": {
                    "ptu_promedio_mensual": redondear(prom_mensual_174),
                    "base_promediada": redondear(base_prom_174),
                    "isr_base_promediada": redondear(isr_base_prom),
                    "isr_ordinario_sin_subsidio": redondear(isr_ord_sin_subsidio),
                    "diferencia_isr": redondear(diferencia_174),
                    "tasa_efectiva": redondear(tasa_174 * 100, 4),
                    "isr_ptu": redondear(isr_ptu_174),
                    "ptu_neta": redondear(ptu_neta_174),
                },
                "comparacion": {
                    "diferencia_isr": redondear(abs(isr_ptu_96 - isr_ptu_174)),
                    "metodo_recomendado": metodo_recomendado,
                    "isr_recomendado": redondear(isr_recomendado),
                    "ptu_neta_final": redondear(ptu_neta_final),
                },
                "prenomina": {
                    "regimen": "Sueldos y Salarios",
                    "tipo_nomina": "Extraordinaria",
                    "clave_percepcion": "003",
                    "concepto_percepcion": "PTU",
                    "ptu_gravada": redondear(ptu_gravada),
                    "ptu_exenta": redondear(ptu_exenta),
                    "clave_deduccion": "002",
                    "concepto_deduccion": "ISR",
                    "isr_retenido": redondear(isr_recomendado),
                    "neto_a_pagar": redondear(ptu_neta_final),
                },
                "advertencias": advertencias_t,
            }
        )

    totales = {
        "ptu_bruta": redondear(sum(r["ptu_bruta"] for r in resultados)),
        "ptu_real": redondear(sum(r["ptu_real"] for r in resultados)),
        "ptu_exenta": redondear(sum(r["ptu_exenta"] for r in resultados)),
        "ptu_gravada": redondear(sum(r["ptu_gravada"] for r in resultados)),
        "isr_art96": redondear(sum(r["art96"]["isr_ptu"] for r in resultados)),
        "isr_art174": redondear(sum(r["art174"]["isr_ptu"] for r in resultados)),
        "isr_recomendado": redondear(sum(r["comparacion"]["isr_recomendado"] for r in resultados)),
        "ptu_neta_a_pagar": redondear(sum(r["comparacion"]["ptu_neta_final"] for r in resultados)),
    }

    return {
        "config": {
            "ejercicio": empresa.ejercicio,
            "anio_pago": anio_pago,
            "uma_diaria": uma_pago,
            "smg_general": smg_pago,
            "smg_frontera": smg_frontera_pago,
            "criterio_exencion": empresa.criterio_exencion,
            "dias_exencion": EXENCION_PTU_DIAS,
            "exencion_por_trabajador": redondear(exencion),
            "tipo_persona": empresa.tipo_persona,
            "fecha_pago": empresa.fecha_pago.isoformat() if empresa.fecha_pago else None,
            "fecha_limite_pago": fecha_limite.isoformat(),
        },
        "empresa": {
            "nombre": empresa.nombre,
            "rfc": empresa.rfc,
            "utilidad_fiscal": empresa.utilidad_fiscal,
            "ptu_no_cobrada": empresa.ptu_no_cobrada,
            "ptu_generada": redondear(ptu_generada),
            "ptu_a_repartir": redondear(ptu_a_repartir),
            "bolsa_dias": redondear(bolsa_dias),
            "bolsa_salarios": redondear(bolsa_salarios),
        },
        "trabajadores": resultados,
        "totales": totales,
        "advertencias": advertencias,
    }

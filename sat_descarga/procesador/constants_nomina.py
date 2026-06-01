"""
Constantes fiscales del procesador de Nómina: UMA, topes IMSS, tarifas ISR
mensuales por año y subsidio para el empleo (SPE).

Portado de todoconta-apps `lib/procesador-nomina/{constants.ts,isr-tariffs.ts,subsidio-empleo.ts}`.
Mantener los valores idénticos para que los reportes sean consistentes entre
proyectos (cualquier comparación que haga el contador entre la app local y el
web debe cuadrar).

Fuentes oficiales:
- Anexo 8 RMF 2026 (DOF 28-12-2025).
- Anexo 8 RMF 2024 (DOF 29-12-2023) — vigente 2023-2025.
- DOF RMF 2022 (12-01-2022) — vigente 2020-2022.
- DOF Subsidio al Empleo 2026 (31-12-2025).
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# UMA y salarios mínimos 2026
# ---------------------------------------------------------------------------

UMA_2026 = 117.31              # diaria
UMA_2026_MENSUAL = 3568.13     # mensual

SALARIO_MINIMO_GENERAL_2026 = 315.04
SALARIO_MINIMO_ZLFN_2026 = 474.11

# Salario Base de Cotización: tope diario IMSS (25 UMA).
SBC_TOPE_DIARIO = UMA_2026 * 25  # 2,932.75


# ---------------------------------------------------------------------------
# Subsidio al Empleo (SPE) 2026 — valores mensuales informativos
# ---------------------------------------------------------------------------

SUBSIDIO_EMPLEO_MENSUAL = 536.22
SUBSIDIO_EMPLEO_DIARIO = 17.64

SUBSIDIO_LIMITES = {
    "SUBSIDIO_DIARIO": 628.0,
    "SUBSIDIO_MULTIPLICADOR_DIAS": 20.66,
}


# ---------------------------------------------------------------------------
# Exenciones ISR (Art. 93 LISR)
# ---------------------------------------------------------------------------

EXENCIONES_ISR = {
    "AGUINALDO_UMA": 30,
    "PTU_UMA": 15,
    "PRIMA_VACACIONAL_UMA": 15,
    "JUBILACION_UMA": 15,
    "INDEMNIZACION_UMA_POR_ANO": 90,
    "PRIMA_ANTIGUEDAD_UMA_POR_ANO": 90,
    "VALES_DESPENSA_SMG": 0.4,
    "PREVISION_SOCIAL_UMA": 7,
}


# ---------------------------------------------------------------------------
# Cuotas IMSS 2026 (descompuestas — usadas con SBC diario)
# ---------------------------------------------------------------------------

CUOTAS_IMSS_2026 = {
    "ENFERMEDADES_MATERNIDAD_FIJA_PATRONAL": 0.204,
    "ENFERMEDADES_MATERNIDAD_EXCEDENCIA_PATRONAL": 0.011,
    "ENFERMEDADES_MATERNIDAD_EXCEDENCIA_OBRERA": 0.004,
    "ENFERMEDADES_MATERNIDAD_DINERO_PATRONAL": 0.007,
    "ENFERMEDADES_MATERNIDAD_DINERO_OBRERA": 0.0025,
    "INVALIDEZ_VIDA_PATRONAL": 0.0175,
    "INVALIDEZ_VIDA_OBRERA": 0.00625,
    "GUARDERIAS_PATRONAL": 0.01,
    "RETIRO_PATRONAL": 0.02,
    "CESANTIA_VEJEZ_PATRONAL": 0.04515,
    "CESANTIA_VEJEZ_OBRERA": 0.01125,
    "INFONAVIT_PATRONAL": 0.05,
}

# Tasas agregadas usadas por el reporte IMSS para el cálculo orientativo.
# Mantienen la fórmula del referente (todoconta: SBC × 0.1875 patrón, × 0.0625
# obrero — agregados orientativos de las cuotas IMSS sin desglosar).
IMSS_TASA_AGREGADA_PATRONAL = 0.1875
IMSS_TASA_AGREGADA_OBRERA = 0.0625


# ---------------------------------------------------------------------------
# Tarifas ISR mensuales (Art. 96 LISR)
#
# Se hardcodean por rango de años porque solo se actualizan cuando la
# inflación acumulada supera 10% (Art. 152 LISR). Cubrimos 2020-2026 con
# 3 tarifas.
#
# Cada tupla: (lim_inf, lim_sup_o_None, cuota_fija, pct_excedente_decimal).
# ---------------------------------------------------------------------------

# 2020-2022 (DOF RMF 2022).
_TARIFA_2020_2022: list[tuple[float, Optional[float], float, float]] = [
    (0.01,        644.58,    0.0,      0.0192),
    (644.59,      5470.92,   12.38,    0.0640),
    (5470.93,     9614.66,   321.26,   0.1088),
    (9614.67,     11176.62,  772.10,   0.1600),
    (11176.63,    13381.47,  1022.01,  0.1792),
    (13381.48,    26988.50,  1417.12,  0.2136),
    (26988.51,    42537.58,  4323.58,  0.2352),
    (42537.59,    81211.25,  7980.73,  0.3000),
    (81211.26,    108281.67, 19582.83, 0.3200),
    (108281.68,   324845.01, 28245.36, 0.3400),
    (324845.02,   None,      101876.90, 0.3500),
]

# 2023-2025 (DOF 29-12-2022).
_TARIFA_2023_2025: list[tuple[float, Optional[float], float, float]] = [
    (0.01,        746.04,    0.0,      0.0192),
    (746.05,      6332.05,   14.32,    0.0640),
    (6332.06,     11128.01,  371.83,   0.1088),
    (11128.02,    12935.82,  893.63,   0.1600),
    (12935.83,    15487.71,  1182.88,  0.1792),
    (15487.72,    31236.49,  1640.18,  0.2136),
    (31236.50,    49233.00,  5004.12,  0.2352),
    (49233.01,    93993.90,  9236.89,  0.3000),
    (93993.91,    125325.20, 22665.17, 0.3200),
    (125325.21,   375975.61, 32691.18, 0.3400),
    (375975.62,   None,      117912.32, 0.3500),
]

# 2026 (DOF 28-12-2025 — Anexo 8 RMF 2026, factor de inflación 1.1321).
_TARIFA_2026: list[tuple[float, Optional[float], float, float]] = [
    (0.01,        844.59,    0.0,      0.0192),
    (844.60,      7168.51,   16.22,    0.0640),
    (7168.52,     12598.02,  420.95,   0.1088),
    (12598.03,    14644.64,  1011.68,  0.1600),
    (14644.65,    17533.64,  1339.14,  0.1792),
    (17533.65,    35362.83,  1856.84,  0.2136),
    (35362.84,    55736.68,  5665.16,  0.2352),
    (55736.69,    106410.50, 10457.09, 0.3000),
    (106410.51,   141880.66, 25659.23, 0.3200),
    (141880.67,   425641.99, 37009.69, 0.3400),
    (425642.00,   None,      133488.54, 0.3500),
]


def get_isr_tarifa(year: int) -> list[tuple[float, Optional[float], float, float]]:
    """Devuelve la tarifa ISR vigente para el año dado (fallback al rango más antiguo)."""
    if year >= 2026:
        return _TARIFA_2026
    if year >= 2023:
        return _TARIFA_2023_2025
    return _TARIFA_2020_2022


def get_tarifa_year_label(year: int) -> str:
    if year >= 2026:
        return "2026"
    if year >= 2023:
        return "2023-2025"
    return "2020-2022"


def calcular_isr_bruto(ingreso_gravado: float, year: int) -> float:
    """
    Aplica la tarifa ISR mensual al ingreso gravado.

    Fórmula: ISR = cuota_fija + (ingreso_gravado - lim_inf) × pct_excedente.
    """
    if ingreso_gravado <= 0:
        return 0.0

    tarifa = get_isr_tarifa(year)
    for lim_inf, lim_sup, cuota_fija, pct in tarifa:
        sup = lim_sup if lim_sup is not None else float("inf")
        if lim_inf <= ingreso_gravado <= sup:
            excedente = ingreso_gravado - lim_inf
            return cuota_fija + excedente * pct

    # Si excede todos los rangos (solo posible si la lista no llegara hasta None)
    ultima = tarifa[-1]
    lim_inf, _, cuota_fija, pct = ultima
    return cuota_fija + (ingreso_gravado - lim_inf) * pct


# ---------------------------------------------------------------------------
# Subsidio para el Empleo (SPE)
#
# - 2020-2024: tabla tradicional de montos fijos por rango de ingresos.
# - 2025-2026: porcentaje de UMA mensual (decreto DOF 01-05-2024 modernizó
#   el SPE) — enero tiene un porcentaje especial.
# ---------------------------------------------------------------------------

_SPE_TABLA_2020_2024: list[tuple[float, float, float]] = [
    (0.01,    1768.96, 407.02),
    (1768.97, 2653.38, 406.83),
    (2653.39, 3472.84, 406.62),
    (3472.85, 3537.87, 392.77),
    (3537.88, 4446.15, 382.46),
    (4446.16, 4717.18, 354.23),
    (4717.19, 5335.42, 324.87),
    (5335.43, 6224.67, 294.63),
    (6224.68, 7113.90, 253.54),
    (7113.91, 7382.33, 217.61),
]

_SPE_CONFIG_UMA = {
    2025: {
        "uma_mensual": 3153.70,
        "limite_ingresos": 10171.00,
        "porcentaje_enero": 0.1439,
        "porcentaje_resto": 0.1380,
    },
    2026: {
        "uma_mensual": 3566.22,
        "limite_ingresos": 11492.66,
        "porcentaje_enero": 0.1559,
        "porcentaje_resto": 0.1502,
    },
}


def _calcular_spe_tabla(ingreso_gravado: float) -> float:
    if ingreso_gravado <= 0:
        return 0.0
    for lim_inf, lim_sup, subsidio in _SPE_TABLA_2020_2024:
        if lim_inf <= ingreso_gravado <= lim_sup:
            return subsidio
    return 0.0


def _calcular_spe_uma(ingreso_gravado: float, year: int, mes: int) -> float:
    cfg = _SPE_CONFIG_UMA[2026 if year >= 2026 else 2025]
    if ingreso_gravado > cfg["limite_ingresos"]:
        return 0.0
    pct = cfg["porcentaje_enero"] if mes == 1 else cfg["porcentaje_resto"]
    return cfg["uma_mensual"] * pct


def calcular_spe(ingreso_gravado: float, year: int, mes: int = 2) -> float:
    """
    SPE mensual aplicable.

    - 2020-2024 → tabla de montos fijos.
    - 2025+    → porcentaje de UMA mensual. `mes=1` aplica el porcentaje
                 especial de enero; cualquier otro mes usa el porcentaje
                 estándar del año.
    """
    if ingreso_gravado <= 0:
        return 0.0
    if year >= 2025:
        return _calcular_spe_uma(ingreso_gravado, year, mes)
    return _calcular_spe_tabla(ingreso_gravado)


def get_limite_spe(year: int) -> float:
    """Límite máximo de ingresos para recibir SPE en el año dado."""
    if year >= 2026:
        return _SPE_CONFIG_UMA[2026]["limite_ingresos"]
    if year >= 2025:
        return _SPE_CONFIG_UMA[2025]["limite_ingresos"]
    return 7382.33


# ---------------------------------------------------------------------------
# Tolerancias de validación
# ---------------------------------------------------------------------------

INTEGRIDAD_TOLERANCE = 0.02

SUPPORTED_YEARS = (2020, 2021, 2022, 2023, 2024, 2025, 2026)


def is_year_supported(year: int) -> bool:
    return 2020 <= year <= 2026


# ---------------------------------------------------------------------------
# Periodicidad — esperados por mes (para detectar periodos incompletos)
# ---------------------------------------------------------------------------

PERIODOS_ESPERADOS_POR_MES: dict[str, tuple[int, str]] = {
    "02": (4, "semanas"),
    "03": (2, "catorcenas"),
    "04": (2, "quincenas"),
    "05": (1, "mes"),
    "10": (3, "decenas"),
}

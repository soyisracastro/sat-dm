"""Constantes y utilidades compartidas entre calculadoras (independientes del año).

Los valores que SÍ cambian por año (UMA, SMG, tarifas ISR, SPE, cuotas IMSS)
viven en ``indicadores.py``. Aquí solo lo que la ley fija sin fecha de caducidad
inmediata: días del año, periodicidades, tabla de vacaciones LFT 2023, primas de
riesgo, exenciones expresadas en UMA, tipos de terminación, ISN por estado.
"""

from __future__ import annotations

import math

# ── Tiempo ────────────────────────────────────────────────────────────────────
DIAS_ANIO = 365
DIAS_MES_PROMEDIO = 30.4

# Periodicidades del Anexo 8 RMF (factor sobre la tarifa mensual)
PERIODICIDADES = ("diario", "semanal", "decenal", "quincenal", "mensual")
FACTORES_PERIODICIDAD: dict[str, float] = {
    "diario": 1 / 30.4,
    "semanal": 7 / 30.4,
    "decenal": 10 / 30.4,
    "quincenal": 15 / 30.4,
    "mensual": 1.0,
}
DIAS_PERIODICIDAD: dict[str, float] = {
    "diario": 1,
    "semanal": 7,
    "decenal": 10,
    "quincenal": 15,
    "mensual": 30.4,
}


def redondear(valor: float, decimales: int = 2) -> float:
    """Redondeo con paridad JavaScript (``Math.round``: mitades hacia +∞).

    El ``round()`` nativo de Python usa banker's rounding y rompería la paridad
    centavo a centavo con la calculadora web, que es el criterio de aceptación
    del port. Redondear SOLO donde la web redondea.
    """
    factor = 10**decimales
    return math.floor(valor * factor + 0.5) / factor


# ── Vacaciones (reforma LFT 2023, "vacaciones dignas") ───────────────────────
TABLA_VACACIONES_LFT: dict[int, int] = {
    1: 12, 2: 14, 3: 16, 4: 18, 5: 20,
    6: 22, 7: 22, 8: 22, 9: 22, 10: 22,
    11: 24, 12: 24, 13: 24, 14: 24, 15: 24,
    16: 26, 17: 26, 18: 26, 19: 26, 20: 26,
    21: 28, 22: 28, 23: 28, 24: 28, 25: 28,
    26: 30, 27: 30, 28: 30, 29: 30, 30: 30,
    31: 32, 32: 32, 33: 32, 34: 32, 35: 32,
}


def dias_vacaciones(antiguedad_anios: int) -> int:
    """Días de vacaciones según antigüedad (Art. 76 LFT, reforma 2023).

    Paridad con ``getDiasVacaciones`` de la web (formatting.ts), incluida su
    fórmula para >35 años: 32 base + 2 días por cada 5 años arriba de 30.
    """
    if antiguedad_anios <= 0:
        return 0
    if antiguedad_anios <= 35:
        return TABLA_VACACIONES_LFT.get(antiguedad_anios, 12)
    periodos_de_cinco = math.floor((antiguedad_anios - 30) / 5)
    return 32 + (periodos_de_cinco - 1) * 2


# ── Exenciones de ISR expresadas en UMA (Art. 93 LISR) ────────────────────────
EXENCION_AGUINALDO_UMA = 30            # fr. XIV
EXENCION_PRIMA_VACACIONAL_UMA = 15     # fr. XIV
EXENCION_PTU_DIAS = 15                 # fr. XIV (UMA o SMG según criterio)
EXENCION_SEPARACION_UMA_POR_ANIO = 90  # fr. XIII (pagos por separación)

# ── Liquidación (LFT) ─────────────────────────────────────────────────────────
PRIMA_ANTIGUEDAD_DIAS_POR_ANIO = 12    # Art. 162
TOPE_PRIMA_ANTIGUEDAD_SMG = 2          # Art. 162 → tope 2 × salario mínimo
ANIOS_MINIMOS_RENUNCIA_PRIMA = 15      # Art. 162 fr. III
MESES_INDEMNIZACION_CONSTITUCIONAL = 3  # Art. 48 → 90 días
DIAS_POR_ANIO_ART50 = 20               # Art. 50 fr. II

# ── Aguinaldo / prima vacacional (LFT) ────────────────────────────────────────
DIAS_AGUINALDO_MINIMO = 15             # Art. 87
PRIMA_VACACIONAL_MINIMA = 0.25         # Art. 80

# ── PTU (LFT Arts. 117-131) ───────────────────────────────────────────────────
PORCENTAJE_PTU = 0.10                  # Art. 120 (resolución CNPTU)
DIAS_TOPE_TRES_MESES = 91.2            # 30.4 × 3, tope Art. 127 fr. VIII
FACTOR_TOPE_CONFIANZA = 1.2            # Art. 127 fr. II: 120% del sindicalizado más alto
DIAS_MINIMOS_EVENTUALES = 60           # Art. 127 fr. VII

TIPOS_TERMINACION: dict[str, dict] = {
    "DESPIDO_INJUSTIFICADO": {
        "label": "Despido Injustificado",
        "descripcion": (
            "El patrón despide al trabajador sin causa justificada. El trabajador "
            "acepta la indemnización sin demandar reinstalación."
        ),
        "finiquito": True,
        "tres_meses": True,
        "veinte_dias": False,  # solo si demanda reinstalación y el patrón se niega
        "prima_antiguedad": True,
        "fundamento_legal": "Artículo 48 LFT",
    },
    "RESCISION_ART51": {
        "label": "Rescisión por el Trabajador (Art. 51)",
        "descripcion": (
            "El trabajador termina la relación laboral por causas imputables al "
            "patrón (reducción de salario, violencia, acoso, etc.)."
        ),
        "finiquito": True,
        "tres_meses": True,
        "veinte_dias": True,
        "prima_antiguedad": True,
        "fundamento_legal": "Artículos 50 y 51 LFT",
    },
    "TERMINACION_COLECTIVA": {
        "label": "Terminación Colectiva",
        "descripcion": (
            "Cierre de empresa, reducción de personal, quiebra o concurso, o "
            "implantación de maquinaria/procedimientos nuevos."
        ),
        "finiquito": True,
        "tres_meses": True,
        "veinte_dias": True,
        "prima_antiguedad": True,
        "fundamento_legal": "Artículos 433, 434, 436 y 439 LFT",
    },
    "RENUNCIA_VOLUNTARIA": {
        "label": "Renuncia Voluntaria",
        "descripcion": (
            "El trabajador decide terminar la relación laboral por su propia "
            "voluntad. Solo recibe finiquito; prima de antigüedad solo si tiene "
            "15+ años."
        ),
        "finiquito": True,
        "tres_meses": False,
        "veinte_dias": False,
        "prima_antiguedad": "condicional",  # solo con 15+ años
        "fundamento_legal": "Artículo 162 fracción III LFT",
    },
}


def aplica_veinte_dias(tipo_terminacion: str) -> bool:
    return TIPOS_TERMINACION[tipo_terminacion]["veinte_dias"] is True


def aplica_prima_antiguedad(tipo_terminacion: str, antiguedad_anios: int) -> bool:
    regla = TIPOS_TERMINACION[tipo_terminacion]["prima_antiguedad"]
    if regla is True:
        return True
    if regla == "condicional":
        return antiguedad_anios >= ANIOS_MINIMOS_RENUNCIA_PRIMA
    return False


# ── IMSS: primas de riesgo de trabajo por clase (Art. 73 LSS, primas medias) ──
PRIMAS_RIESGO: dict[str, float] = {
    "I": 0.0054355,   # 0.54355%
    "II": 0.0113065,  # 1.13065%
    "III": 0.025984,  # 2.59840%
    "IV": 0.0465325,  # 4.65325%
    "V": 0.0758875,   # 7.58875%
}

DESCRIPCION_CLASES_RIESGO: dict[str, str] = {
    "I": "Actividades seguras como oficinas administrativas, servicios educativos o consultorías",
    "II": "Comercio minorista, restaurantes, servicios médicos en consultorios",
    "III": "Manufactura ligera, uso de herramientas o maquinaria no pesada",
    "IV": "Construcción, minería superficial, productos químicos",
    "V": "Minería subterránea, plataformas petroleras, sustancias tóxicas extremas",
}

# ── Impuesto sobre nómina por estado (tasas nominales 2026) ───────────────────
# Las tasas cambian por ley estatal; la UI permite editarla manualmente.
ESTADOS_ISN: list[dict] = [
    {"codigo": "AGS", "nombre": "Aguascalientes", "tasa_nomina": 0.025},
    {"codigo": "BC", "nombre": "Baja California", "tasa_nomina": 0.0425},
    {"codigo": "BCS", "nombre": "Baja California Sur", "tasa_nomina": 0.025},
    {"codigo": "CAMP", "nombre": "Campeche", "tasa_nomina": 0.02},
    {"codigo": "CHAP", "nombre": "Chiapas", "tasa_nomina": 0.02},
    {"codigo": "CHIH", "nombre": "Chihuahua", "tasa_nomina": 0.03},
    {"codigo": "COAH", "nombre": "Coahuila", "tasa_nomina": 0.02},
    {"codigo": "COL", "nombre": "Colima", "tasa_nomina": 0.02},
    {"codigo": "CDMX", "nombre": "Ciudad de México", "tasa_nomina": 0.04},
    {"codigo": "DGO", "nombre": "Durango", "tasa_nomina": 0.02},
    {"codigo": "MEX", "nombre": "Estado de México", "tasa_nomina": 0.03},
    {"codigo": "GTO", "nombre": "Guanajuato", "tasa_nomina": 0.03},
    {"codigo": "GRO", "nombre": "Guerrero", "tasa_nomina": 0.03},
    {"codigo": "HGO", "nombre": "Hidalgo", "tasa_nomina": 0.03},
    {"codigo": "JAL", "nombre": "Jalisco", "tasa_nomina": 0.03},
    {"codigo": "MICH", "nombre": "Michoacán", "tasa_nomina": 0.03},
    {"codigo": "MOR", "nombre": "Morelos", "tasa_nomina": 0.025},
    {"codigo": "NAY", "nombre": "Nayarit", "tasa_nomina": 0.03},
    {"codigo": "NL", "nombre": "Nuevo León", "tasa_nomina": 0.03},
    {"codigo": "OAX", "nombre": "Oaxaca", "tasa_nomina": 0.03},
    {"codigo": "PUE", "nombre": "Puebla", "tasa_nomina": 0.03},
    {"codigo": "QRO", "nombre": "Querétaro", "tasa_nomina": 0.03},
    {"codigo": "QROO", "nombre": "Quintana Roo", "tasa_nomina": 0.03},
    {"codigo": "SLP", "nombre": "San Luis Potosí", "tasa_nomina": 0.03},
    {"codigo": "SIN", "nombre": "Sinaloa", "tasa_nomina": 0.024},
    {"codigo": "SON", "nombre": "Sonora", "tasa_nomina": 0.03},
    {"codigo": "TAB", "nombre": "Tabasco", "tasa_nomina": 0.03},
    {"codigo": "TAMPS", "nombre": "Tamaulipas", "tasa_nomina": 0.03},
    {"codigo": "TLAX", "nombre": "Tlaxcala", "tasa_nomina": 0.03},
    {"codigo": "VER", "nombre": "Veracruz", "tasa_nomina": 0.03},
    {"codigo": "YUC", "nombre": "Yucatán", "tasa_nomina": 0.03},
    {"codigo": "ZAC", "nombre": "Zacatecas", "tasa_nomina": 0.035},
]


def tasa_isn_estado(codigo_estado: str) -> float:
    """Tasa de impuesto sobre nómina del estado, o 2.5% si no se encuentra."""
    for estado in ESTADOS_ISN:
        if estado["codigo"] == codigo_estado:
            return estado["tasa_nomina"]
    return 0.025

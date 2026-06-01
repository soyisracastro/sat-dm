"""
Procesador de comprobantes XML (CFDI, Pagos, Nómina).

Este paquete acumula CFDIs ya descargados por el agente (o subidos manualmente
por el usuario), los persiste en SQLite local y genera reportes/exportaciones.

Diferente de `sat_descarga/utils/xml_reader.py`, que es un parser ligero usado
para validación/organización tras la descarga. Aquí extraemos todos los campos
necesarios para reportes fiscales completos.

Ver el plan en /Users/isca/.claude/plans/analiza-el-proyecto-y-wild-parnas.md
para el roadmap multi-PR (CFDI → Pagos → Nómina).
"""

from .cfdi_parser import CfdiData, ConceptoCfdi, parse_cfdi
from .db import ProcesadorDB, abrir_db
from .catalogos import (
    FORMAS_PAGO,
    METODOS_PAGO,
    USOS_CFDI,
    TIPOS_COMPROBANTE,
    MONEDAS,
    MAX_FILE_SIZE,
    MAX_BATCH_SIZE,
)

__all__ = [
    "CfdiData",
    "ConceptoCfdi",
    "parse_cfdi",
    "ProcesadorDB",
    "abrir_db",
    "FORMAS_PAGO",
    "METODOS_PAGO",
    "USOS_CFDI",
    "TIPOS_COMPROBANTE",
    "MONEDAS",
    "MAX_FILE_SIZE",
    "MAX_BATCH_SIZE",
]

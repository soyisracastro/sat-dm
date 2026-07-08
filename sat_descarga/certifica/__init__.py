"""
Generación de solicitudes de e.firma y CSD (equivalente a la app "Certifica" del
SAT), en Python puro sobre `cryptography`. Ver `generador.py` para el detalle.

Portado de `satcfdi.certifica` (MIT).
"""

from .generador import (
    generar_requerimiento_fiel,
    generar_renovacion_fiel,
    generar_renovacion_fiel_moral,
    generar_solicitud_csd,
)

__all__ = [
    "generar_requerimiento_fiel",
    "generar_renovacion_fiel",
    "generar_renovacion_fiel_moral",
    "generar_solicitud_csd",
]

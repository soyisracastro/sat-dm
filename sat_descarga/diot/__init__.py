"""DIOT 2025 — generación del archivo de carga masiva (carga batch) del SAT.

Prellenado desde el buffer del procesador + estado editable por RFC/periodo +
exportación del .txt oficial de 54 campos. Layout y reglas: docs/producto/diot-2025.md.
"""

from .agregacion import prellenar_desde_procesador, prellenar_y_guardar
from .catalogos import (
    MANIFIESTO,
    OPERACIONES_POR_TERCERO,
    PAISES,
    TIPO_OPERACION,
    TIPO_TERCERO,
)
from .exportar import DiotInvalida, exportar_txt, nombre_archivo
from .layout import CAMPOS_DIOT, CampoDiot, fila_vacia, formatear_linea
from .store import delete_periodo, get_periodo, set_periodo, validar_periodo
from .validaciones import validar_filas

__all__ = [
    "CAMPOS_DIOT",
    "CampoDiot",
    "DiotInvalida",
    "MANIFIESTO",
    "OPERACIONES_POR_TERCERO",
    "PAISES",
    "TIPO_OPERACION",
    "TIPO_TERCERO",
    "delete_periodo",
    "exportar_txt",
    "fila_vacia",
    "formatear_linea",
    "get_periodo",
    "nombre_archivo",
    "prellenar_desde_procesador",
    "prellenar_y_guardar",
    "set_periodo",
    "validar_filas",
    "validar_periodo",
]

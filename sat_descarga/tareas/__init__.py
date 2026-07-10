"""Tareas personales del usuario (centro de mando de pendientes).

Persistencia en ``~/.sat-descarga/tareas.json`` — API pública en
:mod:`sat_descarga.tareas.store`.
"""

from .store import (
    ESTADOS,
    PRIORIDADES,
    TIPOS,
    actualizar,
    crear,
    descartar_sugerencia,
    eliminar,
    listar,
)

__all__ = [
    "ESTADOS",
    "PRIORIDADES",
    "TIPOS",
    "actualizar",
    "crear",
    "descartar_sugerencia",
    "eliminar",
    "listar",
]

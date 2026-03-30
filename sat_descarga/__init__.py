"""
sat_descarga — Cliente Python para el Web Service de Descarga Masiva del SAT.

Uso rápido:
    from sat_descarga import descargar_cfdi
    from datetime import date

    descargar_cfdi(
        cer_path="efirma.cer",
        key_path="efirma.key",
        password="mi_password",
        fecha_inicio=date(2024, 1, 1),
        fecha_fin=date(2024, 1, 31),
        tipo_comprobante="R",  # "R"=recibidos, "E"=emitidos
        directorio_salida="./mis_cfdi/",
    )
"""

from .client import descargar_cfdi, verificar_solicitud_existente
from .fiel import FIEL
from .auth import obtener_token
from .solicitud import solicitar_descarga
from .verificacion import verificar_solicitud
from .descarga import descargar_paquete, descargar_todos

__all__ = [
    "descargar_cfdi",
    "verificar_solicitud_existente",
    "FIEL",
    "obtener_token",
    "solicitar_descarga",
    "verificar_solicitud",
    "descargar_paquete",
    "descargar_todos",
]

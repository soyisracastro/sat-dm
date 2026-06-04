"""
sat_descarga — Descarga masiva de CFDIs y documentos del SAT (México).

Organizado por canal de acceso:
- ``webservice/`` : Web Service oficial (FIEL/SOAP, asíncrono) — CFDIs.
- ``portal/``     : scraping del portal (CIEC o e.firma) — CFDIs y documentos
                    (constancia de situación fiscal, opinión 32-D, ...).
- ``core/``       : base compartida (config, FIEL, http_client).
- ``utils/``      : parseo XML, metadata, organización, validación.
- ``api/``        : servidores FastAPI (local y hosted).
- ``cli/``        : interfaz de línea de comandos (``sat-dm``).

API pública estable:
    from sat_descarga import descargar_cfdi, FIEL                       # Web Service
    from sat_descarga import descargar_cfdi_ciec, descargar_cfdi_fiel   # portal (CFDIs)
    from sat_descarga import descargar_constancia_ciec, descargar_constancia_fiel
    from sat_descarga import descargar_opinion_ciec, descargar_opinion_fiel
"""

from .webservice.client import descargar_cfdi, verificar_solicitud_existente
from .core.fiel import FIEL
from .webservice.auth import obtener_token
from .webservice.solicitud import solicitar_descarga
from .webservice.verificacion import verificar_solicitud
from .webservice.descarga import descargar_paquete, descargar_todos

# Portal (scraping). Playwright se importa de forma lazy dentro de estas funciones,
# así que re-exportarlas aquí NO requiere el extra `ciec`.
from .portal.cfdi import descargar_cfdi_ciec, descargar_cfdi_fiel
from .portal.constancia import descargar_constancia_ciec, descargar_constancia_fiel
from .portal.opinion import descargar_opinion_ciec, descargar_opinion_fiel

# Listas negras del SAT (Art. 69 y 69-B). Cliente HTTP hacia todoconta-apps.
from .utils.listas_negras import (
    MatchListaNegra,
    ListasMetadata,
    consultar_rfcs,
    consultar_metadata,
    detectar_edos,
)

__all__ = [
    "descargar_cfdi",
    "verificar_solicitud_existente",
    "FIEL",
    "obtener_token",
    "solicitar_descarga",
    "verificar_solicitud",
    "descargar_paquete",
    "descargar_todos",
    "descargar_cfdi_ciec",
    "descargar_cfdi_fiel",
    "descargar_constancia_ciec",
    "descargar_constancia_fiel",
    "descargar_opinion_ciec",
    "descargar_opinion_fiel",
    "MatchListaNegra",
    "ListasMetadata",
    "consultar_rfcs",
    "consultar_metadata",
    "detectar_edos",
]

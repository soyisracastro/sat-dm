"""
Estado de sesión y helpers compartidos entre los routers del agente local.

Vive aquí todo lo que usa MÁS de un router (`api/routers/*`):
- `_session` — sesión FIEL en memoria (un usuario a la vez en el agente local).
- `_get_fiel` / `_renovar_token` / `_limpiar_session` — manejo de la e-firma en sesión.
- `_cargar_fiel_empresa` / `_autocargar_empresa_default` — carga de la e.firma desde
  el catálogo de empresas (forman una unidad con `_limpiar_session`, por eso viven
  juntas aquí aunque la autocarga solo la invoque el router de webservice).
- `_descargas_base` — carpeta base de descargas configurada.
- `_registrar_descarga` — registro best-effort en el historial.
- `SolicitudRequest` — único modelo Pydantic compartido entre routers
  (lo usan `/solicitar` en webservice y `/metadata` en utilidades); los demás
  modelos viven en el router de su dominio.

NOTA: server.py re-exporta `_session` y `_limpiar_session` para compatibilidad
con los tests (monkeypatchean/limpian vía `server._limpiar_session()`).
"""

import logging
import os
from datetime import date
from typing import Optional

from fastapi import HTTPException
from pydantic import BaseModel

from ..core.fiel import FIEL
from ..webservice.auth import obtener_token
from ..core.config import TIPO_CFDI, TIPO_EMITIDO

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Estado de sesión (en memoria — un usuario a la vez en el agente local)
# ---------------------------------------------------------------------------

_session: dict = {
    "fiel": None,        # Objeto FIEL cargado
    "rfc": None,         # RFC extraído del certificado
    "cer_path": None,    # Path al .cer
    "key_path": None,    # Path al .key
    "password": None,    # Contraseña de la llave (en memoria, no en disco)
    "es_temp": False,    # True si cer/key son temporales (borrar al limpiar);
                         # False si apuntan a una empresa guardada (NO borrar).
}


def _get_fiel() -> FIEL:
    if _session["fiel"] is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "No hay e-firma cargada. "
                "Llama primero a POST /auth/cargar-fiel con tu .cer y .key"
            ),
        )
    return _session["fiel"]


def _renovar_token() -> str:
    """Obtiene un token fresco del SAT."""
    fiel = _get_fiel()
    token = obtener_token(fiel)
    return token


def _limpiar_session():
    """Limpia el estado de sesión. Solo borra los .cer/.key si eran temporales
    (no toca los de una empresa guardada en ./efirma/)."""
    if _session.get("es_temp"):
        for path_key in ("cer_path", "key_path"):
            path = _session.get(path_key)
            if path:
                try:
                    os.unlink(path)
                except Exception:
                    pass
    _session.update({
        "fiel": None,
        "rfc": None,
        "cer_path": None,
        "key_path": None,
        "password": None,
        "es_temp": False,
    })


def _cargar_fiel_empresa(empresa: dict) -> bool:
    """
    Carga la e.firma de una empresa del catálogo en `_session`.

    `empresa` es el dict de `config_store.get_empresa` (con cer_path/key_path/password).
    Devuelve True si cargó la e.firma; False si la empresa no tiene método FIEL.
    Lanza ValueError si la e.firma está incompleta o no se pudo abrir (cert/llave/contraseña).
    """
    if "fiel" not in empresa.get("metodos", []):
        return False
    cer, key, pwd = empresa.get("cer_path"), empresa.get("key_path"), empresa.get("password")
    if not (cer and key and pwd):
        raise ValueError("La empresa no tiene e.firma completa.")
    fiel = FIEL(cer, key, pwd)  # nota: carga aunque el cert esté vencido (la UI avisa)
    _limpiar_session()
    _session.update({
        "fiel": fiel, "rfc": fiel.rfc, "cer_path": cer,
        "key_path": key, "password": pwd, "es_temp": False,
    })
    # Si la empresa quedó con el RFC como nombre (la extracción del nombre falló
    # al darla de alta, p. ej. cert con Ñ), recupéralo ahora que la FIEL está
    # cargada y tenemos legal_name. Se corrige solo, sin borrar y re-agregar.
    try:
        nombre = fiel.legal_name
        if nombre:
            from ..cli import config_store
            config_store.actualizar_nombre_si_placeholder(fiel.rfc, nombre)
    except Exception as e:  # noqa: BLE001
        logger.debug("No se pudo actualizar el nombre de %s: %s", fiel.rfc, e)
    return True


def _autocargar_empresa_default() -> None:
    """Carga al arranque la e.firma de la empresa predeterminada (si tiene FIEL).

    Se llama desde el lifespan del agente. Tolerante a fallos: si la empresa no
    tiene e.firma, o el cert/llave no se pueden abrir, solo se registra y se sigue
    (la UI permite cargarla a mano)."""
    if _session["fiel"] is not None:
        return
    try:
        from ..cli import config_store
        rfc = config_store.get_default()
        if not rfc:
            return
        if _cargar_fiel_empresa(config_store.get_empresa(rfc)):
            logger.info("e.firma de la empresa activa (%s) cargada al arranque.", rfc)
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo autocargar la e.firma de la empresa activa: %s", e)


# ---------------------------------------------------------------------------
# Helpers compartidos (paths de descargas + historial)
# ---------------------------------------------------------------------------


def _descargas_base() -> str:
    """Carpeta base de descargas configurada (default ~/Documents/TodoConta)."""
    from ..cli import config_store
    return config_store.get_descargas_dir()


def _registrar_descarga(rfc, canal, tipo, descripcion="", ruta="", total=None):
    """Registra una descarga completada en el historial. Best-effort: nunca lanza."""
    try:
        from ..cli import config_store
        config_store.registrar_descarga(
            rfc, canal, tipo, descripcion=descripcion, ruta=ruta, total=total,
        )
    except Exception:  # noqa: BLE001 - el historial no debe romper una descarga
        logger.warning("No se pudo registrar la descarga en el historial", exc_info=True)


# ---------------------------------------------------------------------------
# Modelos compartidos entre routers
# ---------------------------------------------------------------------------


class SolicitudRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    tipo_solicitud: str = TIPO_CFDI       # "CFDI" o "Metadata"
    tipo_comprobante: str = TIPO_EMITIDO  # "E" o "R"
    rfc_emisor: Optional[str] = None
    rfc_receptor: Optional[str] = None

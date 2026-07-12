"""
Almacenamiento seguro de credenciales (contraseña de la e.firma, CIEC, sesión de
todoconta) con dos backends, despachados de forma transparente:

- **Keyring del SO** (default — app de escritorio): Keychain en macOS, Credential
  Manager/DPAPI en Windows, Secret Service en Linux. Las credenciales NUNCA se
  guardan en texto plano en disco — este es el argumento de seguridad de la
  desktop (la e.firma y sus contraseñas se quedan en la máquina del usuario).
- **Archivo cifrado** (`secretos_archivo.py` — modo hosted): dentro de un
  contenedor Docker no hay keychain; si la env `SAT_DM_SECRETS_KEY` está
  presente, los secretos van a `secretos.enc` (AES-256-GCM) en el volumen
  del usuario.

Los llamadores usan las mismas firmas de siempre; el dispatch es interno.
`keyring` se importa de forma lazy para no requerirlo si solo se usa el núcleo
sin persistencia de empresas.
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

# Namespace de este app dentro del keychain del SO.
SERVICE = "sat-dm"

# Métodos de autenticación cuyas credenciales guardamos.
FIEL = "fiel"   # contraseña de la llave privada (.key)
CIEC = "ciec"   # contraseña CIEC del portal
CSD = "csd"     # contraseña de la .key del Certificado de Sello Digital


def _backend_archivo_activo() -> bool:
    return bool(os.environ.get("SAT_DM_SECRETS_KEY"))


def _keyring():
    try:
        import keyring
        return keyring
    except ImportError as e:  # pragma: no cover - depende del entorno
        raise RuntimeError(
            "Se requiere `keyring` para guardar credenciales de forma segura. "
            f"Instálalo (incluido en el extra [server]). Detalle: {e}"
        )


def _clave(rfc: str, metodo: str) -> str:
    return f"{metodo}:{rfc.strip().upper()}"


def guardar(rfc: str, metodo: str, secreto: str) -> None:
    """Guarda la credencial (`metodo` = FIEL | CIEC | CSD) en el backend activo."""
    guardar_blob(SERVICE, _clave(rfc, metodo), secreto)


def obtener(rfc: str, metodo: str) -> Optional[str]:
    """Recupera la credencial, o None si no existe / falla el backend."""
    try:
        return obtener_blob(SERVICE, _clave(rfc, metodo))
    except Exception as e:  # noqa: BLE001 - backend no disponible, clave mala, etc.
        logger.warning("[secretos] no se pudo leer %s: %s", _clave(rfc, metodo), e)
        return None


def borrar(rfc: str, metodo: str) -> None:
    """Borra la credencial (no falla si no existe)."""
    borrar_blob(SERVICE, _clave(rfc, metodo))


# ---------------------------------------------------------------------------
# API genérica (blobs con servicio/usuario propios)
#
# Para secretos que no son credenciales de una empresa — p. ej. la sesión de
# Supabase que persiste license_client bajo el servicio "com.todoconta.desktop".
# Mismo dispatch keyring/archivo que la API por RFC.
# ---------------------------------------------------------------------------


def guardar_blob(servicio: str, usuario: str, valor: str) -> None:
    """Guarda un secreto genérico en el backend activo. Falla con RuntimeError
    si el backend no está disponible (keyring ausente / clave inválida)."""
    if _backend_archivo_activo():
        from . import secretos_archivo

        secretos_archivo.guardar(servicio, usuario, valor)
        return
    _keyring().set_password(servicio, usuario, valor)


def obtener_blob(servicio: str, usuario: str) -> Optional[str]:
    """Recupera un secreto genérico, o None si no existe. A diferencia de
    `obtener()`, los errores del backend se propagan (el caller decide)."""
    if _backend_archivo_activo():
        from . import secretos_archivo

        return secretos_archivo.obtener(servicio, usuario)
    return _keyring().get_password(servicio, usuario)


def borrar_blob(servicio: str, usuario: str) -> None:
    """Borra un secreto genérico (best-effort, nunca falla)."""
    try:
        if _backend_archivo_activo():
            from . import secretos_archivo

            secretos_archivo.borrar(servicio, usuario)
            return
        _keyring().delete_password(servicio, usuario)
    except Exception:  # noqa: BLE001 - no existía o backend sin soporte
        pass

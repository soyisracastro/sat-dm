"""
Almacenamiento seguro de credenciales (contraseña de la e.firma, CIEC) en el
keychain del sistema operativo.

Usa `keyring`: Keychain en macOS, Credential Manager/DPAPI en Windows, Secret
Service en Linux. Las credenciales NUNCA se guardan en texto plano en disco — este
es el argumento de seguridad de la app de escritorio (la e.firma y sus contraseñas
se quedan en la máquina del usuario, protegidas por el SO).

`keyring` se importa de forma lazy para no requerirlo si solo se usa el núcleo sin
persistencia de empresas.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Namespace de este app dentro del keychain del SO.
SERVICE = "sat-dm"

# Métodos de autenticación cuyas credenciales guardamos.
FIEL = "fiel"   # contraseña de la llave privada (.key)
CIEC = "ciec"   # contraseña CIEC del portal


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
    """Guarda la credencial (`metodo` = FIEL | CIEC) en el keychain del SO."""
    _keyring().set_password(SERVICE, _clave(rfc, metodo), secreto)


def obtener(rfc: str, metodo: str) -> Optional[str]:
    """Recupera la credencial del keychain, o None si no existe / falla el backend."""
    try:
        return _keyring().get_password(SERVICE, _clave(rfc, metodo))
    except Exception as e:  # noqa: BLE001 - backend no disponible, etc.
        logger.warning("[secretos] no se pudo leer %s: %s", _clave(rfc, metodo), e)
        return None


def borrar(rfc: str, metodo: str) -> None:
    """Borra la credencial del keychain (no falla si no existe)."""
    try:
        _keyring().delete_password(SERVICE, _clave(rfc, metodo))
    except Exception:  # noqa: BLE001 - no existía o backend sin soporte
        pass

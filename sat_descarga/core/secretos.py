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


# El Credential Manager de Windows (CredWrite) rechaza blobs de más de 2560
# bytes (CRED_MAX_CREDENTIAL_BLOB_SIZE) y keyring codifica el valor en UTF-16
# (~2 bytes por carácter): un secreto de más de ~1280 caracteres truena con
# WinError 1783 «El fragmento ha recibido datos incorrectos». Le pasaba a la
# sesión de Supabase (JWT + refresh token, varios KB) al guardarse en
# /auth/oauth/callback (TODOCONTA-DESKTOP-1G). Los valores largos se parten en
# pedazos bajo el límite, guardados como entradas hermanas del keyring; la
# entrada principal queda con un centinela que dice cuántos pedazos hay.
_CHUNK_CHARS = 1200
_CHUNK_MARCA = "__sat-dm-chunks__:"


def _usuario_chunk(usuario: str, i: int) -> str:
    return f"{usuario}__chunk{i}"


def _borrar_chunks(kr, servicio: str, usuario: str, desde: int) -> None:
    """Borra entradas de pedazos desde el índice `desde` en adelante (restos de
    un valor anterior más largo). Se detiene en el primer índice ausente."""
    i = desde
    while kr.get_password(servicio, _usuario_chunk(usuario, i)) is not None:
        try:
            kr.delete_password(servicio, _usuario_chunk(usuario, i))
        except Exception:  # noqa: BLE001 - carrera con otro borrado; no es fatal
            break
        i += 1


def guardar_blob(servicio: str, usuario: str, valor: str) -> None:
    """Guarda un secreto genérico en el backend activo. Falla con RuntimeError
    si el backend no está disponible (keyring ausente / clave inválida)."""
    if _backend_archivo_activo():
        from . import secretos_archivo

        secretos_archivo.guardar(servicio, usuario, valor)
        return
    kr = _keyring()
    if len(valor) <= _CHUNK_CHARS:
        kr.set_password(servicio, usuario, valor)
        _borrar_chunks(kr, servicio, usuario, desde=0)
        return
    pedazos = [valor[i : i + _CHUNK_CHARS] for i in range(0, len(valor), _CHUNK_CHARS)]
    # Primero los pedazos y al final el centinela: un lector concurrente nunca
    # ve el centinela apuntando a pedazos que aún no existen.
    for i, pedazo in enumerate(pedazos):
        kr.set_password(servicio, _usuario_chunk(usuario, i), pedazo)
    kr.set_password(servicio, usuario, f"{_CHUNK_MARCA}{len(pedazos)}")
    _borrar_chunks(kr, servicio, usuario, desde=len(pedazos))


def obtener_blob(servicio: str, usuario: str) -> Optional[str]:
    """Recupera un secreto genérico, o None si no existe. A diferencia de
    `obtener()`, los errores del backend se propagan (el caller decide)."""
    if _backend_archivo_activo():
        from . import secretos_archivo

        return secretos_archivo.obtener(servicio, usuario)
    kr = _keyring()
    valor = kr.get_password(servicio, usuario)
    if valor is None or not valor.startswith(_CHUNK_MARCA):
        return valor
    try:
        n = int(valor[len(_CHUNK_MARCA):])
    except ValueError:
        return None
    partes = []
    for i in range(n):
        pedazo = kr.get_password(servicio, _usuario_chunk(usuario, i))
        if pedazo is None:  # borrado parcial: el secreto ya no está completo
            return None
        partes.append(pedazo)
    return "".join(partes)


def borrar_blob(servicio: str, usuario: str) -> None:
    """Borra un secreto genérico (best-effort, nunca falla)."""
    try:
        if _backend_archivo_activo():
            from . import secretos_archivo

            secretos_archivo.borrar(servicio, usuario)
            return
        kr = _keyring()
        _borrar_chunks(kr, servicio, usuario, desde=0)
        kr.delete_password(servicio, usuario)
    except Exception:  # noqa: BLE001 - no existía o backend sin soporte
        pass

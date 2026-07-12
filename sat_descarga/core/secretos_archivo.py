"""
Backend de secretos en archivo cifrado, para entornos sin keychain del SO
(modo hosted: el agente corre en un contenedor Docker en el VPS).

Todos los secretos viven en UN archivo (`secretos.enc`) dentro del directorio de
configuración (`~/.sat-descarga`). El contenido es un JSON
`{"servicio\\x00usuario": secreto}` cifrado archivo-completo con AES-256-GCM:
nonce fresco de 12 bytes por escritura + ciphertext con tag de autenticación.
La clave (32 bytes, base64) llega por la env `SAT_DM_SECRETS_KEY` — en el VPS la
deriva el provisioner por usuario desde una master key, así que recrear el
contenedor (p. ej. al actualizar la imagen) conserva el acceso a los secretos.

Este módulo NO decide cuándo usarse: `core/secretos.py` despacha aquí cuando
`SAT_DM_SECRETS_KEY` está presente, y al keyring del SO cuando no.
"""

import base64
import json
import logging
import os
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

ARCHIVO = "secretos.enc"
_NONCE_LEN = 12

# El agente atiende requests concurrentes (poller + UI): el read-modify-write
# del archivo va bajo lock, igual que en config_store.
_lock = threading.RLock()


def _clave_aes() -> bytes:
    raw = os.environ.get("SAT_DM_SECRETS_KEY", "")
    if not raw:
        raise RuntimeError(
            "SAT_DM_SECRETS_KEY no está en el entorno; el backend de secretos "
            "en archivo solo aplica en modo hosted."
        )
    try:
        clave = base64.b64decode(raw, validate=True)
    except Exception as e:
        raise RuntimeError(f"SAT_DM_SECRETS_KEY no es base64 válido: {e}")
    if len(clave) != 32:
        raise RuntimeError(
            f"SAT_DM_SECRETS_KEY debe decodificar a 32 bytes (AES-256); "
            f"llegaron {len(clave)}."
        )
    return clave


def _ruta_archivo() -> Path:
    # Import lazy para no crear un ciclo: cli/config_store importa core/secretos,
    # que a su vez importa este módulo dentro de sus funciones. CONFIG_DIR es la
    # única fuente de verdad del directorio de configuración — así el archivo de
    # secretos sigue al catálogo también en tests (que monkeypatchean CONFIG_DIR).
    from ..cli import config_store

    return config_store.get_config_dir() / ARCHIVO


def _id(servicio: str, usuario: str) -> str:
    return f"{servicio}\x00{usuario}"


def _leer_todo() -> dict:
    path = _ruta_archivo()
    if not path.exists():
        return {}
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    blob = path.read_bytes()
    if len(blob) <= _NONCE_LEN:
        logger.warning("[secretos] %s truncado; se trata como vacío", path.name)
        return {}
    aes = AESGCM(_clave_aes())
    try:
        plano = aes.decrypt(blob[:_NONCE_LEN], blob[_NONCE_LEN:], None)
    except Exception as e:
        # Clave incorrecta o archivo alterado: error duro con pista — degradarlo
        # a "no hay credenciales" dejaría al usuario sin saber por qué.
        raise RuntimeError(
            "No se pudo descifrar secretos.enc (¿cambió SAT_DM_SECRETS_KEY?)."
        ) from e
    return json.loads(plano.decode("utf-8"))


def _escribir_todo(datos: dict) -> None:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    path = _ruta_archivo()
    aes = AESGCM(_clave_aes())
    nonce = os.urandom(_NONCE_LEN)
    plano = json.dumps(datos, ensure_ascii=False).encode("utf-8")
    blob = nonce + aes.encrypt(nonce, plano, None)
    # Escritura atómica y durable (tmp + fsync + replace), mismo patrón que
    # config_store: un lector concurrente nunca ve el archivo a medias.
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        f.write(blob)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    try:
        os.chmod(path, 0o600)
    except OSError:  # pragma: no cover — p. ej. filesystems sin permisos POSIX
        pass


def guardar(servicio: str, usuario: str, secreto: str) -> None:
    """Guarda (o reemplaza) un secreto en el archivo cifrado."""
    with _lock:
        datos = _leer_todo()
        datos[_id(servicio, usuario)] = secreto
        _escribir_todo(datos)


def obtener(servicio: str, usuario: str) -> Optional[str]:
    """Recupera un secreto, o None si no existe. Clave incorrecta → RuntimeError."""
    with _lock:
        return _leer_todo().get(_id(servicio, usuario))


def borrar(servicio: str, usuario: str) -> None:
    """Borra un secreto (no falla si no existe)."""
    with _lock:
        datos = _leer_todo()
        if datos.pop(_id(servicio, usuario), None) is not None:
            _escribir_todo(datos)

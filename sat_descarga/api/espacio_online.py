"""
Puente con el espacio en línea del usuario (su agente personal en la nube).

"Subir credenciales al espacio": la e.firma/CIEC de una empresa viaja cifrada
(HTTPS) DIRECTO del equipo del usuario a su contenedor personal — exactamente
el mismo lugar donde quedan cuando las captura en la versión web. NUNCA tocan
la base de datos compartida ni servicios de terceros: el destino es la misma
alta autenticada que usa la web (/empresas/fiel, /empresas/ciec) contra el
agente remoto del usuario.

El provisioner resuelve (con la sesión de la cuenta) dónde vive ese espacio y
lo enciende si estaba apagado — funciona aunque el usuario nunca haya abierto
la versión web.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

PROVISIONER_URL = os.environ.get(
    "TODOCONTA_PROVISIONER_URL", "https://agente.todoconta.com"
).rstrip("/")

_TIMEOUT = 30


class EspacioOnlineError(RuntimeError):
    """Error con mensaje en español apto para mostrarse al usuario final."""


def _conectar_espacio() -> tuple[str, str]:
    """Resuelve (base_url, token) del agente online del usuario vía provisioner."""
    from . import license_client as lc

    session = lc.load_session()
    if session is None:
        raise EspacioOnlineError(
            "Inicia sesión en tu cuenta para poder usar tu espacio en línea."
        )

    def _pedir(s):
        return requests.post(
            f"{PROVISIONER_URL}/provision/con-token",
            json={"access_token": s.access_token, "refresh_token": s.refresh_token},
            timeout=_TIMEOUT,
        )

    try:
        resp = _pedir(session)
        if resp.status_code == 401:
            nueva = lc.try_refresh_session(session)
            if nueva is None:
                raise EspacioOnlineError("Tu sesión expiró. Vuelve a iniciar sesión.")
            resp = _pedir(nueva)
    except requests.RequestException as e:
        raise EspacioOnlineError(
            "No se pudo contactar tu espacio en línea. Revisa tu internet e intenta de nuevo."
        ) from e

    if resp.status_code in (401, 403):
        try:
            detalle = resp.json().get("detail")
        except ValueError:
            detalle = None
        raise EspacioOnlineError(
            detalle or "Tu cuenta no tiene acceso a la versión web por el momento."
        )
    if resp.status_code != 200:
        raise EspacioOnlineError(
            "Tu espacio en línea no está disponible en este momento. Intenta más tarde."
        )
    data = resp.json()
    return data["base_url"].rstrip("/"), data["token"]


def _validar_alta(resp: requests.Response, que: str) -> None:
    if resp.status_code == 200:
        return
    detalle = None
    try:
        detalle = resp.json().get("detail")
    except ValueError:
        pass
    logger.warning("[espacio] alta de %s respondió %s: %s", que, resp.status_code, detalle)
    raise EspacioOnlineError(
        detalle or f"Tu espacio no pudo guardar la {que}. Intenta más tarde."
    )


def subir_credenciales(rfc: str, metodos: list[str]) -> dict:
    """
    Sube las credenciales locales de la empresa a su espacio en línea.
    `metodos` ⊆ {"fiel", "ciec"}. Devuelve {"ok": True, "subidos": [...]}.
    Lanza KeyError si el RFC no existe y EspacioOnlineError con mensaje de
    usuario en cualquier otro problema.
    """
    from ..cli import config_store

    empresa = config_store.get_empresa(rfc)  # KeyError si no existe
    base, token = _conectar_espacio()
    headers = {"X-Agent-Token": token}
    subidos: list[str] = []

    if "fiel" in metodos:
        cer = empresa.get("cer_path")
        key = empresa.get("key_path")
        pwd = empresa.get("password")
        if not (cer and key and pwd and os.path.exists(cer) and os.path.exists(key)):
            raise EspacioOnlineError(
                "Esta empresa no tiene la e.firma completa en este equipo."
            )
        try:
            with open(cer, "rb") as fc, open(key, "rb") as fk:
                resp = requests.post(
                    f"{base}/empresas/fiel",
                    headers=headers,
                    files={
                        "cer_file": ("fiel.cer", fc, "application/octet-stream"),
                        "key_file": ("fiel.key", fk, "application/octet-stream"),
                    },
                    data={
                        "password": pwd,
                        "nombre": empresa.get("nombre") or "",
                        # El agente remoto valida que el cert sea de ESTE RFC.
                        "rfc_esperado": rfc,
                    },
                    timeout=60,
                )
        except requests.RequestException as e:
            raise EspacioOnlineError(
                "Se interrumpió la subida de la e.firma. Intenta de nuevo."
            ) from e
        _validar_alta(resp, "e.firma")
        subidos.append("fiel")

    if "ciec" in metodos:
        ciec = empresa.get("ciec")
        if not ciec:
            raise EspacioOnlineError("Esta empresa no tiene CIEC guardada en este equipo.")
        try:
            resp = requests.post(
                f"{base}/empresas/ciec",
                headers=headers,
                json={"rfc": rfc, "nombre": empresa.get("nombre") or "", "ciec": ciec},
                timeout=_TIMEOUT,
            )
        except requests.RequestException as e:
            raise EspacioOnlineError(
                "Se interrumpió la subida de la CIEC. Intenta de nuevo."
            ) from e
        _validar_alta(resp, "CIEC")
        subidos.append("ciec")

    if not subidos:
        raise EspacioOnlineError("No hay credenciales que subir para los métodos elegidos.")
    logger.info("[espacio] credenciales de %s subidas: %s", rfc, subidos)
    return {"ok": True, "subidos": subidos}

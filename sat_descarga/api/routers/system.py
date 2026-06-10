"""
Router: estado del servidor, integración con el SO y auth de licencia.

Endpoints: /health, /abrir, /config/descargas-dir y el auth desktop contra
todoconta-apps (/auth/init, /auth/poll, /auth/license, /auth/upgrade,
/auth/logout).
"""

import os
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..state import _session

router = APIRouter()

# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------


class DescargasDirRequest(BaseModel):
    dir: str


class AbrirRequest(BaseModel):
    ruta: str
    modo: str = "carpeta"  # "carpeta" (abre el folder) | "archivo" (abre el PDF/archivo)


# ---------------------------------------------------------------------------
# Endpoints: estado del servidor
# ---------------------------------------------------------------------------

@router.get("/health")
def health():
    """Verifica que el servidor está corriendo y si hay e-firma cargada.

    Incluye la vigencia de la e-firma en sesión (`efirma_vencimiento` ISO y
    `efirma_vigente`) para que la UI muestre el semáforo de vencimiento.
    """
    fiel = _session["fiel"]
    return {
        "status": "ok",
        "rfc_cargado": _session["rfc"],
        "efirma_lista": fiel is not None,
        "efirma_vencimiento": fiel.not_valid_after.date().isoformat() if fiel else None,
        "efirma_vigente": fiel.vigente if fiel else None,
    }


# ---------------------------------------------------------------------------
# Endpoints: abrir descargas en el SO
# ---------------------------------------------------------------------------

def _abrir_en_so(path: str) -> None:
    """Abre `path` (archivo o carpeta) con el manejador por defecto del SO."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # solo existe en Windows
    else:
        subprocess.Popen(["xdg-open", path])


@router.post("/abrir")
def abrir(req: AbrirRequest):
    """
    Abre en el SO una descarga del historial: su carpeta (`modo=carpeta`) o el
    archivo (`modo=archivo`, p. ej. el PDF de constancia/opinión).

    Seguridad: solo se permiten rutas que estén registradas en el historial
    (no se puede abrir una ruta arbitraria del disco).
    """
    from ...cli import config_store

    # Comparar rutas CANONICALIZADAS (resolve() normaliza ".." y sigue symlinks):
    # así un symlink o una variante de la misma ruta no brinca la lista blanca.
    rutas = set()
    for d in config_store.list_todas_descargas():
        if not d.get("ruta"):
            continue
        try:
            rutas.add(Path(d["ruta"]).resolve())
        except OSError:
            continue

    try:
        objetivo = Path(req.ruta).resolve()
    except OSError:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    if objetivo not in rutas:
        raise HTTPException(status_code=403, detail="Ruta no permitida (no está en el historial).")

    if req.modo == "carpeta" and objetivo.is_file():
        objetivo = objetivo.parent
    if not objetivo.exists():
        raise HTTPException(status_code=404, detail="La ruta ya no existe (¿se movió o borró?).")

    try:
        _abrir_en_so(str(objetivo))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"No se pudo abrir: {e}")
    return {"ok": True, "ruta": str(objetivo)}


# ---------------------------------------------------------------------------
# Endpoints: ajustes (carpeta de descargas)
# ---------------------------------------------------------------------------

@router.get("/config/descargas-dir")
def get_descargas_dir_endpoint():
    """Carpeta base donde se guardan las descargas (se crea si no existe)."""
    from ...cli import config_store
    return {"dir": config_store.asegurar_descargas_dir()}


@router.put("/config/descargas-dir")
def set_descargas_dir_endpoint(req: DescargasDirRequest):
    """Cambia la carpeta base de descargas."""
    from ...cli import config_store
    return {"dir": config_store.set_descargas_dir(req.dir)}


# ---------------------------------------------------------------------------
# Auth desktop — proxy + cache hacia todoconta-apps (/api/desktop/*)
# ---------------------------------------------------------------------------
#
# La desktop guarda el Bearer token de Supabase en el keyring del SO (vía
# `license_client`) y expone helpers al renderer para login, license check
# y upgrade a Fundador. El Bearer NUNCA se inyecta al renderer — vive solo
# en el proceso Python; el renderer solo conoce el estado derivado (autenticado,
# is_founder, etc.). Esto reduce la superficie de un XSS en el renderer.


class AuthPollRequest(BaseModel):
    device_code: str


@router.post("/auth/init")
def auth_init():
    """
    Genera un device_code y lo registra en el backend de todoconta-apps.
    Devuelve el code + el URL público que el usuario tiene que abrir.
    """
    from .. import license_client as lc

    code = lc.generate_device_code()
    try:
        result = lc.init_device_code(code)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "device_code": code,
        "expires_at": result.get("expires_at"),
        "activate_url": f"{lc.API_BASE_URL}/desktop/activate?code={code}",
    }


@router.post("/auth/poll")
def auth_poll(req: AuthPollRequest):
    """
    Polling del device_code. Devuelve `{status, ...}` con:
      - status=pending → el usuario aún no completó.
      - status=ok      → activado, sesión guardada en keyring.
      - status=expired → device_code expirado.
      - status=not_found → device_code desconocido.
    """
    from .. import license_client as lc

    try:
        result, session = lc.poll_device_code(req.device_code)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if result == "ok" and session is not None:
        lc.save_session(session)
        # Invalidamos el cache de license para que la próxima lectura
        # refleje al usuario recién logueado.
        lc.clear_license_cache()
        return {"status": "ok", "user": {"id": session.user_id, "email": session.email}}

    return {"status": result}


@router.get("/auth/license")
def auth_license(refresh: bool = False):
    """
    Estado de licencia/fundador del usuario actual. Si no hay sesión:
    `{authenticated: false}`. Si hay y la cache es fresh, la devuelve sin
    pegarle al backend.
    """
    from .. import license_client as lc

    status = lc.get_license_status(force_refresh=refresh)
    # El payload remoto/cacheado puede no traer email; la sesión local sí lo
    # tiene (el renderer lo muestra en el menú de cuenta del sidebar).
    if status.get("authenticated") and not status.get("email"):
        session = lc.load_session()
        if session and session.email:
            status["email"] = session.email
    return status


@router.post("/auth/upgrade")
def auth_upgrade():
    """
    Crea una sesión de Stripe Checkout para que el usuario se vuelva Fundador.
    Devuelve `{url}`; el renderer abre el URL en el navegador del SO.
    """
    from .. import license_client as lc

    session = lc.load_session()
    if session is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        result = lc.init_checkout(session)
    except PermissionError:
        # Sesión expirada: limpiamos y obligamos a re-login.
        lc.clear_session()
        raise HTTPException(status_code=401, detail="Sesión expirada, vuelve a iniciar sesión")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


@router.post("/auth/logout")
def auth_logout():
    """Borra la sesión local (keyring + cache). Idempotente."""
    from .. import license_client as lc

    lc.clear_session()
    return {"ok": True}

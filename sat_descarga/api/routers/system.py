"""
Router: estado del servidor, integración con el SO y auth de licencia.

Endpoints: /health, /abrir, /config/descargas-dir y el auth desktop:
- Directo contra Supabase (login en-app): /auth/login-password, /auth/otp-send,
  /auth/otp-verify, /auth/signup.
- Contra todoconta-apps: /auth/license, /auth/upgrade, /auth/logout, y el
  device-code flow legado (/auth/init, /auth/poll) que queda como fallback.
"""

import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...core.config import es_modo_hosted
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
    `efirma_vigente`) para que la UI muestre el semáforo de vencimiento, y el
    estado del navegador del portal (`navegador`) para el banner de
    "preparando el navegador…" mientras el warm-up descarga Chromium.
    """
    fiel = _session["fiel"]
    try:
        from ...portal.setup import estado_navegador

        navegador = estado_navegador()
    except Exception:
        # Instalación sin playwright (extra [ciec] ausente): /health nunca truena.
        navegador = {"estado": "desconocido", "detalle": None}
    return {
        "status": "ok",
        "modo": "hosted" if es_modo_hosted() else "desktop",
        "rfc_cargado": _session["rfc"],
        "efirma_lista": fiel is not None,
        "efirma_vencimiento": fiel.not_valid_after.date().isoformat() if fiel else None,
        "efirma_vigente": fiel.vigente if fiel else None,
        "navegador": navegador,
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
    if es_modo_hosted():
        # En la web no hay SO del usuario que abrir: el navegador descarga el
        # archivo/ZIP vía los endpoints /descargas/*.
        raise HTTPException(
            status_code=501,
            detail="En la versión web usa el botón Descargar.",
        )
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


class LoginPasswordRequest(BaseModel):
    email: str
    password: str


class OtpSendRequest(BaseModel):
    email: str
    crear_cuenta: bool = False
    nombre: str = ""
    tipo: str = "email"  # "email" (login/registro por código) | "signup" (reenviar confirmación)


class OtpVerifyRequest(BaseModel):
    email: str
    token: str
    tipo: str = "email"  # "email" (login/registro por código) | "signup" (confirmar registro)


class SignupRequest(BaseModel):
    email: str
    password: str
    nombre: str = ""


class OauthStartRequest(BaseModel):
    provider: str = "google"


class OauthCallbackRequest(BaseModel):
    code: str


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


# --- Auth directa contra Supabase (login en-app, sin navegador) -------------
#
# Reemplaza al device-code flow como camino principal: la sesión resultante
# son los mismos JWT de Supabase y se guarda igual en el keyring, así que
# /auth/license y el checkout siguen funcionando sin cambios. Los endpoints
# /auth/init y /auth/poll se conservan como fallback (la página de activación
# web sigue viva), pero la UI ya no los usa.


def _guardar_sesion(session) -> dict:
    from .. import license_client as lc

    lc.save_session(session)
    lc.clear_license_cache()
    return {"ok": True, "user": {"id": session.user_id, "email": session.email}}


def _http_de_auth_error(e) -> HTTPException:
    # 4xx de GoTrue viajan con su mensaje ya en español; 5xx/red como 502.
    status = e.status if 400 <= e.status < 500 else 502
    return HTTPException(status_code=status, detail=e.mensaje)


@router.post("/auth/login-password")
def auth_login_password(req: LoginPasswordRequest):
    """Login con correo + contraseña. Guarda la sesión en el keyring."""
    from .. import supabase_auth as sa

    try:
        session = sa.login_password(req.email.strip(), req.password)
    except sa.SupabaseAuthError as e:
        raise _http_de_auth_error(e)
    return _guardar_sesion(session)


@router.post("/auth/otp-send")
def auth_otp_send(req: OtpSendRequest):
    """
    Envía un código de 6 dígitos al correo. Con `crear_cuenta=true` el código
    también registra al usuario (registro por código, con `nombre` opcional).
    Con `tipo="signup"` reenvía la confirmación de un registro con contraseña.
    """
    from .. import supabase_auth as sa

    try:
        if req.tipo == "signup":
            sa.signup_resend(req.email.strip())
        else:
            sa.otp_send(req.email.strip(), crear_cuenta=req.crear_cuenta, nombre=req.nombre.strip())
    except sa.SupabaseAuthError as e:
        raise _http_de_auth_error(e)
    return {"ok": True}


@router.post("/auth/otp-verify")
def auth_otp_verify(req: OtpVerifyRequest):
    """Verifica el código tecleado en la app y guarda la sesión."""
    from .. import supabase_auth as sa

    try:
        session = sa.otp_verify(req.email.strip(), req.token.strip(), tipo=req.tipo)
    except sa.SupabaseAuthError as e:
        raise _http_de_auth_error(e)
    return _guardar_sesion(session)


@router.post("/auth/signup")
def auth_signup(req: SignupRequest):
    """
    Registro con correo + contraseña. Si Supabase exige confirmar el correo
    (default), devuelve `requiere_confirmacion=true` y la UI pasa al paso de
    código con tipo="signup".
    """
    from .. import supabase_auth as sa

    try:
        session, requiere_confirmacion = sa.signup(
            req.email.strip(), req.password, nombre=req.nombre.strip()
        )
    except sa.SupabaseAuthError as e:
        raise _http_de_auth_error(e)
    if session is not None:
        return {**_guardar_sesion(session), "requiere_confirmacion": False}
    return {"ok": True, "requiere_confirmacion": True}


# --- OAuth (Google) con PKCE, vía deep link `todoconta://auth-callback` ------
#
# El agente es el broker: /start arma la URL de /authorize (el renderer la abre
# en el navegador del SO) y guarda el code_verifier; cuando Supabase regresa el
# `auth_code` por el deep link, /callback lo canjea por la sesión. El desktop es
# mono-usuario con un solo login a la vez, así que el verifier en vuelo cabe en
# una variable de módulo (no persistente: si el agente reinicia a media
# autenticación, el usuario reintenta).

_OAUTH_REDIRECT = "todoconta://auth-callback"
_pkce_verifier = None


@router.post("/auth/oauth/start")
def auth_oauth_start(req: OauthStartRequest):
    """
    Inicia el OAuth con Google (PKCE). Devuelve la URL de `/authorize` que el
    renderer abre en el navegador del SO y guarda el code_verifier hasta el
    callback.
    """
    global _pkce_verifier
    from .. import supabase_auth as sa

    try:
        url, verifier = sa.oauth_authorize_url(_OAUTH_REDIRECT, provider=req.provider)
    except sa.SupabaseAuthError as e:
        raise _http_de_auth_error(e)
    _pkce_verifier = verifier
    return {"url": url}


@router.post("/auth/oauth/callback")
def auth_oauth_callback(req: OauthCallbackRequest):
    """
    Canjea el `auth_code` del deep link por la sesión y la guarda en el keyring.
    Una cuenta @gmail existente (creada por OTP) se vincula automáticamente al
    mismo usuario en Supabase (mismo email verificado) — sin lógica aquí.
    """
    global _pkce_verifier
    from .. import supabase_auth as sa

    verifier = _pkce_verifier
    if not verifier:
        raise HTTPException(
            status_code=400,
            detail="El acceso con Google expiró. Vuelve a intentarlo.",
        )
    try:
        session = sa.oauth_exchange(req.code.strip(), verifier)
    except sa.SupabaseAuthError as e:
        raise _http_de_auth_error(e)
    finally:
        _pkce_verifier = None
    return _guardar_sesion(session)


# --- Adopción de sesión (solo modo hosted) -----------------------------------
#
# En la versión web el PRIMER login ocurre fuera del agente (lo hace el
# provisioner contra Supabase, antes de que el navegador conozca este
# contenedor). La UI entrega aquí los tokens resultantes para que la sesión
# quede persistida igual que tras un login local — y /auth/license, el poller y
# el checkout funcionen sin cambios. En modo desktop este endpoint no existe.


class AdoptSessionRequest(BaseModel):
    access_token: str
    refresh_token: Optional[str] = None
    user_id: str
    email: Optional[str] = None


@router.post("/auth/adopt-session")
def auth_adopt_session(req: AdoptSessionRequest):
    """(Solo hosted) Persiste una sesión de Supabase ya autenticada por el provisioner."""
    if not es_modo_hosted():
        raise HTTPException(status_code=404, detail="Not Found")
    from .. import license_client as lc

    session = lc.Session(
        access_token=req.access_token,
        refresh_token=req.refresh_token,
        user_id=req.user_id,
        email=req.email,
    )
    return _guardar_sesion(session)


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


def _accion_con_refresh(fn):
    """
    Ejecuta `fn(session)` (una acción de license_client que pega al backend con
    Bearer) aplicando el patrón estándar: si el Bearer expiró (PermissionError)
    intenta `try_refresh_session` ANTES de desloguear; si el refresh tampoco
    salva, limpia la sesión. Los errores del backend (RuntimeError) → 502.
    """
    from .. import license_client as lc

    session = lc.load_session()
    if session is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        return fn(session)
    except PermissionError:
        nueva = lc.try_refresh_session(session)
        if nueva is None:
            lc.clear_session()
            raise HTTPException(status_code=401, detail="Sesión expirada, vuelve a iniciar sesión")
        try:
            return fn(nueva)
        except PermissionError:
            lc.clear_session()
            raise HTTPException(status_code=401, detail="Sesión expirada, vuelve a iniciar sesión")
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.post("/auth/upgrade")
def auth_upgrade():
    """
    Crea una sesión de Stripe Checkout para que el usuario se vuelva Fundador.
    Devuelve `{url}`; el renderer abre el URL en el navegador del SO.
    """
    from .. import license_client as lc

    return _accion_con_refresh(lc.init_checkout)


@router.post("/auth/subscribe")
def auth_subscribe():
    """
    Crea la Stripe Checkout session de la suscripción anual de TodoConta Desktop.
    Devuelve `{url, session_id, promo}`; el renderer abre el URL en el navegador.
    """
    from .. import license_client as lc

    return _accion_con_refresh(lc.init_subscribe_checkout)


@router.post("/auth/cancel-subscription")
def auth_cancel_subscription():
    """
    Cancela la suscripción al fin del periodo. Devuelve `{ok, cancel_at, manual}`.
    """
    from .. import license_client as lc

    return _accion_con_refresh(lc.cancel_subscription)


@router.post("/auth/transfer-intent")
def auth_transfer_intent():
    """
    Registra la intención de pago por transferencia y devuelve los datos
    bancarios. `{ok, amount_mxn, promo, banco, message}`.
    """
    from .. import license_client as lc

    return _accion_con_refresh(lc.create_transfer_intent)


@router.post("/auth/logout")
def auth_logout():
    """Borra la sesión local (keyring + cache). Idempotente."""
    from .. import license_client as lc

    lc.clear_session()
    return {"ok": True}

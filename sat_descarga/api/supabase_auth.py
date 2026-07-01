"""
Auth directa contra Supabase (GoTrue REST) — login en-app estilo Notion.

El proyecto Supabase es el MISMO que usa todoconta-apps (app.todoconta.com):
cualquier usuario registrado en la web entra al desktop y viceversa. El
trigger `on_auth_user_created` de la DB crea el profile automáticamente, así
que el signup directo desde aquí también funciona con `/api/desktop/license`.

Flujos expuestos (consumidos por los endpoints /auth/* de routers/system.py):
- `login_password(email, password)`      → POST /token?grant_type=password
- `otp_send(email, crear_cuenta, nombre)`→ POST /otp (código de 6 dígitos al correo)
- `otp_verify(email, token, tipo)`       → POST /verify (type=email|signup)
- `signup(email, password, nombre)`      → POST /signup (confirmación por código)
- `refresh(refresh_token)`               → POST /token?grant_type=refresh_token

La anon key es pública por diseño (viaja en el bundle JS de la web); aquí va
hardcodeada con override por env para apuntar a otro proyecto en dev/tests.

Nota de despliegue: para que el usuario pueda TECLEAR el código en la app, los
templates de email de Supabase (Magic Link y Confirm signup) deben incluir
`{{ .Token }}` además del link.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import os
import secrets
from typing import Optional
from urllib.parse import urlencode

import requests

from .license_client import Session

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get(
    "TODOCONTA_SUPABASE_URL", "https://pyyyzvicjpffohwjsmzi.supabase.co"
).rstrip("/")
SUPABASE_ANON_KEY = os.environ.get(
    "TODOCONTA_SUPABASE_ANON_KEY",
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9."
    "eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB5eXl6dmljanBmZm9od2pzbXppIiwicm9sZSI6"
    "ImFub24iLCJpYXQiOjE3NjgxNjAyNjIsImV4cCI6MjA4MzczNjI2Mn0."
    "kkOVRZu-u1Iyn6jOqoA7ti5crKJFqgCulsGtOodrLQQ",
)

_TIMEOUT = 15


class SupabaseAuthError(Exception):
    """Error de GoTrue ya traducido a mensaje para el usuario."""

    def __init__(self, mensaje: str, status: int = 400, error_code: str = ""):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.status = status
        self.error_code = error_code


# Mensajes en español por error_code de GoTrue. El default es el msg crudo.
_MENSAJES = {
    "invalid_credentials": "Correo o contraseña incorrectos.",
    "email_not_confirmed": (
        "Tu correo aún no está confirmado. Entra con un código de acceso "
        "para confirmarlo."
    ),
    "otp_expired": "El código expiró o no es válido. Pide uno nuevo.",
    "otp_disabled": "No encontramos una cuenta con ese correo. Crea tu cuenta primero.",
    "user_already_exists": "Ya existe una cuenta con ese correo. Inicia sesión.",
    "email_exists": "Ya existe una cuenta con ese correo. Inicia sesión.",
    "weak_password": "La contraseña es demasiado corta o común. Usa mínimo 8 caracteres.",
    "validation_failed": "Revisa el correo: no parece válido.",
    "over_email_send_rate_limit": (
        "Demasiados intentos. Espera un minuto y vuelve a intentar."
    ),
    "over_request_rate_limit": (
        "Demasiados intentos. Espera un momento y vuelve a intentar."
    ),
    "refresh_token_not_found": "La sesión expiró. Vuelve a iniciar sesión.",
    "signup_disabled": "El registro está deshabilitado por el momento.",
    # Flujo OAuth (Google) con PKCE: el code/verifier no cuadran o el flow expiró.
    "bad_code_verifier": "No pudimos completar el acceso con Google. Intenta de nuevo.",
    "bad_oauth_state": "No pudimos completar el acceso con Google. Intenta de nuevo.",
    "flow_state_not_found": "El acceso con Google expiró. Vuelve a intentarlo.",
    "flow_state_expired": "El acceso con Google expiró. Vuelve a intentarlo.",
    "provider_disabled": "El acceso con Google no está disponible por el momento.",
}


def _raise_de_respuesta(resp: requests.Response) -> None:
    """Traduce el error de GoTrue a SupabaseAuthError con mensaje en español."""
    try:
        data = resp.json()
    except ValueError:
        data = {}
    # GoTrue moderno: {code, error_code, msg}; el endpoint /token a veces usa
    # el formato OAuth {error, error_description}.
    error_code = data.get("error_code") or data.get("error") or ""
    msg = data.get("msg") or data.get("error_description") or resp.text
    if error_code == "invalid_grant" or "Invalid login credentials" in str(msg):
        error_code = "invalid_credentials"
    mensaje = _MENSAJES.get(error_code)
    if mensaje is None:
        logger.warning("[supabase] error sin traducción (%s): %s", error_code, msg)
        mensaje = "No pudimos completar la operación. Intenta de nuevo."
    raise SupabaseAuthError(mensaje, status=resp.status_code, error_code=error_code)


def _post(path: str, payload: dict, params: Optional[dict] = None) -> dict:
    try:
        resp = requests.post(
            f"{SUPABASE_URL}/auth/v1{path}",
            json=payload,
            params=params,
            headers={"apikey": SUPABASE_ANON_KEY},
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        logger.warning("[supabase] %s falló: %s", path, e)
        raise SupabaseAuthError(
            "No pudimos conectar con el servicio de cuentas. Revisa tu internet.",
            status=502,
            error_code="network",
        )
    if resp.status_code >= 400:
        _raise_de_respuesta(resp)
    try:
        return resp.json()
    except ValueError:
        return {}


def _session_de_payload(data: dict) -> Session:
    """Construye la Session local desde la respuesta de GoTrue."""
    user = data.get("user") or {}
    return Session(
        access_token=data["access_token"],
        refresh_token=data.get("refresh_token"),
        user_id=user.get("id", ""),
        email=user.get("email"),
    )


def login_password(email: str, password: str) -> Session:
    """Login con correo + contraseña. Levanta SupabaseAuthError si falla."""
    data = _post(
        "/token", {"email": email, "password": password},
        params={"grant_type": "password"},
    )
    return _session_de_payload(data)


def otp_send(email: str, crear_cuenta: bool = False, nombre: str = "") -> None:
    """
    Envía un código de un solo uso al correo. Con `crear_cuenta=False`, GoTrue
    rechaza correos sin cuenta (otp_disabled) — así un typo no crea cuentas
    fantasma. Con `crear_cuenta=True` el código también registra al usuario.
    """
    payload: dict = {"email": email, "create_user": crear_cuenta}
    if crear_cuenta and nombre:
        payload["data"] = {"full_name": nombre}
    _post("/otp", payload)


def signup_resend(email: str) -> None:
    """Reenvía el código de confirmación de un registro con contraseña."""
    _post("/resend", {"type": "signup", "email": email})


def otp_verify(email: str, token: str, tipo: str = "email") -> Session:
    """
    Verifica el código tecleado en la app. `tipo="email"` para login/registro
    por código; `tipo="signup"` para confirmar un registro con contraseña.
    """
    data = _post("/verify", {"type": tipo, "email": email, "token": token})
    return _session_de_payload(data)


def signup(email: str, password: str, nombre: str = "") -> tuple[Optional[Session], bool]:
    """
    Registro con correo + contraseña. Devuelve `(session, requiere_confirmacion)`:
    con confirmación de email activada (default en Supabase) no hay sesión
    inmediata — GoTrue manda un código y la UI pasa al paso OTP (tipo=signup).

    Ojo: si el correo ya existe, GoTrue devuelve datos faux (sin error) para no
    filtrar qué correos tienen cuenta; el código simplemente nunca llega.
    """
    payload: dict = {"email": email, "password": password}
    if nombre:
        payload["data"] = {"full_name": nombre}
    data = _post("/signup", payload)
    if data.get("access_token"):
        return _session_de_payload(data), False
    return None, True


def refresh(refresh_token: str) -> Session:
    """Renueva la sesión con el refresh_token guardado en el keyring."""
    data = _post(
        "/token", {"refresh_token": refresh_token},
        params={"grant_type": "refresh_token"},
    )
    return _session_de_payload(data)


# ---------------------------------------------------------------------------
# OAuth (Google) con PKCE — flujo del desktop vía deep link `todoconta://`
# ---------------------------------------------------------------------------
#
# El agente es el broker: genera el par verifier/challenge, abre `/authorize`
# en el navegador del SO y, cuando Supabase regresa el `auth_code` por el deep
# link, lo canjea por la sesión (POST /token?grant_type=pkce). El token nunca
# toca el renderer; se guarda en el keyring igual que el flujo OTP. La
# vinculación de una cuenta @gmail existente (creada por OTP) la hace Supabase
# automáticamente por mismo email verificado — aquí no hay lógica de linking.

_PROVIDERS_PERMITIDOS = {"google"}


def _code_verifier() -> str:
    """Genera un code_verifier PKCE (base64url sin padding, ~43 chars)."""
    return base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode("ascii")


def _code_challenge(verifier: str) -> str:
    """Deriva el code_challenge S256 del verifier (base64url sin padding)."""
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def oauth_authorize_url(redirect_to: str, provider: str = "google") -> tuple[str, str]:
    """
    Arma la URL de `/authorize` para iniciar el OAuth con PKCE y devuelve
    `(url, code_verifier)`. El verifier debe guardarse hasta el callback para
    canjear el `auth_code`. Levanta SupabaseAuthError si el provider no está
    soportado.
    """
    if provider not in _PROVIDERS_PERMITIDOS:
        raise SupabaseAuthError(
            "El acceso con Google no está disponible por el momento.",
            status=400,
            error_code="provider_disabled",
        )
    verifier = _code_verifier()
    params = {
        "provider": provider,
        "redirect_to": redirect_to,
        "code_challenge": _code_challenge(verifier),
        "code_challenge_method": "s256",
    }
    url = f"{SUPABASE_URL}/auth/v1/authorize?{urlencode(params)}"
    return url, verifier


def oauth_exchange(auth_code: str, code_verifier: str) -> Session:
    """Canjea el `auth_code` del deep link por una sesión (PKCE)."""
    data = _post(
        "/token",
        {"auth_code": auth_code, "code_verifier": code_verifier},
        params={"grant_type": "pkce"},
    )
    return _session_de_payload(data)

"""
Cliente HTTP del agente local hacia la API de todoconta-apps
(`https://app.todoconta.com/api/desktop/*`), junto con la persistencia segura
del token de sesión en el keyring del SO.

Responsabilidades:
- Generar device codes y orquestar el polling del login.
- Guardar/cargar/borrar el Bearer token en el keyring (no en disco).
- Llamar al backend con el Bearer para license + checkout.
- Cachear el estado de licencia en `~/.sat-descarga/license-cache.json` con
  TTL de 24h y un "grace period" de 30 días offline (la app NO se bloquea si
  el backend está caído; solo se desactualiza el badge de fundador).
"""

from __future__ import annotations

import json
import logging
import os
import random
import string
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import requests

try:
    import keyring  # type: ignore[import-not-found]
except ImportError:  # pragma: no cover — keyring siempre debería estar (core dep)
    keyring = None  # type: ignore[assignment]

from ..cli import config_store

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuración
# ---------------------------------------------------------------------------

API_BASE_URL = os.environ.get(
    "TODOCONTA_API_BASE_URL", "https://app.todoconta.com"
).rstrip("/")

# Servicio en el keyring para los tokens de sesión.
KEYRING_SERVICE = "com.todoconta.desktop"
KEYRING_USER = "session"  # un solo blob JSON

# Path del cache local de license status.
LICENSE_CACHE_PATH = config_store.CONFIG_DIR / "license-cache.json"

# TTL del cache: 24h fresh, 30 días grace (con warning) cuando no hay internet.
CACHE_FRESH_SECONDS = 24 * 60 * 60
CACHE_GRACE_SECONDS = 30 * 24 * 60 * 60

# Device code: 8 chars alfanuméricos (sin 0/O/1/I para evitar confusión).
DEVICE_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
DEVICE_CODE_LEN = 8


# ---------------------------------------------------------------------------
# Sesión (Bearer token + refresh_token en keyring)
# ---------------------------------------------------------------------------


@dataclass
class Session:
    access_token: str
    refresh_token: Optional[str]
    user_id: str
    email: Optional[str]


def _keyring_required() -> None:
    if keyring is None:
        raise RuntimeError(
            "El módulo `keyring` no está disponible. "
            "Reinstala el agente: `pip install keyring`."
        )


def save_session(session: Session) -> None:
    """Persiste la sesión en el keyring del SO."""
    _keyring_required()
    blob = json.dumps(
        {
            "access_token": session.access_token,
            "refresh_token": session.refresh_token,
            "user_id": session.user_id,
            "email": session.email,
        }
    )
    keyring.set_password(KEYRING_SERVICE, KEYRING_USER, blob)


def load_session() -> Optional[Session]:
    """Lee la sesión del keyring. None si no hay sesión guardada."""
    _keyring_required()
    raw = keyring.get_password(KEYRING_SERVICE, KEYRING_USER)
    if not raw:
        return None
    try:
        data = json.loads(raw)
        return Session(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            user_id=data["user_id"],
            email=data.get("email"),
        )
    except (json.JSONDecodeError, KeyError) as e:
        logger.warning("[license] sesión inválida en keyring: %s", e)
        return None


def clear_session() -> None:
    """Borra la sesión del keyring (logout). Tolerante a 'no había nada'."""
    _keyring_required()
    try:
        keyring.delete_password(KEYRING_SERVICE, KEYRING_USER)
    except Exception:  # noqa: BLE001 — keyring varía por SO
        pass
    # También borra el cache de license para no mostrar un badge stale.
    clear_license_cache()


# ---------------------------------------------------------------------------
# Device code (login flow)
# ---------------------------------------------------------------------------


def generate_device_code() -> str:
    """Genera un código alfanumérico aleatorio de 8 chars."""
    return "".join(random.choices(DEVICE_CODE_ALPHABET, k=DEVICE_CODE_LEN))


def init_device_code(device_code: str) -> dict:
    """
    Registra el device_code en el backend. Devuelve `{ok, expires_at}` o
    levanta `RuntimeError` con mensaje del API.
    """
    resp = requests.post(
        f"{API_BASE_URL}/api/desktop/auth/init",
        json={"device_code": device_code},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()
    try:
        detail = resp.json().get("error", resp.text)
    except ValueError:
        detail = resp.text
    raise RuntimeError(f"init_device_code falló ({resp.status_code}): {detail}")


def poll_device_code(device_code: str) -> tuple[str, Optional[Session]]:
    """
    Polling del device code. Devuelve:
        ('pending', None)   → user no completó activación, sigue polling.
        ('ok', Session)     → activado, sesión disponible.
        ('expired', None)   → device code expirado, pedir uno nuevo.
        ('not_found', None) → device code no existe.
    Cualquier otro error levanta RuntimeError.
    """
    resp = requests.post(
        f"{API_BASE_URL}/api/desktop/auth/poll",
        json={"device_code": device_code},
        timeout=10,
    )
    if resp.status_code == 202:
        return "pending", None
    if resp.status_code == 200:
        data = resp.json()
        if data.get("status") == "pending":
            return "pending", None
        session = Session(
            access_token=data["access_token"],
            refresh_token=data.get("refresh_token"),
            user_id=data["user"]["id"],
            email=(data.get("profile") or {}).get("email"),
        )
        return "ok", session
    if resp.status_code == 410:
        return "expired", None
    if resp.status_code == 404:
        return "not_found", None
    try:
        detail = resp.json().get("error", resp.text)
    except ValueError:
        detail = resp.text
    raise RuntimeError(f"poll_device_code falló ({resp.status_code}): {detail}")


# ---------------------------------------------------------------------------
# License (status del usuario)
# ---------------------------------------------------------------------------


def _cache_read() -> Optional[dict]:
    if not LICENSE_CACHE_PATH.exists():
        return None
    try:
        with LICENSE_CACHE_PATH.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def _cache_write(payload: dict) -> None:
    LICENSE_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = LICENSE_CACHE_PATH.with_suffix(".json.tmp")
    with tmp.open("w") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    tmp.replace(LICENSE_CACHE_PATH)


def clear_license_cache() -> None:
    if LICENSE_CACHE_PATH.exists():
        try:
            LICENSE_CACHE_PATH.unlink()
        except OSError:
            pass


def _mensaje_usuario(resp: "requests.Response") -> str:
    """
    Mensaje en español apto para el usuario final a partir de una respuesta
    no-200. Si el backend mandó un mensaje amigable (campo `error`) lo usa tal
    cual; si no (p. ej. una página HTML 404/502 del host), devuelve un texto
    genérico SIN jerga técnica ni HTML.
    """
    try:
        data = resp.json()
    except ValueError:
        data = None
    if isinstance(data, dict):
        msg = data.get("error")
        if isinstance(msg, str) and msg.strip() and "<" not in msg:
            return msg
    if resp.status_code == 404:
        return "Esta función todavía no está disponible. Inténtalo más tarde."
    if resp.status_code >= 500:
        return "Tuvimos un problema de conexión. Inténtalo de nuevo en un momento."
    return "No se pudo completar la operación. Inténtalo de nuevo."


def fetch_license_remote(session: Session) -> dict:
    """Hace GET /api/desktop/license con el Bearer del session."""
    resp = requests.get(
        f"{API_BASE_URL}/api/desktop/license",
        headers={"Authorization": f"Bearer {session.access_token}"},
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 401:
        raise PermissionError("Bearer inválido o expirado")
    logger.warning("[license] license HTTP %s: %s", resp.status_code, resp.text[:200])
    raise RuntimeError(_mensaje_usuario(resp))


def _fetch_license_con_refresh(session: Session) -> dict:
    """
    `fetch_license_remote` con un reintento tras renovar el Bearer. Si el 401
    persiste (o no hay refresh_token utilizable) propaga PermissionError; los
    errores de red se propagan tal cual para que el caller use su cache.
    """
    try:
        return fetch_license_remote(session)
    except PermissionError:
        nueva = try_refresh_session(session)
        if nueva is None:
            raise
        return fetch_license_remote(nueva)


def try_refresh_session(session: Session) -> Optional[Session]:
    """
    Intenta renovar la sesión con el refresh_token guardado en el keyring.
    Devuelve la sesión nueva (ya persistida) o None si no se pudo.

    El access token de Supabase dura ~1h; sin este paso, cualquier 401
    deslogueaba al usuario aunque el refresh_token siguiera siendo válido.
    """
    if not session.refresh_token:
        return None
    # Import diferido: supabase_auth importa Session de este módulo.
    from . import supabase_auth

    try:
        nueva = supabase_auth.refresh(session.refresh_token)
    except Exception as e:  # noqa: BLE001 — red o refresh_token revocado
        logger.warning("[license] refresh de sesión falló: %s", e)
        return None
    # Conservar identidad previa si el payload viniera incompleto.
    if not nueva.user_id:
        nueva.user_id = session.user_id
    if not nueva.email:
        nueva.email = session.email
    save_session(nueva)
    logger.info("[license] sesión renovada vía refresh_token")
    return nueva


def get_license_status(force_refresh: bool = False) -> dict:
    """
    Devuelve el estado de licencia del usuario.

    Lógica:
    1. Si no hay sesión → `{authenticated: false}` (UI mandará a /login).
    2. Si hay cache fresh (<24h) y no `force_refresh` → devuelve cache.
    3. Intenta `fetch_license_remote()`:
       - Éxito → actualiza cache, devuelve.
       - 401 → sesión expirada → limpia sesión + cache, devuelve unauthenticated.
       - Cualquier otro error → si hay cache <30 días → devuelve cache con
         `stale=true`. Si no hay cache o >30 días → devuelve cache lo mejor que
         se pueda con `stale=true, offline=true`.
    """
    session = load_session()
    if session is None:
        return {"authenticated": False}

    cache = _cache_read()
    now = int(time.time())

    if (
        not force_refresh
        and cache
        and (now - cache.get("cached_at", 0)) < CACHE_FRESH_SECONDS
    ):
        return {**cache.get("payload", {}), "from_cache": True}

    try:
        payload = _fetch_license_con_refresh(session)
    except PermissionError:
        # Sesión inválida y el refresh tampoco la salvó → limpia todo.
        clear_session()
        return {"authenticated": False, "reason": "session_expired"}
    except Exception as e:  # noqa: BLE001 — red / DNS / timeout
        logger.warning("[license] no se pudo refrescar: %s", e)
        if cache and (now - cache.get("cached_at", 0)) < CACHE_GRACE_SECONDS:
            return {
                **cache.get("payload", {}),
                "from_cache": True,
                "stale": True,
                "offline": True,
            }
        # Sin cache utilizable → mostrar mínimo "authenticated" para no
        # bloquear features actuales (v1.0 no tiene features gateadas).
        return {
            "authenticated": True,
            "is_founder": False,
            "premium_features_unlocked": False,
            "stale": True,
            "offline": True,
        }

    _cache_write({"cached_at": now, "payload": payload})
    return payload


# ---------------------------------------------------------------------------
# Checkout (upgrade a Fundador)
# ---------------------------------------------------------------------------


def init_checkout(session: Session) -> dict:
    """Llama POST /api/desktop/checkout y devuelve `{url, session_id}`."""
    return _post_desktop(session, "/api/desktop/checkout", "init_checkout")


# ---------------------------------------------------------------------------
# Suscripción anual de TodoConta Desktop (tarjeta, transferencia, cancelar)
# ---------------------------------------------------------------------------


def init_subscribe_checkout(session: Session) -> dict:
    """
    POST /api/desktop/subscribe → `{url, session_id, promo}`.

    Crea la Stripe Checkout session de la suscripción anual. El backend decide
    el precio (promo $1,495 si el usuario es elegible, si no $2,990).
    """
    return _post_desktop(session, "/api/desktop/subscribe", "init_subscribe_checkout")


def cancel_subscription(session: Session) -> dict:
    """
    POST /api/desktop/cancel-subscription → `{ok, cancel_at, manual}`.

    Cancela al fin del periodo (el usuario conserva acceso hasta `cancel_at`).
    """
    return _post_desktop(
        session, "/api/desktop/cancel-subscription", "cancel_subscription"
    )


def create_transfer_intent(session: Session) -> dict:
    """
    POST /api/desktop/transfer-intent → `{ok, amount_mxn, promo, banco, message}`.

    Registra la intención de pago por transferencia y devuelve los datos
    bancarios para el depósito (activación manual).
    """
    return _post_desktop(
        session, "/api/desktop/transfer-intent", "create_transfer_intent"
    )


def _post_desktop(session: Session, path: str, op: str) -> dict:
    """POST sin body a un endpoint `/api/desktop/*` con Bearer. 401→PermissionError."""
    resp = requests.post(
        f"{API_BASE_URL}{path}",
        headers={
            "Authorization": f"Bearer {session.access_token}",
            "Content-Type": "application/json",
        },
        timeout=10,
    )
    if resp.status_code == 200:
        return resp.json()
    if resp.status_code == 401:
        raise PermissionError("Bearer inválido o expirado")
    logger.warning("[license] %s HTTP %s: %s", op, resp.status_code, resp.text[:200])
    raise RuntimeError(_mensaje_usuario(resp))


def _expose_for_tests() -> dict[str, Any]:
    """Helper que no se usa en producción — facilita patcheo en tests."""
    return {
        "API_BASE_URL": API_BASE_URL,
        "KEYRING_SERVICE": KEYRING_SERVICE,
        "KEYRING_USER": KEYRING_USER,
    }

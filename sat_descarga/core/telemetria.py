"""
Telemetría de errores del agente (Sentry) — opcional y apagada por defecto.

Solo se enciende si hay `SENTRY_DSN` en el entorno (el cascarón Electron lo inyecta
al spawnear el agente en builds empaquetados). Sin DSN —o sin `sentry-sdk`
instalado— TODO es no-op: ni en dev ni en CLI se envía nada.

Privacidad (esta app maneja datos fiscales: RFC, e.firma, CFDIs):
  - `send_default_pii=False`.
  - `max_request_body_size="never"`: los cuerpos de request NUNCA se envían (los
    POST /empresas/* traen la contraseña de la e.firma y la CIEC en el form).
  - `before_send` redacta RFCs y rutas con nombre de usuario, y elimina claves
    sensibles (password/contraseña/ciec/secreto/token) que pudieran colarse en
    `extra`/`contexts`/breadcrumbs.
  - Nunca se envían .cer/.key ni contraseñas (viven en el keychain del SO).
"""

import logging
import os
import re

logger = logging.getLogger(__name__)

# RFC de persona física (13) o moral (12). Se redacta en cualquier string.
_RFC_RE = re.compile(r"\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}\b")

# Prefijos de home con nombre de usuario (PII) → se anonimizan conservando la forma.
_HOME_RES = (
    (re.compile(r"([A-Za-z]:\\Users\\)[^\\/]+", re.IGNORECASE), r"\1<usuario>"),
    (re.compile(r"(/Users/)[^/]+"), r"\1<usuario>"),
    (re.compile(r"(/home/)[^/]+"), r"\1<usuario>"),
)

# Claves de diccionario cuyo VALOR se elimina por completo si aparecen en el evento.
_CLAVE_SENSIBLE_RE = re.compile(
    r"(password|contrase|ciec|secreto|secret|token|api[_-]?key)", re.IGNORECASE
)

_inicializado = False


def init_sentry() -> bool:
    """Inicializa Sentry si hay `SENTRY_DSN`. Devuelve True si quedó activo.

    Idempotente y silencioso: sin DSN o sin sentry-sdk instalado, no hace nada.
    """
    global _inicializado
    if _inicializado:
        return True

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        return False

    try:
        import sentry_sdk
    except ImportError:
        logger.warning(
            "SENTRY_DSN presente pero sentry-sdk no está instalado; telemetría apagada."
        )
        return False

    sentry_sdk.init(
        dsn=dsn,
        release=os.getenv("SENTRY_RELEASE") or None,
        environment=os.getenv("SENTRY_ENVIRONMENT", "production"),
        send_default_pii=False,
        max_request_body_size="never",
        before_send=_before_send,
    )
    _inicializado = True
    logger.info(
        "Telemetría Sentry activada (environment=%s).",
        os.getenv("SENTRY_ENVIRONMENT", "production"),
    )
    return True


def capturar_excepcion(exc: BaseException) -> None:
    """Reporta una excepción a Sentry si está activo; no-op si no.

    Útil para fallos que se degradan a un HTTP 4xx (p. ej. el alta de empresa que
    revienta y se devuelve como 400): la integración de FastAPI solo captura
    excepciones NO atrapadas, así que estos hay que reportarlos a mano."""
    if not _inicializado:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:  # noqa: BLE001 — la telemetría jamás debe romper el flujo
        logger.debug("No se pudo capturar la excepción en Sentry", exc_info=True)


# ---------------------------------------------------------------------------
# Scrubbing de PII
# ---------------------------------------------------------------------------

def _redactar_texto(texto: str) -> str:
    texto = _RFC_RE.sub("<RFC>", texto)
    for patron, reemplazo in _HOME_RES:
        texto = patron.sub(reemplazo, texto)
    return texto


def _scrub(obj):
    """Recorre el evento: redacta RFCs/rutas en strings y borra valores sensibles."""
    if isinstance(obj, dict):
        limpio = {}
        for clave, valor in obj.items():
            if isinstance(clave, str) and _CLAVE_SENSIBLE_RE.search(clave):
                limpio[clave] = "<redactado>"
            else:
                limpio[clave] = _scrub(valor)
        return limpio
    if isinstance(obj, (list, tuple)):
        return [_scrub(v) for v in obj]
    if isinstance(obj, str):
        return _redactar_texto(obj)
    return obj


def _before_send(event, hint):  # noqa: ARG001 — `hint` lo exige la firma de Sentry
    try:
        return _scrub(event)
    except Exception:  # noqa: BLE001 — ante la duda, deja pasar el evento original
        return event

"""
Login al SSO NIDP del SAT, agnóstico al trámite (CIEC o e.firma).

Estos helpers son la capa de autenticación compartida por todos los scrapers del
portal (CFDI, constancia, opinión 32-D, ...): solo cambian la `url_entrada` y el
predicado `exito(url)` para detectar el aterrizaje post-login. Playwright se importa
de forma lazy (dentro de las funciones), así que importar este módulo NO requiere el
extra `ciec`.
"""

import logging

logger = logging.getLogger(__name__)

LOGIN_TIMEOUT_MS = 180_000        # 3 min para el login FIEL (e.firma, sin captcha)
MAX_INTENTOS_CAPTCHA = 3          # CIEC: 1 + 2 reintentos; tras agotarse → cancelar
EXITO_TIMEOUT_MS = 25_000         # espera de aterrizaje tras enviar el captcha

# Selectores donde el portal NIDP del SAT muestra el mensaje de error del login.
_ERROR_SELECTORS = "#msgError, .msg-error, #errormsg"

# Si el mensaje de error es de CAPTCHA, reintentar tiene sentido (otra imagen).
_KW_CAPTCHA = ("captcha", "imagen", "caracteres", "código de la imagen",
               "texto de la imagen")
# Si es de credenciales (RFC/contraseña), reintentar el captcha es inútil → abortar.
# (El chequeo de captcha va primero, así que "válid" no captura errores de captcha.)
_KW_CREDENCIALES = ("contraseña", "contrasena", "rfc", "usuario", "clave",
                    "incorrect", "válid", "invalid")


class CredencialCIECInvalida(RuntimeError):
    """El portal del SAT rechazó el RFC/contraseña CIEC (no es problema del captcha).

    Se lanza para abortar de inmediato (sin gastar reintentos de captcha) cuando el
    portal muestra un error de credenciales."""


def _es_error_credenciales(msg: str) -> bool:
    """True si `msg` (texto del error del portal) indica RFC/contraseña incorrectos
    (y NO un error de captcha, que sí amerita reintentar)."""
    low = msg.lower()
    if any(k in low for k in _KW_CAPTCHA):
        return False
    return any(k in low for k in _KW_CREDENCIALES)


def _texto_error_login(page) -> str:
    """Texto del mensaje de error visible en el login (o '' si no hay)."""
    el = page.query_selector(_ERROR_SELECTORS)
    if el is None:
        return ""
    try:
        if not el.is_visible():
            return ""
    except Exception:  # noqa: BLE001 — si is_visible falla, intentamos leer igual
        pass
    return (el.text_content() or "").strip()


def _login_ciec_con_reintentos(rellenar_form, leer_captcha_img, pedir_captcha,
                               enviar, max_intentos=MAX_INTENTOS_CAPTCHA):
    """
    Política de reintentos del captcha CIEC (pura, sin Playwright → testeable).

    Por cada intento: rellena el form, lee la imagen del captcha, la muestra al
    usuario (`pedir_captcha`) y envía. Hasta `max_intentos`.

    Args:
        rellenar_form(): rellena RFC+contraseña (idempotente; la página puede haberse
            recargado tras un captcha incorrecto).
        leer_captcha_img() -> bytes: imagen del captcha vigente.
        pedir_captcha(img, intento, max) -> Optional[str]: UI; None = el usuario canceló.
        enviar(texto) -> bool: envía y devuelve True si el login tuvo éxito; puede
            LANZAR `CredencialCIECInvalida` si el portal rechaza RFC/contraseña
            (fail-fast: se propaga y aborta sin gastar los reintentos restantes).

    Raises:
        CredencialCIECInvalida: si el portal rechaza el RFC/contraseña CIEC.
        RuntimeError: si el usuario cancela o si se agotan los intentos (la operación
            se cancela para no bloquear/abusar del portal del SAT).
    """
    for intento in range(1, max_intentos + 1):
        rellenar_form()
        img = leer_captcha_img()
        texto = pedir_captcha(img, intento, max_intentos)
        if texto is None:
            raise RuntimeError("Captcha cancelado por el usuario; operación abortada.")
        logger.info("[CIEC] Captcha enviado (intento %d/%d)...", intento, max_intentos)
        if enviar(texto):
            return
        logger.warning("[CIEC] Intento %d/%d falló (¿captcha incorrecto?).",
                       intento, max_intentos)
    raise RuntimeError(
        f"Login CIEC no completado tras {max_intentos} intentos; operación cancelada "
        "para no bloquear el portal del SAT. Reintenta más tarde."
    )


def iniciar_sesion_ciec(page, rfc: str, ciec: str, url_entrada: str, exito,
                        max_intentos: int = MAX_INTENTOS_CAPTCHA, pedir_captcha=None):
    """
    Login CIEC headless con el captcha vía mini-ventana (NO se muestra el browser).

    Abre `url_entrada` en un browser headless. Por cada intento: rellena RFC+contraseña,
    extrae la imagen del captcha y la muestra en una mini-ventana para que el usuario la
    teclee; envía y verifica el aterrizaje con `exito(url)`. Hasta `max_intentos`
    (default 3 = 1 + 2 reintentos); si todos fallan o el usuario cancela, lanza
    RuntimeError (operación cancelada).

    `pedir_captcha(img_bytes, intento, max) -> Optional[str]` es inyectable (default: la
    mini-ventana tkinter de `portal/captcha.py`); None ⇒ el usuario canceló.

    Reutilizado por el portal CFDI (CIECClient) y los scrapers de constancia / opinión:
    solo cambian `url_entrada` y `exito`.
    """
    from playwright.sync_api import TimeoutError as PWTimeout
    from .captcha import bytes_de_data_uri

    if pedir_captcha is None:
        from .captcha import pedir_captcha as pedir_captcha

    rfc = rfc.strip().upper()
    page.goto(url_entrada, wait_until="domcontentloaded")

    def rellenar_form():
        # Espera el form de login (cfdiau/loginda: #rfc, #userCaptcha, #submit). Tras
        # un captcha incorrecto la página se recarga, así que se re-rellena cada vez.
        page.wait_for_selector("input#userCaptcha", timeout=30_000)
        try:
            page.wait_for_load_state("networkidle", timeout=8_000)
        except PWTimeout:
            pass
        for sel in ("input#rfc", 'input[id*="rfc" i]'):
            if page.query_selector(sel):
                page.fill(sel, rfc)
                break
        for sel in ("input#password", 'input[type="password"]'):
            if page.query_selector(sel):
                page.fill(sel, ciec)
                break

    def leer_captcha_img() -> bytes:
        el = page.query_selector('img[src^="data:image"]')
        if el is None:
            raise RuntimeError("No se encontró la imagen del captcha en el login.")
        return bytes_de_data_uri(el.get_attribute("src") or "")

    def enviar(texto: str) -> bool:
        page.fill("input#userCaptcha", texto)
        # no_wait_after=True: el clic NO debe bloquear esperando la navegación del
        # submit. Por default Playwright espera "scheduled navigations to finish"
        # dentro del propio click() (timeout 30 s); si el SAT tarda en responder el
        # POST, el click revienta con TimeoutError y crashea el job (Sentry
        # TODOCONTA-DESKTOP-9). La espera del aterrizaje ya la hace wait_for_url de
        # abajo, con nuestro EXITO_TIMEOUT_MS y la lógica de reintento de captcha.
        page.click("input#submit", no_wait_after=True)
        try:
            page.wait_for_url(exito, timeout=EXITO_TIMEOUT_MS)
        except PWTimeout:
            # No aterrizó. Si el portal muestra un error de CREDENCIALES (RFC/contraseña),
            # reintentar el captcha es inútil → abortar de inmediato con copy claro.
            # Si es error de captcha (u otro), devolver False para reintentar.
            err = _texto_error_login(page)
            if err and _es_error_credenciales(err):
                raise CredencialCIECInvalida(
                    f"El SAT rechazó el acceso: «{err}». Revisa el RFC y la contraseña "
                    "CIEC de esta empresa en Empresas."
                )
            if err:
                logger.warning("[CIEC] Error de login (reintentable): %s", err)
            return False
        try:
            page.wait_for_load_state("networkidle", timeout=15_000)
        except PWTimeout:
            pass
        return True

    _login_ciec_con_reintentos(
        rellenar_form, leer_captcha_img, pedir_captcha, enviar, max_intentos
    )
    logger.info("[CIEC] Login exitoso.")


def iniciar_sesion_fiel(page, cer_path: str, key_path: str, password: str,
                        url_entrada: str, exito, timeout_ms: int = LOGIN_TIMEOUT_MS):
    """
    Login con e.firma (FIEL) genérico, paralelo a `iniciar_sesion_ciec`.

    Sube .cer + .key + contraseña de la clave privada en la pestaña e.firma del SSO
    NIDP del SAT. Best-effort: intenta automatizar la selección de archivos; si los
    selectores no coinciden, el browser queda VISIBLE para que el usuario complete
    el login a mano (la e.firma no tiene captcha). Espera hasta `exito(url)`.

    Reutilizado por los scrapers (constancia/opinión): solo cambia url_entrada y `exito`.
    """
    import os
    from playwright.sync_api import TimeoutError as PWTimeout

    cer_path = os.path.abspath(cer_path)
    key_path = os.path.abspath(key_path)

    page.goto(url_entrada, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeout:
        pass

    try:
        _login_efirma(page, cer_path, key_path, password)
    except Exception as e:
        logger.warning("[FIEL] Autollenado e.firma falló (%s). "
                       "Complétalo a mano en el browser.", e)

    logger.info("[FIEL] Si hace falta, selecciona .cer/.key + contraseña y «Enviar» "
                "en el browser. Esperando login (hasta %d s)...", timeout_ms // 1000)
    try:
        page.wait_for_url(exito, timeout=timeout_ms)
    except PWTimeout:
        raise RuntimeError(
            f"Login e.firma no completado. URL actual: {page.url}."
        )
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeout:
        pass
    logger.info("[FIEL] Login exitoso.")


def _login_efirma(page, cer_path: str, key_path: str, password: str):
    """
    Login e.firma con los selectores CONFIRMADOS del NIDP del SAT (mayo 2026).

    La entrada (lanzador, tipoLogeo=c) cae en "Acceso por contraseña"; se cambia a
    e.firma con #buttonFiel, se suben .cer/.key (inputs file ocultos → state=attached)
    y la contraseña, y se envía con #submit (onclick="firmar(event)", firma client-side).

    OJO: el form e.firma comparte el id `#submit` con el de "Acceso por contraseña"
    (que queda OCULTO al cambiar a e.firma). Por eso se hace clic en el `#submit`
    VISIBLE: clavarse en el oculto provocaría timeout (visto en loginda / opinión 32-D).
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    # Cambiar a la pestaña e.firma desde "Acceso por contraseña".
    try:
        page.click("#buttonFiel", timeout=10_000)
    except PWTimeout:
        logger.info("[FIEL] No vi #buttonFiel (¿ya en la pantalla de e.firma?).")

    # Form de e.firma. Los inputs file son display:none → esperar 'attached'.
    page.wait_for_selector("#fileCertificate", state="attached", timeout=20_000)
    page.set_input_files("#fileCertificate", cer_path)
    page.set_input_files("#filePrivateKey", key_path)
    page.fill("#privateKeyPassword", password)
    logger.info("[FIEL] .cer/.key/contraseña llenados (auto).")

    # Clic en el #submit visible (el del form e.firma); el #submit del form de
    # contraseña queda oculto y compartiría el id.
    try:
        page.click("#submit:visible", timeout=10_000)
    except PWTimeout:
        page.click("#submit")  # fallback: id sin filtrar
    logger.info("[FIEL] e.firma enviada.")

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

LOGIN_TIMEOUT_MS = 180_000  # 3 min para resolver captcha + login


def iniciar_sesion_ciec(page, rfc: str, ciec: str, url_entrada: str, exito, timeout_ms: int = LOGIN_TIMEOUT_MS):
    """
    Login CIEC genérico reutilizable por cualquier portal del SAT que use el SSO NIDP.

    Abre `url_entrada`, pre-llena RFC + contraseña, espera a que el USUARIO resuelva
    el captcha y dé «Enviar» en el browser visible, y luego espera hasta que
    `exito(url)` sea True (predicado sobre la URL para detectar el aterrizaje
    post-login; cada portal redirige a un destino distinto).

    Reutilizado por el portal CFDI (CIECClient) y por los scrapers de constancia /
    opinión, que solo cambian `url_entrada` y `exito`.
    """
    from playwright.sync_api import TimeoutError as PWTimeout

    page.goto(url_entrada, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeout:
        pass

    # Pre-llenar RFC + contraseña (el usuario solo resuelve el captcha).
    for sel in ("input#rfc", 'input[id*="rfc" i]'):
        if page.query_selector(sel):
            page.fill(sel, rfc.strip().upper())
            break
    for sel in ("input#password", 'input[type="password"]'):
        if page.query_selector(sel):
            page.fill(sel, ciec)
            break

    logger.info(
        "[CIEC] Resuelve el captcha y haz clic en «Enviar» en el browser. "
        "Esperando login (hasta %d s)...", timeout_ms // 1000
    )
    try:
        page.wait_for_url(exito, timeout=timeout_ms)
    except PWTimeout:
        raise RuntimeError(
            f"Login no completado. URL actual: {page.url}. "
            "¿Captcha incorrecto o sesión previa abierta?"
        )
    try:
        page.wait_for_load_state("networkidle", timeout=15_000)
    except PWTimeout:
        pass
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

    page.click("#submit")  # firmar(event)
    logger.info("[FIEL] e.firma enviada.")

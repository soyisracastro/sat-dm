"""
Envío de la Solicitud de Certificado de Sello Digital (CSD) al portal CertiSAT
Web del SAT, con autenticación por e.firma (FIEL). Reutiliza el login genérico
`iniciar_sesion_fiel` de `login.py`.

Flujo (confirmado 2026-07-08, ver docs/path-renovacion-efirma-csd.md):
  1. Login NIDP SOLO e.firma en `loginc.mat.sat.gob.mx` con target a CertiSAT;
     el form ya es de e.firma (mismos selectores #fileCertificate/#filePrivateKey/
     #privateKeyPassword/#submit que usa `iniciar_sesion_fiel`).
  2. `requerimiento.do?menu=requerimiento` → subir el `.sdg` (input `requerimiento`)
     → «Enviar requerimiento» → devuelve el NÚMERO DE OPERACIÓN.
  3. «Seguimiento» → descarga el acuse PDF (`pdf.do` → Acuse_GeneracionSellos.pdf).
  4. «Recuperación de certificados» → RFC + «Último certificado expedido» → tabla
     con el link al `.cer` (rdc.sat.gob.mx). El `.cer` NO está disponible de
     inmediato (tarda minutos) → se reintenta y se verifica que empareje con la
     `.key` nueva antes de darlo por bueno (para no bajar un CSD viejo).

El `.sdg` se genera aparte (módulo `certifica/`). El browser corre headless (la
e.firma no tiene captcha). Requiere playwright (+ chromium).
"""

import datetime
import logging
from pathlib import Path
from typing import Optional

from .login import iniciar_sesion_fiel

logger = logging.getLogger(__name__)

# URL de entrada del login NIDP SOLO e.firma cuyo `target` lleva a CertiSAT Web.
CSD_URL_ENTRADA_FIEL = (
    "https://loginc.mat.sat.gob.mx/nidp/idff/sso"
    "?id=XACCertiSAT&sid=0&option=credential&sid=0"
    "&target=https%3A%2F%2Faplicacionesc.mat.sat.gob.mx%2Fcertisat%2F"
)
# Tras el login se aterriza en el HOST de CertiSAT. OJO: el predicado de éxito debe
# mirar el HOST REAL (la parte antes del `?`), NO "contiene la cadena": el host
# aplicacionesc.mat.sat.gob.mx aparece dentro del `target=` de la propia URL de
# login (loginc.mat...), así que un `in url` da falso positivo y "aterriza" sin
# haber entrado (bug detectado en prueba 3).
CSD_LANDING_HOST = "aplicacionesc.mat.sat.gob.mx"


def _aterrizo_en_certisat(url: str) -> bool:
    """True solo si la URL actual ES del host de CertiSAT (no la de login que lo
    lleva en el `target=`)."""
    return url.split("?", 1)[0].startswith("https://" + CSD_LANDING_HOST)
REQUERIMIENTO_URL = f"https://{CSD_LANDING_HOST}/certisat/requerimiento.do?menu=requerimiento"
RECUPERACION_URL = f"https://{CSD_LANDING_HOST}/certisat/recuperacion.do?menu=recuperacion"

_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _mismo_par(cer_der: bytes, key_bytes: bytes, password: str) -> bool:
    """True si la llave pública de `cer_der` corresponde a la privada `key_bytes`."""
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    try:
        cert = x509.load_der_x509_certificate(cer_der)
        key = serialization.load_der_private_key(key_bytes, password.encode())
    except Exception:
        return False
    spki = lambda k: k.public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    return spki(cert.public_key()) == spki(key.public_key())


class CSDPortalClient:
    """Cliente para enviar el `.sdg` y recuperar el CSD emitido (portal e.firma)."""

    def __init__(self, cer_path: str, key_path: str, password: str, headless: bool = True):
        self.cer_path = cer_path
        self.key_path = key_path
        self.password = password
        self.headless = headless
        # RFC del titular (para nombrar archivos y la Recuperación).
        self.rfc = ""
        try:
            from ..core.fiel import FIEL
            self.rfc = FIEL(cer_path, key_path, password).rfc
        except Exception as e:  # noqa: BLE001
            logger.warning("[CSD] no se pudo leer el RFC del .cer: %s", e)

    # ------------------------------------------------------------------
    # Orquestación
    # ------------------------------------------------------------------

    def enviar(
        self,
        sdg_path: str,
        directorio_salida: str = "./csd/",
        key_nueva_path: Optional[str] = None,
        recuperar: bool = True,
        intentos_cert: int = 6,
        espera_cert_s: int = 30,
    ) -> dict:
        """
        Sube el `.sdg` y devuelve el número de operación + acuse; opcionalmente
        recupera el `.cer` emitido (reintentando hasta que empareje con la .key nueva).

        Returns: {"numero_operacion", "acuse_pdf", "estado", "cer"} (los últimos
        pueden ser None si no se lograron capturar / el cert no estaba listo).
        """
        try:
            from playwright.sync_api import sync_playwright
            from playwright.sync_api import TimeoutError as PWTimeout
        except ImportError:
            raise ImportError(
                "playwright no está instalado. Ejecuta:\n"
                "  pip install playwright\n  playwright install chromium"
            )
        from .setup import asegurar_chromium, lanzar_chromium
        asegurar_chromium()

        out_dir = Path(directorio_salida)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        res: dict = {"numero_operacion": None, "acuse_pdf": None, "estado": None, "cer": None}

        with sync_playwright() as p:
            browser = lanzar_chromium(p, headless=self.headless, slow_mo=60)
            context = browser.new_context(accept_downloads=True, user_agent=_UA)
            page = context.new_page()
            try:
                self._login(page)

                # --- Subir el .sdg ---
                num = self._subir_sdg(page, sdg_path)
                res["numero_operacion"] = num
                logger.info("[CSD] Número de operación: %s", num)
                (out_dir / f"numero_operacion_{self.rfc}_{stamp}.txt").write_text(
                    num, encoding="utf-8"
                )

                # --- Seguimiento + acuse ---
                estado, acuse = self._seguimiento(context, page, out_dir, stamp)
                res["estado"] = estado
                res["acuse_pdf"] = acuse

                # --- Recuperar el .cer emitido ---
                if recuperar:
                    cer = self._recuperar_cert(
                        context, page, out_dir, stamp,
                        key_nueva_path, intentos_cert, espera_cert_s,
                    )
                    res["cer"] = cer
                return res
            finally:
                browser.close()

    def recuperar(
        self,
        directorio_salida: str = "./csd/",
        key_nueva_path: Optional[str] = None,
        intentos: int = 10,
        espera_s: int = 30,
    ) -> dict:
        """Descarga (más tarde) el último CSD emitido del RFC, sin re-enviar nada.

        Útil cuando el `.cer` no estaba listo al enviar (tarda minutos). Si se pasa
        `key_nueva_path`, verifica que el cert recuperado empareje con esa llave."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("playwright no está instalado.")
        from .setup import asegurar_chromium, lanzar_chromium
        asegurar_chromium()

        out_dir = Path(directorio_salida)
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        with sync_playwright() as p:
            browser = lanzar_chromium(p, headless=self.headless, slow_mo=60)
            context = browser.new_context(accept_downloads=True, user_agent=_UA)
            page = context.new_page()
            try:
                self._login(page)
                cer = self._recuperar_cert(
                    context, page, out_dir, stamp, key_nueva_path, intentos, espera_s
                )
                return {"cer": cer}
            finally:
                browser.close()

    # ------------------------------------------------------------------
    # Pasos
    # ------------------------------------------------------------------

    def _login(self, page, intentos: int = 3):
        """Login e.firma con reintentos: el NIDP a veces se atora en un paso
        intermedio (`/nidp/app`) en vez de aterrizar en CertiSAT; reintentar lo
        resuelve (cada intento re-entra por la URL fresca)."""
        ultimo = None
        for intento in range(1, intentos + 1):
            try:
                iniciar_sesion_fiel(
                    page, self.cer_path, self.key_path, self.password,
                    url_entrada=CSD_URL_ENTRADA_FIEL,
                    exito=_aterrizo_en_certisat,
                    timeout_ms=45_000,
                )
                return
            except RuntimeError as e:
                ultimo = e
                logger.warning("[CSD] login intento %d/%d no aterrizó (%s); reintento…",
                               intento, intentos, page.url[:70])
        raise RuntimeError(f"No se pudo entrar a CertiSAT tras {intentos} intentos: {ultimo}")

    def _subir_sdg(self, page, sdg_path: str) -> str:
        """Sube el `.sdg` y devuelve el número de operación (o lanza si el SAT no lo dio)."""
        import os
        from playwright.sync_api import TimeoutError as PWTimeout

        page.goto(REQUERIMIENTO_URL, wait_until="domcontentloaded")
        page.wait_for_selector("#txtFileReq", state="attached", timeout=30_000)
        page.set_input_files("#txtFileReq", os.path.abspath(sdg_path))
        logger.info("[CSD] .sdg seleccionado: %s", os.path.basename(sdg_path))
        page.click('input[name="enviar"]', no_wait_after=True)

        try:
            page.wait_for_selector('input[name="numeroOperacion"]', timeout=60_000)
        except PWTimeout:
            cuerpo = (page.inner_text("body")[:400] if page else "").strip()
            raise RuntimeError(
                "El SAT no devolvió número de operación tras subir el .sdg. "
                "A veces es un error transitorio del portal; reintenta. "
                f"Pantalla: «{cuerpo}»"
            )
        # El SAT rinde el número en un input visible Y uno hidden (mismo valor) →
        # `.first` evita el strict-mode violation de Playwright.
        num = (page.locator('input[name="numeroOperacion"]').first.input_value() or "").strip()
        if not num:
            raise RuntimeError("Número de operación vacío en la respuesta del SAT.")
        return num

    def _seguimiento(self, context, page, out_dir: Path, stamp: str):
        """Clic en «Seguimiento», lee el estado y descarga el acuse PDF (best-effort)."""
        from playwright.sync_api import TimeoutError as PWTimeout

        estado, acuse = None, None
        try:
            page.click('input[value="Seguimiento"]', no_wait_after=True)
            page.wait_for_load_state("networkidle", timeout=20_000)
        except PWTimeout:
            pass
        except Exception as e:  # noqa: BLE001
            logger.warning("[CSD] no pude entrar a Seguimiento: %s", e)
            return estado, acuse

        # Estado del certificado (fila de detalle).
        try:
            txt = page.inner_text("body")
            for linea in txt.splitlines():
                if "Certificado Digital generado" in linea or "generado" in linea.lower():
                    estado = linea.strip()
                    break
            logger.info("[CSD] Estado en seguimiento: %s", estado or "(no leído)")
        except Exception:  # noqa: BLE001
            pass

        # Acuse PDF: el link abre window.open('pdf.do') que descarga el PDF.
        dest = out_dir / f"Acuse_GeneracionSellos_{self.rfc}_{stamp}.pdf"
        try:
            acuse = self._descargar_acuse(context, page, dest)
        except Exception as e:  # noqa: BLE001
            logger.warning("[CSD] no se pudo descargar el acuse: %s", e)
        return estado, acuse

    def _descargar_acuse(self, context, page, dest: Path) -> Optional[Path]:
        from playwright.sync_api import TimeoutError as PWTimeout

        link = page.locator('a:has-text("Acuse de recibo")')
        if link.count() == 0:
            return None
        descarga: dict = {}
        context.on("download", lambda d: descarga.setdefault("d", d))
        popup = None
        try:
            with context.expect_page(timeout=8_000) as pop:
                link.first.click()
            popup = pop.value
        except PWTimeout:
            pass
        for _ in range(20):
            if "d" in descarga:
                break
            page.wait_for_timeout(300)
        if "d" in descarga:
            descarga["d"].save_as(str(dest))
            return dest if dest.exists() and dest.stat().st_size > 0 else None
        if popup is not None and popup.url.startswith("http"):
            try:
                resp = popup.goto(popup.url, wait_until="commit", timeout=10_000)
                if resp:
                    b = resp.body()
                    if b[:5] == b"%PDF-":
                        dest.write_bytes(b)
                        return dest
            except Exception:  # noqa: BLE001
                pass
        return None

    def _recuperar_cert(self, context, page, out_dir: Path, stamp: str,
                        key_nueva_path, intentos: int, espera_s: int) -> Optional[Path]:
        """
        Busca en «Recuperación de certificados» el último CSD del RFC y lo descarga.
        Reintenta porque el `.cer` tarda minutos en publicarse; si se pasó la `.key`
        nueva, verifica que empareje (para no bajar un CSD viejo).
        """
        key_bytes = None
        if key_nueva_path and Path(key_nueva_path).exists():
            key_bytes = Path(key_nueva_path).read_bytes()

        for intento in range(1, intentos + 1):
            cer_bytes, serie = self._buscar_y_bajar_ultimo(context, page)
            if cer_bytes:
                ok_par = (key_bytes is None) or _mismo_par(cer_bytes, key_bytes, self.password)
                if ok_par:
                    dest = out_dir / f"{serie or ('CSD_' + self.rfc)}.cer"
                    dest.write_bytes(cer_bytes)
                    logger.info("[CSD] ✓ CSD recuperado: %s (%d bytes)", dest, len(cer_bytes))
                    return dest
                logger.info("[CSD] El último cert aún no es el nuestro (empareja=False); espero…")
            logger.info("[CSD] Cert no disponible (intento %d/%d); espero %ds…",
                        intento, intentos, espera_s)
            if intento < intentos:
                page.wait_for_timeout(espera_s * 1000)
        logger.warning("[CSD] El CSD no estuvo listo tras %d intentos. Recupéralo luego "
                       "con el mismo RFC (suele tardar unos minutos).", intentos)
        return None

    def _buscar_y_bajar_ultimo(self, context, page):
        """Recuperación por RFC + «Último certificado expedido» → (cer_bytes, serie) o (None, None)."""
        try:
            page.goto(RECUPERACION_URL, wait_until="domcontentloaded")
            page.wait_for_selector('input[name="txtRFC"]', timeout=20_000)
            page.fill('input[name="txtRFC"]', self.rfc)
            radio = page.locator('input[name="chkCantidadCertificados"][value="ultimo"]')
            if radio.count() > 0:
                radio.first.check()
            page.click('input[name="btnRFC"]', no_wait_after=True)
        except Exception as e:  # noqa: BLE001
            logger.warning("[CSD] error en la búsqueda de recuperación: %s", e)
            return None, None

        # Los resultados tardan un momento y pueden vivir en un frame → esperar el
        # link del .cer en CUALQUIER frame (no solo el principal).
        href = self._esperar_link_cer(page, timeout_s=12)
        if not href:
            return None, None
        serie = href.rsplit("/", 1)[-1].removesuffix(".cer") or None
        return self._bajar_cer(context, href), serie

    def _esperar_link_cer(self, page, timeout_s: int = 12) -> Optional[str]:
        """Devuelve el href del `.cer` (rdc.sat.gob.mx) en cualquier frame, o None."""
        import time as _t

        deadline = _t.time() + timeout_s
        while _t.time() < deadline:
            for fr in page.frames:
                try:
                    loc = fr.locator('a[href*="rdc.sat.gob.mx"][href$=".cer"]')
                    if loc.count() > 0:
                        href = loc.first.get_attribute("href")
                        if href:
                            return href
                except Exception:  # noqa: BLE001
                    continue
            page.wait_for_timeout(800)
        return None

    def _bajar_cer(self, context, href: str) -> Optional[bytes]:
        """Descarga el `.cer` emitido. El repositorio `rdc.sat.gob.mx` es público y
        su TLS SÍ lo acepta requests (curl lo baja limpio); además el navegador lo
        trata como descarga (content-type x-x509-ca-cert), así que HTTP directo es
        lo más simple. Fallback: capturar la descarga con el navegador."""
        import tempfile

        # 1) HTTP directo (verify=False: los certs del SAT rompen la validación estándar).
        try:
            import requests
            import urllib3

            urllib3.disable_warnings()
            r = requests.get(href, timeout=20, verify=False, headers={"User-Agent": _UA})
            if r.status_code == 200 and r.content[:1] == b"\x30":  # DER SEQUENCE
                return r.content
        except Exception as e:  # noqa: BLE001
            logger.info("[CSD] descarga HTTP del .cer falló (%s); pruebo con el navegador…", e)

        # 2) Fallback: el navegador dispara "Download is starting" → capturarla.
        dl = context.new_page()
        try:
            with dl.expect_download(timeout=15_000) as di:
                try:
                    dl.goto(href)
                except Exception:  # noqa: BLE001 — la descarga aborta el goto; es lo esperado
                    pass
            tf = Path(tempfile.mktemp(suffix=".cer"))
            di.value.save_as(str(tf))
            b = tf.read_bytes()
            return b if b and b[:1] == b"\x30" else None
        except Exception:  # noqa: BLE001
            return None
        finally:
            dl.close()


# ---------------------------------------------------------------------------
# Función pública de conveniencia
# ---------------------------------------------------------------------------

def enviar_solicitud_csd_fiel(
    cer_path: str,
    key_path: str,
    password: str,
    sdg_path: str,
    directorio_salida: str = "./csd/",
    key_nueva_path: Optional[str] = None,
    headless: bool = True,
    recuperar: bool = True,
    intentos_cert: int = 6,
    espera_cert_s: int = 30,
) -> dict:
    """
    Envía un `.sdg` (Solicitud de CSD) al portal CertiSAT Web con e.firma y devuelve
    el número de operación + acuse; opcionalmente recupera el `.cer` emitido.

    `key_nueva_path` es la `.key` que se generó junto al `.sdg`: si se pasa, se usa
    para confirmar que el CSD recuperado es el correcto (empareja con esa llave).
    El browser corre headless (la e.firma no tiene captcha).
    """
    client = CSDPortalClient(cer_path, key_path, password, headless=headless)
    return client.enviar(
        sdg_path, directorio_salida=directorio_salida, key_nueva_path=key_nueva_path,
        recuperar=recuperar, intentos_cert=intentos_cert, espera_cert_s=espera_cert_s,
    )


def recuperar_ultimo_csd_fiel(
    cer_path: str,
    key_path: str,
    password: str,
    directorio_salida: str = "./csd/",
    key_nueva_path: Optional[str] = None,
    headless: bool = True,
    intentos: int = 10,
    espera_s: int = 30,
) -> dict:
    """Descarga el último CSD emitido del RFC desde CertiSAT Web (para cuando el
    `.cer` no estaba listo al enviar). Devuelve {"cer": Path|None}."""
    client = CSDPortalClient(cer_path, key_path, password, headless=headless)
    return client.recuperar(
        directorio_salida=directorio_salida, key_nueva_path=key_nueva_path,
        intentos=intentos, espera_s=espera_s,
    )

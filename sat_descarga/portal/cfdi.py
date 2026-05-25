"""
Módulo CIEC: descarga de CFDIs vía el portal portalcfdi.facturaelectronica.sat.gob.mx
usando autenticación CIEC (RFC + contraseña), sin e-firma.

Útil cuando no se tiene la FIEL del contribuyente (p. ej. una persona física
ajena) o para volúmenes pequeños donde la espera del Web Service es inaceptable.

Mecanismo (confirmado contra el portal real, mayo 2026):
  - Login: el portal redirige a cfdiau.sat.gob.mx; el captcha lo resuelve el
    usuario en el browser VISIBLE. Tras enviar, regresa a portalcfdi.
  - Búsqueda:
      * Recibidos (ConsultaReceptor.aspx): filtra UN día a la vez (dropdowns
        año/mes/día + rango de hora). Se itera día por día.
      * Emitidos (ConsultaEmisor.aspx): rango de fechas. Los inputs de fecha
        son disabled-por-diseño (display-only de un date-picker); se fuerzan
        por JS. El radio "Fecha de Emisión" SOLO se activa con click NATIVO
        (su onclick dispara __doPostBack; setear .checked por JS no basta).
  - Descarga: cada fila de resultados trae un ícono cuyo onclick ejecuta
    AccionCfdi('RecuperaCfdi.aspx?Datos=<token>','Recuperacion'). Esa URL
    devuelve el XML como adjunto. La paginación es client-side (todas las
    filas están en el DOM desde la primera búsqueda), así que se extraen los
    tokens de TODAS las filas y se descargan una por una.

OJO — cuota: el portal limita las descargas individuales por día
(hfDescarga = "CuotaParcial"/"CuotaCompleta"). Al agotarse, se detiene.

Requiere:
    pip install playwright
    playwright install chromium
"""

import logging
import re
from datetime import date, timedelta
from pathlib import Path
from typing import List, Optional

from .login import iniciar_sesion_ciec

logger = logging.getLogger(__name__)

PORTAL_URL = "https://portalcfdi.facturaelectronica.sat.gob.mx"
DOWNLOAD_TIMEOUT_MS = 30_000


class CIECClient:
    """Cliente para descargar CFDIs vía el portal web del SAT (CIEC)."""

    def __init__(self, rfc: str, ciec: str, headless: bool = False):
        self.rfc = rfc.strip().upper()
        self.ciec = ciec
        # headless=False por defecto: el usuario resuelve el captcha en el browser.
        self.headless = headless

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def descargar(
        self,
        fecha_inicio: date,
        fecha_fin: date,
        tipo_comprobante: str = "RE",
        directorio_salida: str = "./cfdi/",
        max_registros: int = 2000,
    ) -> List[Path]:
        """
        Descarga CFDIs del portal del SAT con un solo login.

        Args:
            fecha_inicio / fecha_fin: rango del periodo.
            tipo_comprobante: "R" (recibidos), "E" (emitidos) o "RE"/ambos
                (default). Si se piden ambos, cada tipo va a su subcarpeta
                (recibidos/ y emitidos/); si es uno solo, va directo a la carpeta.
            directorio_salida: carpeta destino de los XMLs.
            max_registros: tope TOTAL de XMLs a descargar (protege contra la cuota).

        Returns:
            Lista de Paths a los XMLs descargados.
        """
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError(
                "playwright no está instalado. Ejecuta:\n"
                "  pip install playwright\n"
                "  playwright install chromium"
            )

        tipos = _normalizar_tipos(tipo_comprobante)
        base_dir = Path(directorio_salida)
        base_dir.mkdir(parents=True, exist_ok=True)
        descargados: List[Path] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, slow_mo=80)
            context = browser.new_context(
                accept_downloads=True,
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            )
            page = context.new_page()

            try:
                self._login(page)  # un solo captcha para todos los tipos
                for tipo in tipos:
                    if len(descargados) >= max_registros:
                        break
                    etiqueta = "Emitidos" if tipo == "E" else "Recibidos"
                    # Subcarpeta por tipo solo si se pidió más de uno.
                    out_dir = (base_dir / etiqueta.lower()) if len(tipos) > 1 else base_dir
                    out_dir.mkdir(parents=True, exist_ok=True)
                    logger.info("[CIEC] === %s → %s ===", etiqueta, out_dir)
                    descargados.extend(self._descargar_tipo(
                        page, tipo, fecha_inicio, fecha_fin, out_dir,
                        max_registros - len(descargados),
                    ))
            finally:
                browser.close()

        logger.info("[CIEC] Descarga completada: %d XMLs en %s",
                    len(descargados), base_dir)
        return descargados

    def _descargar_tipo(
        self, page, tipo: str, fecha_inicio: date, fecha_fin: date,
        out_dir: Path, max_registros: int,
    ) -> List[Path]:
        """Busca y descarga UN tipo ("R" o "E") en out_dir. Devuelve los Paths."""
        descargados: List[Path] = []
        vistos: set = set()

        if tipo == "E":
            bloques = [(fecha_inicio, fecha_fin)]
            buscar = lambda fi, ff: self._buscar_emisor(page, fi, ff)
        else:
            # Recibidos: un día a la vez.
            bloques = [(d, d) for d in _dias(fecha_inicio, fecha_fin)]
            buscar = lambda fi, ff: self._buscar_receptor_dia(page, fi)

        fallos_seguidos = 0
        for fi, ff in bloques:
            if len(descargados) >= max_registros:
                break
            buscar(fi, ff)
            # Se extraen TODAS las URLs de las filas antes de descargar, así
            # las descargas pueden navegar la misma página sin perder datos.
            filas = self._extraer_filas(page)
            if not filas:
                continue
            logger.info("[CIEC] %s%s: %d CFDIs en resultados.",
                        fi, "" if fi == ff else f"→{ff}", len(filas))

            for fila in filas:
                if len(descargados) >= max_registros:
                    break
                uuid = fila["uuid"]
                url = fila["url"]
                if not uuid or uuid in vistos:
                    continue
                vistos.add(uuid)
                dest = out_dir / f"{uuid}.xml"
                if dest.exists() and dest.stat().st_size > 0:
                    descargados.append(dest)
                    continue
                if not url:
                    logger.warning("[CIEC] %s sin URL de descarga.", uuid)
                    continue
                if self._descargar_xml(page, url, dest):
                    descargados.append(dest)
                    fallos_seguidos = 0
                    logger.info("[CIEC] ✓ %s (%d)", uuid, len(descargados))
                else:
                    fallos_seguidos += 1
                    logger.warning("[CIEC] ✗ no se pudo descargar %s", uuid)
                    # 3 fallos seguidos: probable cuota diaria agotada o
                    # error del portal. Mejor detenerse que seguir en vano.
                    if fallos_seguidos >= 3:
                        logger.error(
                            "[CIEC] ⛔ 3 descargas seguidas fallaron "
                            "(¿cuota diaria agotada?). Deteniendo; "
                            "reintenta más tarde o mañana."
                        )
                        return descargados
        return descargados

    # ------------------------------------------------------------------
    # Login (captcha resuelto por el usuario en el browser visible)
    # ------------------------------------------------------------------

    def _login(self, page):
        # El portal CFDI aterriza de vuelta en portalcfdi (saliendo de cfdiau).
        iniciar_sesion_ciec(
            page, self.rfc, self.ciec,
            url_entrada=f"{PORTAL_URL}/",
            exito=lambda url: "portalcfdi.facturaelectronica.sat.gob.mx" in url
                              and "cfdiau" not in url,
        )

    # ------------------------------------------------------------------
    # Selección del radio de fechas (común a ambas consultas)
    # ------------------------------------------------------------------

    def _seleccionar_radio_fechas(self, page):
        """
        Click NATIVO en el radio 'Fecha de ...'. Su onclick dispara
        setTimeout('__doPostBack(...)',0) → postback completo que habilita los
        controles de fecha. Setear .checked por JS NO funciona (el servidor
        re-renderiza con el radio de Folio Fiscal y los campos disabled).
        """
        from playwright.sync_api import TimeoutError as PWTimeout

        radio = page.query_selector("input#ctl00_MainContent_RdoFechas")
        if radio and not radio.is_checked():
            radio.click()
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except PWTimeout:
                pass

    # ------------------------------------------------------------------
    # Búsqueda: Recibidos (un día)
    # ------------------------------------------------------------------

    def _buscar_receptor_dia(self, page, dia: date):
        from playwright.sync_api import TimeoutError as PWTimeout

        if PORTAL_URL not in page.url or "ConsultaReceptor" not in page.url:
            page.goto(f"{PORTAL_URL}/ConsultaReceptor.aspx",
                      wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=20_000)
            except PWTimeout:
                pass

        self._seleccionar_radio_fechas(page)

        _select(page, "select#DdlAnio", str(dia.year))
        _select(page, "select#ctl00_MainContent_CldFecha_DdlMes", str(dia.month))
        _select(page, "select#ctl00_MainContent_CldFecha_DdlDia", f"{dia.day:02d}")
        _select(page, "select#ctl00_MainContent_CldFecha_DdlHora", "0")
        _select(page, "select#ctl00_MainContent_CldFecha_DdlMinuto", "0")
        _select(page, "select#ctl00_MainContent_CldFecha_DdlSegundo", "0")
        _select(page, "select#ctl00_MainContent_CldFecha_DdlHoraFin", "23")
        _select(page, "select#ctl00_MainContent_CldFecha_DdlMinutoFin", "59")
        _select(page, "select#ctl00_MainContent_CldFecha_DdlSegundoFin", "59")

        self._buscar(page)

    # ------------------------------------------------------------------
    # Búsqueda: Emitidos (rango)
    # ------------------------------------------------------------------

    def _buscar_emisor(self, page, fi: date, ff: date):
        from playwright.sync_api import TimeoutError as PWTimeout

        page.goto(f"{PORTAL_URL}/ConsultaEmisor.aspx", wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("networkidle", timeout=20_000)
        except PWTimeout:
            pass

        # Click nativo en el radio y esperar a que el SELECT DE HORA se habilite
        # (el input de texto de fecha es disabled-por-diseño y nunca se habilita).
        radio = page.query_selector("input#ctl00_MainContent_RdoFechas")
        if radio:
            radio.click()
        try:
            page.wait_for_function(
                "() => { const e=document.getElementById("
                "'ctl00_MainContent_CldFechaInicial2_DdlHora'); "
                "return e && !e.disabled; }",
                timeout=20_000,
            )
        except PWTimeout:
            logger.warning("[CIEC] Los controles de fecha de Emitidos no se "
                           "habilitaron tras el click del radio.")

        # Forzar los inputs de fecha (display-only) por JS.
        fi_s, ff_s = fi.strftime("%d/%m/%Y"), ff.strftime("%d/%m/%Y")
        page.evaluate(
            """([fi, ff]) => {
                const set = (id, v) => {
                    const el = document.getElementById(id);
                    if (!el) return;
                    el.removeAttribute('disabled'); el.disabled = false;
                    el.value = v;
                    el.dispatchEvent(new Event('change', {bubbles: true}));
                };
                set('ctl00_MainContent_CldFechaInicial2_Calendario_text', fi);
                set('ctl00_MainContent_CldFechaFinal2_Calendario_text', ff);
            }""",
            [fi_s, ff_s],
        )
        _select(page, "select#ctl00_MainContent_CldFechaInicial2_DdlHora", "0")
        _select(page, "select#ctl00_MainContent_CldFechaInicial2_DdlMinuto", "0")
        _select(page, "select#ctl00_MainContent_CldFechaInicial2_DdlSegundo", "0")
        _select(page, "select#ctl00_MainContent_CldFechaFinal2_DdlHora", "23")
        _select(page, "select#ctl00_MainContent_CldFechaFinal2_DdlMinuto", "59")
        _select(page, "select#ctl00_MainContent_CldFechaFinal2_DdlSegundo", "59")

        self._buscar(page)

    def _buscar(self, page):
        """
        Click en 'Buscar CFDI' y espera a que el UpdatePanel (AJAX) RENDERICE.

        El botón hace ocultaResultados() + postback parcial; networkidle NO basta
        (regresa antes de que las filas aparezcan → falso 0). Hay que esperar a que
        el spinner UpdateProgress1 se oculte y aparezcan filas o el panel "sin
        resultados".
        """
        from playwright.sync_api import TimeoutError as PWTimeout

        btn = page.query_selector("input#ctl00_MainContent_BtnBusqueda")
        if not btn:
            raise RuntimeError("No se encontró el botón de búsqueda.")
        btn.click()
        page.wait_for_timeout(800)  # dar tiempo a ocultaResultados() + arranque del postback
        try:
            page.wait_for_function(
                """() => {
                    const filas = document.querySelectorAll('input.ListaFolios').length;
                    const noRes = document.getElementById('ctl00_MainContent_PnlNoResultados');
                    const sinResultados = !!(noRes && noRes.offsetParent !== null);
                    const prog = document.getElementById('ctl00_MainContent_UpdateProgress1');
                    const cargando = !!(prog && prog.offsetParent !== null);
                    return !cargando && (filas > 0 || sinResultados);
                }""",
                timeout=60_000,
            )
        except PWTimeout:
            logger.warning("[CIEC] La búsqueda no terminó de renderizar a tiempo.")
        try:
            page.wait_for_load_state("networkidle", timeout=10_000)
        except PWTimeout:
            pass

    # ------------------------------------------------------------------
    # Extracción de filas (UUID + URL de descarga) y descarga
    # ------------------------------------------------------------------

    def _extraer_filas(self, page) -> List[dict]:
        """
        Lee todas las filas de resultados (la paginación es client-side, así que
        están todas en el DOM). De cada una saca el UUID (input.ListaFolios) y la
        URL relativa RecuperaCfdi.aspx?Datos=<token> del ícono de descarga.
        """
        filas = page.evaluate(
            r"""() => {
                const cbs = Array.from(document.querySelectorAll('input.ListaFolios'));
                const spans = Array.from(document.querySelectorAll('span[name="BtnDescarga"]'));
                const out = [];
                for (let i = 0; i < cbs.length; i++) {
                    let url = null;
                    if (spans[i]) {
                        const oc = spans[i].getAttribute('onclick') || '';
                        const m = oc.match(/RecuperaCfdi\.aspx\?Datos=([^']+)/);
                        if (m) url = 'RecuperaCfdi.aspx?Datos=' + m[1];
                    }
                    out.push({ uuid: (cbs[i].value || '').toUpperCase(), url });
                }
                return out;
            }"""
        )
        for f in filas:
            if f["url"]:
                f["url"] = f"{PORTAL_URL}/{f['url']}"
        return filas

    def _descargar_xml(self, page, url: str, dest: Path) -> bool:
        """
        Descarga un XML navegando a RecuperaCfdi.aspx?Datos=<token>. El server
        responde con el adjunto; goto aborta la navegación pero expect_download
        captura el archivo. Replica exactamente lo que hace window.open del portal.

        Usa la misma página de resultados (las URLs ya se extrajeron antes), por
        eso no hace falta una pestaña aparte.
        """
        from playwright.sync_api import TimeoutError as PWTimeout

        try:
            with page.expect_download(timeout=DOWNLOAD_TIMEOUT_MS) as di:
                try:
                    page.goto(url, wait_until="commit")
                except Exception:
                    pass  # ERR_ABORTED: la navegación se convirtió en descarga
            download = di.value
            download.save_as(str(dest))
            return dest.exists() and dest.stat().st_size > 0
        except PWTimeout:
            return False  # no bajó archivo (posible cuota agotada o error)
        except Exception as e:
            logger.debug("[CIEC] error descargando %s: %s", dest.name, e)
            return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalizar_tipos(tipo: str) -> List[str]:
    """Convierte el arg de tipo en la lista de tipos a descargar."""
    t = (tipo or "").strip().upper()
    if t in ("E", "EMITIDOS"):
        return ["E"]
    if t in ("R", "RECIBIDOS"):
        return ["R"]
    # "RE", "ER", "AMBOS", "ALL", "B", vacío → ambos (recibidos primero)
    return ["R", "E"]


def _select(page, sel: str, val: str):
    if page.query_selector(sel):
        try:
            page.select_option(sel, val)
        except Exception as e:
            logger.debug("[CIEC] no se pudo seleccionar %s=%s: %s", sel, val, e)


def _dias(fi: date, ff: date):
    d = fi
    while d <= ff:
        yield d
        d += timedelta(days=1)


def _es_uuid(text: str) -> bool:
    return bool(re.fullmatch(
        r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}",
        text.strip(),
    ))


# ---------------------------------------------------------------------------
# Función pública de conveniencia
# ---------------------------------------------------------------------------

def descargar_cfdi_ciec(
    rfc: str,
    ciec: str,
    fecha_inicio: date,
    fecha_fin: date,
    tipo_comprobante: str = "RE",
    directorio_salida: str = "./cfdi/",
    max_registros: int = 2000,
    headless: bool = False,
) -> List[Path]:
    """
    Descarga CFDIs del portal del SAT usando autenticación CIEC.

    tipo_comprobante: "R" (recibidos), "E" (emitidos) o "RE"/ambos (default).
    El browser es VISIBLE: resuelve el captcha y haz clic en «Enviar».
    El resto (búsqueda + descarga item por item) es automático.
    """
    client = CIECClient(rfc=rfc, ciec=ciec, headless=headless)
    return client.descargar(
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo_comprobante=tipo_comprobante,
        directorio_salida=directorio_salida,
        max_registros=max_registros,
    )

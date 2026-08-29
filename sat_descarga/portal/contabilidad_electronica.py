"""
Envío de la Contabilidad Electrónica (Anexo 24) al portal del SAT con e.firma.

Portal: https://ceportalenvioprod.clouda.sat.gob.mx/ — ASP.NET MVC, sesión de
15 minutos (`#lifeTime`), login por el NIDP del SAT (mismo formulario que el
resto de los scrapers: `_login_efirma` de portal/login.py, sin captcha).

Flujo real (mapeado en el repo `diot`, contabilidad-electronica/steps_contabilidad_2025.md):

  1. login e.firma
  2. modal «Contribuyente Amparado» → botón `#btnLogout` (postea a
     /Envio/RedirecAmparados; a pesar del id NO cierra sesión, es el paso normal)
  3. /Envio/Carga, dos secciones:
     a) «¿Desea sellar su información?» — `#rbNo` viene marcado; con `#rbSi` se
        abre `#frmEFirma` (cer/key/contraseña) para sellar los XML
     b) lista de archivos: `#btnAddFile` agrega un <li> a `#ulArchivos` con id
        aleatorio; dentro van `#flDocumento<ID>` (file oculto), `#cmbTipoPoliza<ID>`
        (motivo, se puebla al elegir archivo) y `#status<ID>` (resultado)
  4. `#btnEnviar` → modal de resumen (Documento/Motivo/Año/Mes) → `.btnDo`
  5. por archivo: éxito (`alert-success`, "recibido con éxito ... Folio No. N")
     o error (`alert-danger`)
  6. el acuse de recepción se baja directo de
     /ConsultaAcuses/AR_<folio>?folio=<folio>&tipoAcuse=1

OJO — el acuse de RECEPCIÓN no ampara el cumplimiento: el propio PDF dice que el
archivo "será procesado" y que hay que verificar el acuse de ACEPTACIÓN o
RECHAZO en Buzón Tributario › Contabilidad Electrónica › Consultas. Esa segunda
fase todavía no está automatizada aquí (falta mapear esa pantalla).
"""

from __future__ import annotations

import logging
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Callable, Optional

logger = logging.getLogger(__name__)

URL_PORTAL = "https://ceportalenvioprod.clouda.sat.gob.mx/"
URL_CARGA = "https://ceportalenvioprod.clouda.sat.gob.mx/Envio/Carga"
URL_ACUSE = ("https://ceportalenvioprod.clouda.sat.gob.mx/ConsultaAcuses/"
             "AR_{folio}?folio={folio}&tipoAcuse=1")

LOGIN_TIMEOUT_MS = 120_000
LOGIN_INTENTOS = 3
ENVIO_TIMEOUT_MS = 180_000

# Nomenclatura del Anexo 24: RFC + AAAA + MM + tipo.
RE_NOMBRE_ZIP = re.compile(r"^([A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3})(\d{4})(\d{2})([A-Z]{2})$")

TIPOS_ARCHIVO = {
    "CT": "Catálogo de cuentas",
    "BN": "Balanza de comprobación (normal)",
    "BC": "Balanza de comprobación (complementaria)",
    "PL": "Pólizas del periodo",
    "XF": "Auxiliar de folios",
    "XC": "Auxiliares de cuenta y subcuenta",
}
# Raíz esperada del XML por tipo — atrapa el ZIP bien nombrado con contenido que no
# corresponde (p. ej. una balanza renombrada como catálogo).
RAIZ_ESPERADA = {"CT": "Catalogo", "BN": "Balanza", "BC": "Balanza",
                 "PL": "Polizas", "XF": "AuxiliarFolios", "XC": "AuxiliarCtas"}

# El SAT descomprime el ZIP a un temporal y a veces lo lee antes de que exista.
# Es una carrera del lado de ellos: reintentando el mismo archivo entra.
RE_ERROR_TRANSITORIO = re.compile(
    r"could not find file|se present[óo] un error durante la carga|"
    r"tiempo de espera|timeout|intente (?:de )?nuevo",
    re.I,
)
RE_FOLIO = re.compile(r"Folio\s*No\.?\s*(\d{10,})", re.I)
RE_FECHA_ACUSE = re.compile(r"el d[íi]a\s+([\d/]+)\s+a las\s+([\d:]+)", re.I)

# -- selectores -------------------------------------------------------------
SEL_AMPARADOS = "form[action='/Envio/RedirecAmparados'] #btnLogout"
SEL_RB_SI = "#rbSi"
SEL_LBL_SI = 'label[for="rbSi"]'
SEL_DIV_EFIRMA = "#divEFirma"
SEL_HF_RFC = "#hfRfc"
SEL_CER_BTN = "#txtCertificado button"
SEL_KEY_BTN = "#txtLlavePrivada button"
SEL_CER_FILE = "#certificate"
SEL_KEY_FILE = "#privateKey"
SEL_PWD_LLAVE = "#pwdPassLlave"
SEL_TXT_RFC = "#txtRfc"
SEL_ERRORES_FIEL = "#erroresFiel"
SEL_BTN_ADD = "#btnAddFile"
SEL_UL = "#ulArchivos"
SEL_BTN_ENVIAR = "#btnEnviar"
SEL_MODAL_DO = ".modal-content .btnDo"
SEL_MODAL_CANCEL = ".modal-content .btnClose"


# ---------------------------------------------------------------------------
# Inventario de los ZIP (independiente del portal)
# ---------------------------------------------------------------------------

def _sin_acentos(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s or "")
                   if unicodedata.category(c) != "Mn").lower()


def inspeccionar_zip(path) -> dict:
    """Lee un ZIP de contabilidad electrónica y coteja nombre contra contenido.

    Devuelve dict con rfc/anio/mes/tipo/... y `problemas`: lista de
    inconsistencias. Un ZIP con problemas NO debería enviarse: el SAT lo
    rechazaría en la validación posterior (y el acuse de recepción no avisa).
    """
    path = Path(path)
    info = {"path": str(path), "archivo": path.name, "problemas": []}

    m = RE_NOMBRE_ZIP.match(path.stem.upper())
    if not m:
        info["problemas"].append(
            f"«{path.name}» no cumple la nomenclatura RFC+AAAA+MM+TIPO del Anexo 24")
        return info

    rfc, anio, mes, tipo = m.groups()
    info.update(rfc=rfc, anio=anio, mes=mes, tipo=tipo,
                tipo_desc=TIPOS_ARCHIVO.get(tipo, tipo))
    if tipo not in TIPOS_ARCHIVO:
        info["problemas"].append(f"tipo de archivo «{tipo}» desconocido")
    if not (1 <= int(mes) <= 13):
        info["problemas"].append(f"mes «{mes}» fuera de rango (01-13)")

    try:
        with zipfile.ZipFile(path) as zf:
            nombres = [n for n in zf.namelist() if not n.startswith("__MACOSX")]
            if len(nombres) != 1:
                info["problemas"].append(
                    f"el ZIP trae {len(nombres)} archivos; debe traer solo el XML")
            if not nombres:
                return info
            interno = nombres[0]
            if Path(interno).stem.upper() != path.stem.upper():
                info["problemas"].append(
                    f"el XML de adentro se llama «{interno}», no «{path.stem}.xml»")
            raiz = ET.fromstring(zf.read(interno))
    except (zipfile.BadZipFile, ET.ParseError, OSError) as e:
        info["problemas"].append(f"no se pudo leer el ZIP/XML: {e}")
        return info

    tag = raiz.tag.split("}")[-1]
    a = raiz.attrib
    info.update(raiz=tag, version=a.get("Version", ""),
                tipo_envio=a.get("TipoEnvio", ""))
    esperada = RAIZ_ESPERADA.get(tipo)
    if esperada and tag != esperada:
        info["problemas"].append(
            f"el XML es <{tag}> pero el nombre dice {tipo} (esperaba <{esperada}>)")
    for campo, esperado in (("RFC", rfc), ("Anio", anio), ("Mes", mes)):
        # el catálogo de cuentas no lleva Mes en algunas versiones: solo checar si viene
        actual = a.get(campo)
        if actual is not None and actual != esperado:
            info["problemas"].append(
                f"{campo} del XML = «{actual}» ≠ «{esperado}» del nombre del archivo")
    return info


def inventario(paths) -> list[dict]:
    """Inspecciona varios ZIP y los ordena por RFC/ejercicio/periodo/tipo."""
    filas = [inspeccionar_zip(p) for p in paths]
    return sorted(filas, key=lambda f: (f.get("rfc", ""), f.get("anio", ""),
                                        f.get("mes", ""), f.get("tipo", "")))


# ---------------------------------------------------------------------------
# Portal
# ---------------------------------------------------------------------------

class EnviadorCE:
    """Envía ZIPs de contabilidad electrónica al portal del SAT.

    Por default NO envía: llega hasta el modal de resumen, lo lee y cancela
    (mismo contrato que `PresentadorDiot`). El envío real requiere enviar=True.
    """

    def __init__(self, headless: bool = True,
                 progreso: Optional[Callable[[str], None]] = None,
                 reintentos: int = 4):
        self.headless = headless
        self.progreso = progreso or (lambda msg: None)
        self.reintentos = max(1, reintentos)

    def _paso(self, msg: str):
        logger.info("[CE] %s", msg)
        self.progreso(msg)

    # -- flujo principal ---------------------------------------------------

    def enviar(self, cer_path: str, key_path: str, password: str,
               zips: list, *, sellar: bool = True, enviar: bool = False,
               motivo: str = "mensual", salida: Optional[str] = None) -> dict:
        """Sube `zips` (rutas a .zip) uno por uno. Devuelve dict con resultados."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            raise ImportError("playwright no está instalado:\n"
                              "  pip install playwright\n  playwright install chromium")
        from .setup import asegurar_chromium, lanzar_chromium

        rutas = [Path(z) for z in zips]
        faltantes = [str(p) for p in rutas if not p.is_file()]
        if faltantes:
            raise FileNotFoundError("no existen: " + ", ".join(faltantes))

        fichas = [inspeccionar_zip(p) for p in rutas]
        con_problemas = [f for f in fichas if f["problemas"]]
        if con_problemas:
            detalle = "; ".join(f"{f['archivo']}: {f['problemas'][0]}"
                                for f in con_problemas)
            raise ValueError(f"ZIPs que no pasan la revisión previa → {detalle}")

        rfcs = {f["rfc"] for f in fichas}
        if len(rfcs) > 1:
            raise ValueError(
                "los ZIPs son de varios RFC ({}); una sesión = una empresa"
                .format(", ".join(sorted(rfcs))))
        rfc_lote = rfcs.pop()

        resultado = {"rfc": rfc_lote, "enviados": [], "fallidos": [],
                     "estado": "enviado" if enviar else "validado"}

        asegurar_chromium()
        with sync_playwright() as p:
            browser = lanzar_chromium(p, headless=self.headless, slow_mo=60)
            context = browser.new_context(accept_downloads=True)
            page = context.new_page()
            try:
                self._login(page, cer_path, key_path, password)
                self._cerrar_amparados(page)

                rfc_sesion = (page.get_attribute(SEL_HF_RFC, "value") or "").upper()
                if rfc_sesion and rfc_sesion != rfc_lote:
                    # sin esto se podrían subir los archivos de una empresa con la
                    # sesión de otra: el portal los acepta y el rechazo llega después
                    raise ValueError(
                        f"la sesión es de {rfc_sesion} pero los ZIPs son de "
                        f"{rfc_lote}. No se envió nada.")
                self._paso(f"Sesión de {rfc_sesion or rfc_lote}.")

                if sellar:
                    self._sellar(page, cer_path, key_path, password, rfc_lote)

                for ficha in fichas:
                    r = self._enviar_uno(page, context, ficha, motivo, enviar,
                                         salida)
                    # clasificar por estado, no por folio: en modo validación
                    # no hay folio y aun así el archivo pasó
                    if r.get("estado") == "error":
                        resultado["fallidos"].append(r)
                    else:
                        resultado["enviados"].append(r)
                return resultado
            except Exception:
                try:
                    dest = Path(salida) if salida else Path(fichas[0]["path"]).parent
                    dest.mkdir(parents=True, exist_ok=True)
                    page.screenshot(path=str(dest / f"error_ce_{rfc_lote}.png"),
                                    full_page=True)
                    (dest / f"error_ce_{rfc_lote}.html").write_text(
                        page.content(), encoding="utf-8")
                    logger.error("[CE] Falla en %s — evidencia en %s", page.url, dest)
                except Exception:  # noqa: BLE001 — no tapar el error original
                    pass
                raise
            finally:
                browser.close()

    # -- pasos -------------------------------------------------------------

    def _login(self, page, cer_path, key_path, password):
        """Login e.firma con reintentos.

        El NIDP del SAT se atora de vez en cuando a media redirección y deja la
        página en /nidp/wsfed/ep sin avanzar: 2 fallas en 15 entradas el
        2026-08-29, y la primera entró al reintentar un minuto después. No es
        bloqueo por frecuencia (13 logins seguidos en 28 min salieron bien), así
        que lo que corresponde es reintentar, no esperar.
        """
        from .login import iniciar_sesion_fiel
        for intento in range(1, LOGIN_INTENTOS + 1):
            self._paso(f"Login con e.firma en el portal de contabilidad "
                       f"electrónica (intento {intento}/{LOGIN_INTENTOS})...")
            try:
                iniciar_sesion_fiel(
                    page, cer_path, key_path, password, URL_PORTAL,
                    # el aterrizaje es /Envio/Carga o la interstitial de
                    # amparados; basta con haber salido del host del NIDP
                    exito=lambda url: ("clouda.sat.gob.mx" in url
                                       and "nidp" not in url),
                    timeout_ms=LOGIN_TIMEOUT_MS,
                )
                return
            except RuntimeError as e:
                if intento == LOGIN_INTENTOS:
                    raise
                logger.warning("[CE] El login no completó (%s); reintento.",
                               str(e)[:160])

    def _cerrar_amparados(self, page):
        """El aviso «Contribuyente Amparado» se interpone en cada entrada.

        El botón trae id="btnLogout" pero su form postea a /Envio/RedirecAmparados
        y es el camino normal hacia /Envio/Carga — no cierra la sesión.
        """
        from playwright.sync_api import TimeoutError as PWTimeout
        try:
            page.wait_for_selector(SEL_AMPARADOS, timeout=8_000)
        except PWTimeout:
            return
        self._paso("Aviso de contribuyente amparado → Aceptar.")
        page.click(SEL_AMPARADOS)
        page.wait_for_selector(SEL_BTN_ADD, timeout=30_000)

    def _sellar(self, page, cer_path, key_path, password, rfc_lote):
        """Marca «Sí» al sellado y carga la e.firma en `#frmEFirma`."""
        from playwright.sync_api import TimeoutError as PWTimeout
        self._paso("Sellando la información con la e.firma...")
        self._activar_sellado(page)
        page.wait_for_selector(SEL_PWD_LLAVE, state="visible", timeout=20_000)

        def _cargar():
            # Igual que en la DIOT: los file inputs van ocultos y el JS que parsea
            # el .cer (y llena #txtRfc/#cerB64/#numeroSerie) cuelga del botón
            # «Buscar». Inyectar directo al input no siempre dispara ese parseo.
            try:
                with page.expect_file_chooser(timeout=8_000) as fc:
                    page.click(SEL_CER_BTN)
                fc.value.set_files(cer_path)
                with page.expect_file_chooser(timeout=8_000) as fc:
                    page.click(SEL_KEY_BTN)
                fc.value.set_files(key_path)
            except Exception as e:  # noqa: BLE001
                logger.info("[CE] Sin file chooser (%s); inyectando al input.",
                            type(e).__name__)
                page.set_input_files(SEL_CER_FILE, cer_path)
                page.set_input_files(SEL_KEY_FILE, key_path)
            page.fill(SEL_PWD_LLAVE, password)

        for intento in range(1, 4):
            _cargar()
            try:
                page.wait_for_function(
                    "() => { const el = document.querySelector('#txtRfc');"
                    "        return el && el.value && el.value.length >= 12; }",
                    timeout=15_000)
                break
            except PWTimeout:
                logger.info("[CE] #txtRfc sigue vacío (intento %d/3).", intento)
        else:
            raise RuntimeError("el portal nunca parseó el .cer (#txtRfc vacío)")

        rfc_cer = (page.input_value(SEL_TXT_RFC) or "").strip().upper()
        if rfc_cer != rfc_lote:
            # es el error que el portal reporta como "El certificado no corresponde
            # al contribuyente firmado"; mejor atajarlo antes de subir nada
            raise ValueError(f"el .cer es de {rfc_cer} y los ZIPs son de {rfc_lote}")

        err = self._texto(page, SEL_ERRORES_FIEL)
        if err:
            raise ValueError(f"el portal rechazó la e.firma: {err}")

    def _activar_sellado(self, page):
        """Marca «Sí» en el sellado y espera a que se abra `#divEFirma`.

        El radio va con el patrón input+label estilizado y el handler del portal
        cuelga del LABEL: `page.check("#rbSi")` deja el input marcado pero
        `#divEFirma` se queda en display:none (visto 2026-08-29).
        """
        from playwright.sync_api import TimeoutError as PWTimeout
        try:
            page.click(SEL_LBL_SI)
            page.wait_for_selector(SEL_DIV_EFIRMA, state="visible", timeout=10_000)
            return
        except PWTimeout:
            logger.info("[CE] El label no abrió #divEFirma; forzando por JS.")
        page.eval_on_selector(
            SEL_RB_SI,
            "el => { el.checked = true;"
            "        el.dispatchEvent(new Event('change', {bubbles: true}));"
            "        el.dispatchEvent(new Event('click', {bubbles: true})); }")
        page.wait_for_selector(SEL_DIV_EFIRMA, state="visible", timeout=10_000)

    def _enviar_uno(self, page, context, ficha, motivo, enviar, salida) -> dict:
        """Agrega un archivo, lo manda y lee el resultado, con reintentos."""
        etiqueta = f"{ficha['archivo']} ({ficha['tipo_desc']} {ficha['anio']}-{ficha['mes']})"
        ultimo_error = ""
        for intento in range(1, self.reintentos + 1):
            self._paso(f"{etiqueta} — intento {intento}/{self.reintentos}")
            item = self._agregar_archivo(page, ficha["path"], motivo)

            page.click(SEL_BTN_ENVIAR)
            page.wait_for_selector(f"{SEL_MODAL_DO}:visible", timeout=30_000)
            resumen = self._leer_modal(page)

            if not enviar:
                page.click(SEL_MODAL_CANCEL)
                self._paso(f"{etiqueta} — validado, NO enviado (falta --enviar).")
                return {**ficha, "resumen_portal": resumen, "folio": None,
                        "estado": "validado"}

            page.click(SEL_MODAL_DO)
            estado = self._esperar_status(page, item)
            if estado["ok"]:
                folio = estado["folio"]
                self._paso(f"{etiqueta} — recibido, folio {folio}")
                acuse = self._bajar_acuse(context, folio, ficha, salida)
                return {**ficha, "folio": folio, "fecha": estado.get("fecha"),
                        "acuse": acuse, "estado": "enviado",
                        "intentos": intento}
            ultimo_error = estado["mensaje"]
            if not RE_ERROR_TRANSITORIO.search(ultimo_error):
                break  # error de fondo (XML inválido, periodo cerrado): no insistir
            logger.info("[CE] Error transitorio del SAT; reintento. (%s)",
                        ultimo_error[:120])
        return {**ficha, "folio": None, "estado": "error", "mensaje": ultimo_error}

    def _agregar_archivo(self, page, zip_path: str, motivo: str) -> str:
        """Clic en «Agregar», adjunta el ZIP y elige el motivo. Devuelve el id del <li>."""
        from playwright.sync_api import TimeoutError as PWTimeout

        previos = set(self._ids_items(page))
        item = None
        for clic in range(1, 4):
            page.click(SEL_BTN_ADD)
            try:
                page.wait_for_function(
                    "n => document.querySelectorAll('#ulArchivos > li').length > n",
                    arg=len(previos), timeout=8_000)
            except PWTimeout:
                # El PRIMER «Agregar» después de cargar la e.firma se consume
                # procesándola (#modifiedFiel pasa de 1 a 0) y no crea renglón:
                # sin error, sin petición, sin alerta. Hay que volver a picarlo.
                # (medido contra el portal el 2026-08-29)
                logger.info("[CE] «Agregar» no creó renglón (clic %d); reintento.",
                            clic)
                continue
            nuevos = [i for i in self._ids_items(page) if i not in previos]
            if nuevos:
                item = nuevos[-1]
                break
        if not item:
            raise RuntimeError("«Agregar» no creó un renglón nuevo en #ulArchivos "
                               "tras 3 clics")

        try:
            with page.expect_file_chooser(timeout=8_000) as fc:
                page.click(f"#txtDocumento{item} button")
            fc.value.set_files(zip_path)
        except Exception as e:  # noqa: BLE001
            logger.info("[CE] Sin file chooser para el ZIP (%s); inyectando.",
                        type(e).__name__)
            page.set_input_files(f"#flDocumento{item}", zip_path)

        self._elegir_motivo(page, item, motivo)
        return item

    def _elegir_motivo(self, page, item: str, motivo: str):
        """El combo de motivo se puebla al elegir el archivo (viene disabled)."""
        sel = f"#cmbTipoPoliza{item}"
        # El portal no deja un placeholder + opciones: al leer el ZIP REEMPLAZA
        # la lista por los motivos válidos para ese tipo de archivo, y para una
        # balanza normal eso es una sola opción («Envio Mensual», value=7). Por
        # eso la espera es "hay alguna opción real", no "hay más de una".
        page.wait_for_function(
            "s => { const el = document.querySelector(s);"
            "       if (!el || el.disabled) return false;"
            "       return Array.from(el.options)"
            "                   .some(o => o.value && o.value !== '-1'); }",
            arg=sel, timeout=30_000)
        opciones = page.eval_on_selector(
            sel, "el => Array.from(el.options).map(o => [o.value, o.text.trim()])")
        buscado = _sin_acentos(motivo)
        for valor, texto in opciones:
            if valor != "-1" and buscado in _sin_acentos(texto):
                page.select_option(sel, valor)
                return
        disponibles = ", ".join(f"«{t}»" for _, t in opciones if _ != "-1")
        raise ValueError(f"no hay motivo que empate con «{motivo}». "
                         f"Opciones del portal: {disponibles}")

    def _esperar_status(self, page, item: str) -> dict:
        """Espera el renglón de resultado y lo clasifica."""
        sel = f"#status{item}"
        # El portal reusa el mismo <span> para el avance y para el resultado:
        # primero escribe "Enviando archivo. Por favor espere..." y después el
        # folio o el error. Esperar a que HAYA texto se queda con el mensaje
        # intermedio (visto 2026-08-29), así que hay que esperar el estado final.
        page.wait_for_function(
            "s => { const el = document.querySelector(s); if (!el) return false;"
            "       const t = (el.innerText || el.textContent || '').trim();"
            "       if (!t) return false;"
            "       if (/folio/i.test(t)) return true;"
            "       return !/(espere|procesando|enviando|cargando)/i.test(t); }",
            arg=sel, timeout=ENVIO_TIMEOUT_MS)
        datos = page.eval_on_selector(
            sel,
            "el => ({txt: el.innerText || el.textContent,"
            "        cls: (el.closest('.notificacion') || {}).className || ''})")
        texto = (datos["txt"] or "").strip()
        ok = "alert-success" in datos["cls"]
        m = RE_FOLIO.search(texto)
        if ok and not m:
            ok = False
        f = RE_FECHA_ACUSE.search(texto)
        return {"ok": ok, "mensaje": texto,
                "folio": m.group(1) if m else None,
                "fecha": f"{f.group(1)} {f.group(2)}" if f else None}

    def _bajar_acuse(self, context, folio: str, ficha: dict,
                     salida: Optional[str]) -> Optional[str]:
        """Baja el acuse de recepción por su URL directa (sin pelear con el visor)."""
        destino = Path(salida) if salida else Path(ficha["path"]).parent
        destino.mkdir(parents=True, exist_ok=True)
        dest = destino / f"AR_{folio}.pdf"
        url = URL_ACUSE.format(folio=folio)
        try:
            resp = context.request.get(url, timeout=60_000)
            cuerpo = resp.body()
            if cuerpo[:5] == b"%PDF-":
                dest.write_bytes(cuerpo)
                self._paso(f"Acuse guardado: {dest}")
                return str(dest)
            logger.warning("[CE] %s no devolvió PDF (status %s)", url, resp.status)
        except Exception as e:  # noqa: BLE001
            logger.warning("[CE] No se pudo bajar el acuse %s: %s", folio, e)
        return None

    # -- utilidades --------------------------------------------------------

    @staticmethod
    def _ids_items(page) -> list[str]:
        """Ids de los <li> de #ulArchivos, sin el prefijo 'li'."""
        return page.eval_on_selector_all(
            f"{SEL_UL} > li", "els => els.map(e => e.id.replace(/^li/, ''))")

    @staticmethod
    def _texto(page, selector: str) -> str:
        el = page.query_selector(selector)
        if not el or not el.is_visible():
            return ""
        return (el.inner_text() or "").strip()

    @staticmethod
    def _leer_modal(page) -> list[dict]:
        """Tabla del modal de confirmación: Documento / Motivo / Año / Mes."""
        return page.eval_on_selector_all(
            ".modal-content tbody tr",
            "rs => rs.map(r => { const c = r.querySelectorAll('td');"
            "  return {documento: c[0]?.innerText.trim(), motivo: c[1]?.innerText.trim(),"
            "          anio: c[2]?.innerText.trim(), mes: c[3]?.innerText.trim()}; })")


def enviar_contabilidad_fiel(cer_path: str, key_path: str, password: str,
                             zips: list, **kw) -> dict:
    """Atajo funcional, paralelo a `presentar_diot_fiel`."""
    headless = kw.pop("headless", True)
    progreso = kw.pop("progreso", None)
    reintentos = kw.pop("reintentos", 4)
    return EnviadorCE(headless=headless, progreso=progreso,
                      reintentos=reintentos).enviar(
        cer_path, key_path, password, zips, **kw)

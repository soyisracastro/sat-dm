"""
Inicialización de Playwright para distribución empaquetada.

En el flujo dev (con Playwright instalado vía pip y `playwright install chromium`)
no se necesita esto: Playwright encuentra Chromium en su path por default.

En el flujo empaquetado (PyInstaller `sat-agent.exe`), Chromium NO viaja
adentro del binario (pesaría ~170 MB). En su lugar:

1. Establecemos `PLAYWRIGHT_BROWSERS_PATH` apuntando a una carpeta del usuario
   (`%LOCALAPPDATA%\\TodoConta\\playwright-browsers\\` en Windows,
   `~/.cache/todoconta/playwright-browsers/` en macOS/Linux).
2. Al arrancar el agente, `warmup_async()` descarga/actualiza los browsers en
   background; si un endpoint del portal llega antes, `asegurar_chromium()`
   bloquea hasta que estén listos.
3. Subsiguientes invocaciones son no-ops (los browsers ya están en disco).

Cada release de Playwright fija REVISIONES exactas de browser (en
`driver/package/browsers.json`), y desde 1.49 el modo headless usa un binario
aparte (`chromium_headless_shell`). Por eso la verificación es por revisión y
cubre ambos binarios: una carpeta de una versión anterior NO cuenta como
instalado (ese era el bug del "Executable doesn't exist" tras actualizar).

La descarga real la hace el driver de Playwright (no `subprocess [sys.executable]`,
que en un .exe de PyInstaller apunta al .exe mismo y no a Python).
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import threading
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

# Browsers que el portal necesita, con los nombres tal cual aparecen en
# browsers.json. Punto de extensión: si un trámite futuro requiere otra
# dependencia de Playwright, se agrega aquí.
_NAVEGADORES_REQUERIDOS = ("chromium", "chromium-headless-shell")

# Fragmentos que delatan "el binario del browser no está" en errores de launch.
# OJO: no matchear "BrowserType.launch" a secas — aparece también en timeouts.
_SENALES_BROWSER_FALTANTE = ("Executable doesn't exist", "playwright install")


def _browsers_dir() -> Path:
    """Carpeta donde se descarga Chromium para el agente empaquetado."""
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "TodoConta" / "playwright-browsers"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "TodoConta" / "playwright-browsers"
    # Linux / otros
    cache = os.environ.get("XDG_CACHE_HOME") or str(Path.home() / ".cache")
    return Path(cache) / "todoconta" / "playwright-browsers"


# True si PLAYWRIGHT_BROWSERS_PATH venía seteada desde afuera (cache compartido,
# p. ej. el ms-playwright de dev): ahí desactivamos la GC del install para no
# borrar revisiones que otros proyectos sí usan.
_path_externo = False


def configurar_playwright_browsers_path() -> Path:
    """
    Establece la env var `PLAYWRIGHT_BROWSERS_PATH` y devuelve el path.

    Idempotente: si ya está seteada, la respeta (override manual del usuario).
    """
    global _path_externo
    existing = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if existing:
        _path_externo = True
        return Path(existing)
    path = _browsers_dir()
    path.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(path)
    return path


# ---------------------------------------------------------------------------
# Estado del navegador (lo consume /health y el banner de la UI)
# ---------------------------------------------------------------------------

_estado_lock = Lock()
_estado: dict = {"estado": "pendiente", "detalle": None}
# estados: "pendiente" | "instalando" | "listo" | "error"


def _set_estado(estado: str, detalle: str | None = None) -> None:
    with _estado_lock:
        _estado["estado"] = estado
        _estado["detalle"] = detalle


def estado_navegador() -> dict:
    """Copia thread-safe del estado actual del navegador de descargas."""
    with _estado_lock:
        return dict(_estado)


# ---------------------------------------------------------------------------
# Verificación por revisión exacta
# ---------------------------------------------------------------------------


def _browsers_json_path() -> Path | None:
    """
    Localiza el `browsers.json` del paquete playwright instalado (trae la
    revisión exacta que esta versión espera de cada browser). Funciona igual
    en dev y en el bundle PyInstaller (viaja en los datas del .spec).
    """
    try:
        import playwright  # type: ignore
    except ImportError:
        return None
    path = Path(playwright.__file__).parent / "driver" / "package" / "browsers.json"
    return path if path.is_file() else None


def _revisiones_requeridas() -> dict[str, str] | None:
    """{"chromium": "1223", "chromium-headless-shell": "1223"} o None si no se pudo leer."""
    path = _browsers_json_path()
    if path is None:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        revisiones = {
            b["name"]: str(b["revision"])
            for b in data.get("browsers", [])
            if b.get("name") in _NAVEGADORES_REQUERIDOS
        }
    except (OSError, ValueError, KeyError, TypeError):
        return None
    if set(revisiones) != set(_NAVEGADORES_REQUERIDOS):
        return None
    return revisiones


def _dir_navegador(nombre: str, revision: str) -> str:
    """Convención de Playwright: "chromium-headless-shell" rev 1223 → "chromium_headless_shell-1223"."""
    return f"{nombre.replace('-', '_')}-{revision}"


def _navegadores_instalados(browsers_path: Path) -> bool:
    """
    True si TODOS los browsers requeridos están en disco en la revisión exacta
    que pide la versión instalada de Playwright. El marker
    `INSTALLATION_COMPLETE` lo escribe Playwright al terminar bien cada
    descarga, así que también descarta descargas interrumpidas.
    """
    if not browsers_path.exists():
        return False

    revisiones = _revisiones_requeridas()
    if revisiones is None:
        # Sin browsers.json no podemos validar revisión; pedimos al menos una
        # carpeta completa de cada binario (mejor que el viejo "cualquier
        # chromium-*", que ignoraba el headless shell).
        logger.warning(
            "[portal] No se pudo leer browsers.json — verificación de browsers "
            "sin revisión exacta"
        )
        prefijos = {n.replace("-", "_") + "-" for n in _NAVEGADORES_REQUERIDOS}
        encontrados: set[str] = set()
        for entry in browsers_path.iterdir():
            if not entry.is_dir():
                continue
            for prefijo in prefijos:
                if entry.name.startswith(prefijo) and (
                    entry / "INSTALLATION_COMPLETE"
                ).is_file():
                    encontrados.add(prefijo)
        return encontrados == prefijos

    return all(
        (browsers_path / _dir_navegador(nombre, rev) / "INSTALLATION_COMPLETE").is_file()
        for nombre, rev in revisiones.items()
    )


# ---------------------------------------------------------------------------
# Instalación
# ---------------------------------------------------------------------------

_install_lock = Lock()
_install_checked = False


def asegurar_chromium(force: bool = False) -> None:
    """
    Verifica que los browsers del portal estén instalados en la revisión que
    esta versión de Playwright requiere. Si no, los descarga con
    `playwright install chromium` (instala chromium + headless shell + ffmpeg).

    Thread-safe: solo se chequea/descarga una vez por proceso. Con `force=True`
    se re-verifica aunque ya hubiera pasado (auto-reparación tras un launch
    fallido).
    """
    global _install_checked
    if _install_checked and not force:
        return

    with _install_lock:
        if force:
            _install_checked = False
        if _install_checked:
            return

        browsers_path = configurar_playwright_browsers_path()

        if _navegadores_instalados(browsers_path):
            _set_estado("listo")
            _install_checked = True
            return

        logger.info(
            "[portal] Browsers no detectados (o revisión desactualizada) en %s "
            "— descargando…",
            browsers_path,
        )
        _set_estado(
            "instalando", "Descargando el navegador de descargas (~170 MB)…"
        )
        try:
            _instalar_chromium()
        except Exception as e:
            _set_estado("error", str(e))
            raise
        _set_estado("listo")
        _install_checked = True


def navegador_listo() -> bool:
    """
    Check rápido y sin lock: ¿el navegador ya está usable? Lo usa el worker de
    jobs para decidir si avisar al usuario que va a haber una descarga.
    """
    if _install_checked:
        return True
    return _navegadores_instalados(configurar_playwright_browsers_path())


def lanzar_chromium(playwright, **launch_kwargs):
    """
    `playwright.chromium.launch(...)` con red de seguridad: si el binario no
    existe (p. ej. la revisión cambió bajo nuestros pies o alguien borró el
    cache), fuerza la reinstalación y reintenta una vez.
    """
    asegurar_chromium()
    try:
        return playwright.chromium.launch(**launch_kwargs)
    except Exception as e:
        if not any(s in str(e) for s in _SENALES_BROWSER_FALTANTE):
            raise
        logger.warning(
            "[portal] Binario del navegador ausente al lanzar — reinstalando…"
        )
        asegurar_chromium(force=True)
        try:
            return playwright.chromium.launch(**launch_kwargs)
        except Exception as e2:
            raise RuntimeError(
                "No se pudo iniciar el navegador de descargas aunque se "
                "reinstaló. Verifica tu conexión a internet y vuelve a "
                "intentar; si persiste, reinstala TodoConta."
            ) from e2


def warmup_async() -> threading.Thread | None:
    """
    Lanza `asegurar_chromium()` en un hilo daemon al arrancar el agente, para
    que la descarga (primera vez o post-actualización) ocurra en background
    antes de que el usuario intente usar el portal.

    Con `SAT_AGENT_SKIP_BROWSER_WARMUP=1` no hace nada (tests/CI).
    """
    if os.environ.get("SAT_AGENT_SKIP_BROWSER_WARMUP") == "1":
        return None

    def _warmup() -> None:
        try:
            asegurar_chromium()
        except Exception:
            # El detalle ya quedó en estado_navegador(); el siguiente intento
            # de uso del portal reintenta.
            logger.exception("[portal] Warm-up del navegador falló")

    t = threading.Thread(target=_warmup, name="browser-warmup", daemon=True)
    t.start()
    return t


def _instalar_chromium() -> None:
    """
    Invoca el driver de Playwright para descargar Chromium.

    En dev (Python instalado): usa `python -m playwright install chromium`.
    En .exe empaquetado: invoca el driver de Playwright directamente.

    Si la descarga falla, levanta `RuntimeError` con detalle para que el
    endpoint que disparó esto pueda devolver un 503 al renderer.
    """
    cmd = _comando_install_chromium()
    if cmd is None:
        raise RuntimeError(
            "No se pudo localizar el driver de Playwright. Reinstala TodoConta."
        )

    env = os.environ.copy()
    if _path_externo:
        # Cache compartido (no exclusivo de TodoConta): que la GC del install
        # no borre revisiones que otros proyectos todavía usan.
        env["PLAYWRIGHT_SKIP_BROWSER_GC"] = "1"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min — Chromium pesa ~170MB
            env=env,
        )
    except subprocess.TimeoutExpired as e:
        raise RuntimeError(
            "La descarga de Chromium tardó demasiado (>10 min). "
            "Verifica tu conexión a internet."
        ) from e

    if result.returncode != 0:
        raise RuntimeError(
            "La descarga de Chromium falló:\n"
            f"  stdout: {result.stdout[-500:]}\n"
            f"  stderr: {result.stderr[-500:]}"
        )

    logger.info("[portal] Chromium instalado correctamente")


def _comando_install_chromium() -> list[str] | None:
    """
    Construye el comando para descargar Chromium según el entorno.

    Estrategias en orden de preferencia:
      1. .exe empaquetado (PyInstaller): usar el driver de Playwright directamente.
      2. Dev (Python disponible): `python -m playwright install chromium`.
    """
    # Caso PyInstaller: sys.frozen es True y sys.executable apunta al .exe.
    if getattr(sys, "frozen", False):
        try:
            from playwright._impl._driver import compute_driver_executable  # type: ignore
        except ImportError:
            return None
        try:
            node_path, cli_path = compute_driver_executable()
        except Exception:  # pragma: no cover — defensivo
            return None
        return [str(node_path), str(cli_path), "install", "chromium"]

    # Caso dev: hay un intérprete Python real.
    return [sys.executable, "-m", "playwright", "install", "chromium"]

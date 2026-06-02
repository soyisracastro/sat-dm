"""
Inicialización de Playwright para distribución empaquetada.

En el flujo dev (con Playwright instalado vía pip y `playwright install chromium`)
no se necesita esto: Playwright encuentra Chromium en su path por default.

En el flujo empaquetado (PyInstaller `sat-agent.exe`), Chromium NO viaja
adentro del binario (pesaría ~170 MB). En su lugar:

1. Establecemos `PLAYWRIGHT_BROWSERS_PATH` apuntando a una carpeta del usuario
   (`%LOCALAPPDATA%\\TodoConta\\playwright-browsers\\` en Windows,
   `~/.cache/todoconta/playwright-browsers/` en macOS/Linux).
2. La PRIMERA vez que un endpoint del portal (`/ciec/*`, `/fiel/*`) se invoca,
   se llama a `asegurar_chromium()` que descarga Chromium si no está presente.
3. Subsiguientes invocaciones son no-ops (Chromium ya está en disco).

La descarga real la hace el driver de Playwright (no `subprocess [sys.executable]`,
que en un .exe de PyInstaller apunta al .exe mismo y no a Python).
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)


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


def configurar_playwright_browsers_path() -> Path:
    """
    Establece la env var `PLAYWRIGHT_BROWSERS_PATH` y devuelve el path.

    Idempotente: si ya está seteada, la respeta (override manual del usuario).
    """
    existing = os.environ.get("PLAYWRIGHT_BROWSERS_PATH")
    if existing:
        return Path(existing)
    path = _browsers_dir()
    path.mkdir(parents=True, exist_ok=True)
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(path)
    return path


_install_lock = Lock()
_install_checked = False


def asegurar_chromium() -> None:
    """
    Verifica que Chromium esté instalado en la carpeta de browsers. Si no,
    lo descarga con `playwright install chromium`.

    Thread-safe: solo se chequea/descarga una vez por proceso.
    """
    global _install_checked
    if _install_checked:
        return

    with _install_lock:
        if _install_checked:
            return

        browsers_path = configurar_playwright_browsers_path()

        if _chromium_disponible(browsers_path):
            _install_checked = True
            return

        logger.info(
            "[portal] Chromium no detectado en %s — descargando…", browsers_path
        )
        _instalar_chromium()
        _install_checked = True


def _chromium_disponible(browsers_path: Path) -> bool:
    """
    Heurística rápida: existe al menos una carpeta `chromium-*` con un binario.

    No usamos Playwright para chequear porque sería circular (sync_playwright()
    pide Chromium para arrancar, justo lo que queremos evitar antes de descargarlo).
    """
    if not browsers_path.exists():
        return False
    for entry in browsers_path.iterdir():
        if entry.is_dir() and entry.name.startswith("chromium-"):
            # Búsqueda barata de un ejecutable conocido.
            for child in entry.rglob("chrome*"):
                if child.is_file():
                    return True
    return False


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

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min — Chromium pesa ~170MB
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

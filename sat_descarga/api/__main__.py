"""
Entry point del agente FastAPI para invocarlo como módulo.

Uso:
    python -m sat_descarga.api                    # default port 8787
    python -m sat_descarga.api --port 18787
    SAT_AGENT_PORT=18787 python -m sat_descarga.api

Este módulo es el blanco de PyInstaller cuando se empaqueta el agente Python
como `sat-agent.exe` para distribuirlo junto al shell Electron. Mantener este
archivo CHICO y CON IMPORTS DIFERIDOS para que PyInstaller pueda compilarlo
sin arrastrar el grafo completo de FastAPI/Playwright hasta que realmente se
ejecute.

Host fijo en 127.0.0.1 — el agente solo escucha localmente, nunca se expone a
la red.

Logging: cuando corre como `.exe` (PyInstaller con `console=False`), stdout
y stderr van a /dev/null en Windows. Para no perder el rastro de errores de
arranque, configuramos un logger que escribe a un archivo rotado en
`%LOCALAPPDATA%\\TodoConta\\logs\\agent.log` (Windows) o el equivalente en
otros SO. En dev (`uv run uvicorn ...`) este archivo igual se crea — el
usuario puede ignorarlo, los logs siguen viéndose en la terminal.
"""

from __future__ import annotations

import argparse
import logging
import logging.handlers
import os
import sys
from pathlib import Path


def _parse_port() -> int:
    parser = argparse.ArgumentParser(
        prog="sat-agent",
        description="Agente FastAPI local de TodoConta Desktop.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Puerto TCP a escuchar (default: $SAT_AGENT_PORT o 8787).",
    )
    args = parser.parse_args()

    if args.port is not None:
        return args.port

    env_port = os.environ.get("SAT_AGENT_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            print(
                f"[sat-agent] SAT_AGENT_PORT inválido: {env_port!r} — usando 8787",
                file=sys.stderr,
            )

    return 8787


def _ruta_log() -> Path:
    """
    Devuelve la ruta del archivo de log del agente. Crea el directorio si no
    existe.

    - Windows: %LOCALAPPDATA%\\TodoConta\\logs\\agent.log
    - macOS:   ~/Library/Logs/TodoConta/agent.log
    - Linux:   ~/.local/state/TodoConta/agent.log
    """
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "TodoConta" / "logs"
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Logs" / "TodoConta"
    else:
        base = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local" / "state"))) / "TodoConta"

    base.mkdir(parents=True, exist_ok=True)
    return base / "agent.log"


def _configurar_logging() -> Path:
    """
    Setup de logging hacia un archivo rotado (5 MB × 3 backups) + stderr.

    Captura el logger raíz (todos los módulos del agente) y los de uvicorn
    (`uvicorn`, `uvicorn.error`, `uvicorn.access`). Sin esto, cuando el .exe
    corre con `console=False`, todo error de arranque se pierde sin trazas.
    """
    log_path = _ruta_log()

    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_path,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)
    file_handler.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(file_handler)

    # stderr handler: útil en dev (terminal). En .exe con console=False no se
    # ve, pero no hace daño.
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(fmt)
    stderr_handler.setLevel(logging.INFO)
    root.addHandler(stderr_handler)

    # Forzar a uvicorn a usar la misma config (su default es loguear a stdout).
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        log = logging.getLogger(name)
        log.handlers.clear()
        log.addHandler(file_handler)
        log.addHandler(stderr_handler)
        log.propagate = False

    return log_path


def main() -> None:
    # CONFIGURAR LOGGING ANTES DE TODO. Con `console=False` en PyInstaller,
    # stdout/stderr van a /dev/null; cualquier crash previo a este punto se
    # pierde sin traza. El log file en %LOCALAPPDATA%\TodoConta\logs\agent.log
    # (Windows) es nuestra única vía de diagnóstico cuando un usuario reporta
    # "no arranca".
    log_path = _configurar_logging()
    log = logging.getLogger("sat-agent")

    # Bootstrap line: si ESTO se ve en el log, el binario arrancó y los
    # imports básicos funcionaron. Si NO se ve, es VC++ Redistributable
    # faltante, antivirus matando el proceso, o un crash de PyInstaller
    # antes del primer bytecode user-level.
    log.info(
        "[bootstrap] pid=%d argv=%s cwd=%s exe=%s platform=%s",
        os.getpid(),
        sys.argv,
        os.getcwd(),
        sys.executable,
        sys.platform,
    )

    try:
        port = _parse_port()
        host = "127.0.0.1"

        log.info("[bootstrap] log_path=%s host=%s port=%s", log_path, host, port)

        # Importar uvicorn y el app SOLO al ejecutar (no al importar el módulo).
        # PyInstaller agradece esto: el __main__ no arrastra el grafo hasta que
        # main() se invoca. Import absoluto porque PyInstaller corre __main__ sin
        # parent package context.
        log.info("[bootstrap] importando uvicorn + sat_descarga.api.server …")
        import uvicorn

        from sat_descarga.api.server import app

        log.info("[bootstrap] imports listos — arrancando uvicorn")
        # log_config=None: no sobreescribir la config que armamos arriba.
        uvicorn.run(app, host=host, port=port, log_level="info", log_config=None)
    except Exception:
        log.exception("error fatal en arranque del agente")
        raise


if __name__ == "__main__":
    main()

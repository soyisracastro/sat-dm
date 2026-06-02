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
"""

from __future__ import annotations

import argparse
import os
import sys


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


def main() -> None:
    port = _parse_port()
    host = "127.0.0.1"

    # Importar uvicorn y el app SOLO al ejecutar (no al importar el módulo).
    # PyInstaller agradece esto: el __main__ no arrastra el grafo hasta que
    # main() se invoca. Import absoluto porque PyInstaller corre __main__ sin
    # parent package context.
    import uvicorn

    from sat_descarga.api.server import app

    print(f"[sat-agent] escuchando en http://{host}:{port}", file=sys.stderr)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()

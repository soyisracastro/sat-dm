"""
Smoke test del entrypoint del agente (`python -m sat_descarga.api`).

Valida que el módulo arranca, escucha en el puerto solicitado y responde 200 a
/health. Es el mismo flujo que ejecuta PyInstaller cuando empaqueta `sat-agent.exe`
y que el CI valida en release.yml — si esto pasa, el binario empacado también
debería arrancar.

Requiere el extra `server` (FastAPI/uvicorn). Si no está instalado, el test se
salta automáticamente.

NO uses `host=0.0.0.0` ni un puerto conocido — el agente solo escucha en
127.0.0.1 y un puerto efímero para no chocar con instancias paralelas en CI.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("uvicorn")


def _puerto_libre() -> int:
    """Pide un puerto efímero al kernel."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _esperar_health(url: str, timeout_s: float = 30.0) -> int:
    """Pollea /health hasta que responda o expire timeout. Devuelve status code."""
    deadline = time.time() + timeout_s
    last_err: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as r:
                return r.status
        except (urllib.error.URLError, ConnectionError, TimeoutError) as e:
            last_err = e
            time.sleep(0.4)
    raise AssertionError(f"/health no respondió en {timeout_s}s (último error: {last_err!r})")


def test_entrypoint_arranca_y_responde_health(tmp_path):
    """
    Arranca `python -m sat_descarga.api --port N` en subprocess, espera /health,
    valida 200 y mata el proceso.
    """
    port = _puerto_libre()

    # Aislar el agente de cualquier estado del usuario (~/.sat-descarga). El
    # lifespan llama a `_autocargar_empresa_default()` que lee empresas.json y
    # en macOS sin firma puede colgarse leyendo el keychain. Vacío evita ese
    # camino. El skip del warm-up evita que el lifespan intente descargar
    # Chromium durante el test.
    env = {
        **os.environ,
        "HOME": str(tmp_path),
        "USERPROFILE": str(tmp_path),
        "SAT_AGENT_SKIP_BROWSER_WARMUP": "1",
    }

    proc = subprocess.Popen(
        [sys.executable, "-m", "sat_descarga.api", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
    )
    try:
        status = _esperar_health(f"http://127.0.0.1:{port}/health", timeout_s=30.0)
        assert status == 200
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

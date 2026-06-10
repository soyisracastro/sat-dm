"""Tests del middleware de token efímero del agente (server.py).

En producción, Electron genera un token por arranque y se lo pasa al agente
vía env SAT_AGENT_TOKEN; el middleware rechaza con 401 cualquier request que
no lo traiga (header X-Agent-Token, o ?token= para SSE). Sin la env, el
middleware no exige nada (CLI / uvicorn manual en dev).
"""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402

TOKEN = "token-de-prueba-abc123"


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")
    monkeypatch.setattr(config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta"))
    yield
    server._limpiar_session()


@pytest.fixture
def client_con_token(monkeypatch):
    monkeypatch.setattr(server, "_AGENT_TOKEN", TOKEN)
    return TestClient(server.app)


@pytest.fixture
def client_sin_token(monkeypatch):
    monkeypatch.setattr(server, "_AGENT_TOKEN", "")
    return TestClient(server.app)


class TestTokenMiddleware:

    def test_sin_token_rechaza_401(self, client_con_token):
        r = client_con_token.get("/health")
        assert r.status_code == 401

    def test_token_invalido_rechaza_401(self, client_con_token):
        r = client_con_token.get("/health", headers={"X-Agent-Token": "otro"})
        assert r.status_code == 401

    def test_header_correcto_pasa(self, client_con_token):
        r = client_con_token.get("/health", headers={"X-Agent-Token": TOKEN})
        assert r.status_code == 200

    def test_query_param_pasa(self, client_con_token):
        # EventSource no acepta headers; el token viaja como ?token=.
        r = client_con_token.get(f"/health?token={TOKEN}")
        assert r.status_code == 200

    def test_options_preflight_no_exige_token(self, client_con_token):
        # El preflight CORS no puede traer headers custom; no ejecuta endpoints.
        r = client_con_token.options(
            "/empresas",
            headers={
                "Origin": "app://-",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert r.status_code != 401

    def test_sin_env_no_exige_nada(self, client_sin_token):
        r = client_sin_token.get("/health")
        assert r.status_code == 200

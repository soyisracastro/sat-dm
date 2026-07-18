"""Tests de GET/PUT /config/organizador — config GLOBAL del organizador.

Usan FastAPI TestClient; settings.json se redirige a tmp (fixture local), así
que no tocan ~/.sat-descarga real.
"""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")
    monkeypatch.setattr(
        config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta")
    )


@pytest.fixture
def client():
    return TestClient(server.app)


def test_get_regresa_defaults_sin_guardar(client):
    cfg = client.get("/config/organizador").json()
    assert cfg["guardada"] is False
    assert cfg["estructura"] == "rfc_emisor/anio/mes"
    assert cfg["copiar"] is True


def test_put_parcial_y_roundtrip(client):
    r = client.put(
        "/config/organizador",
        json={"estructura": "anio/mes", "copiar": False},
    )
    assert r.status_code == 200
    cfg = r.json()
    assert cfg["guardada"] is True
    assert cfg["estructura"] == "anio/mes"
    assert cfg["copiar"] is False

    # Patch parcial: lo no enviado NO se pisa (exclude_unset).
    cfg2 = client.put("/config/organizador", json={"separador": "_"}).json()
    assert cfg2["estructura"] == "anio/mes"
    assert cfg2["copiar"] is False
    assert cfg2["separador"] == "_"

    # GET refleja lo guardado.
    assert client.get("/config/organizador").json() == cfg2


def test_put_valida_tipos(client):
    r = client.put("/config/organizador", json={"niveles_custom": "no-una-lista"})
    assert r.status_code == 422

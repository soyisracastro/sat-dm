"""Tests de los endpoints de catálogo de empresas del agente (server.py).

Usan FastAPI TestClient. El catálogo se redirige a tmp y el keychain es en memoria
(fixture autouse del conftest), así que no tocan ~/.sat-descarga ni el keychain real.
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
    yield
    server._limpiar_session()


@pytest.fixture
def client():
    return TestClient(server.app)


def test_lista_vacia(client):
    assert client.get("/empresas").json() == {"empresas": []}


def test_alta_ciec_y_activar(client):
    r = client.post("/empresas/ciec", json={
        "rfc": "CAUI890921DAA", "nombre": "Cliente CIEC", "ciec": "miCiec123",
    })
    assert r.status_code == 200 and r.json()["rfc"] == "CAUI890921DAA"

    empresas = client.get("/empresas").json()["empresas"]
    assert len(empresas) == 1
    assert empresas[0]["rfc"] == "CAUI890921DAA" and empresas[0]["metodos"] == ["ciec"]
    # La contraseña CIEC NO viaja en el listado.
    assert "ciec" not in empresas[0] and "password" not in empresas[0]

    act = client.post("/empresas/CAUI890921DAA/activar").json()
    assert act["metodos"] == ["ciec"] and act["efirma_lista"] is False


def test_alta_fiel_activar_y_baja(client, test_cer, test_key, test_password, test_rfc):
    with open(test_cer, "rb") as c, open(test_key, "rb") as k:
        r = client.post(
            "/empresas/fiel",
            files={"cer_file": ("f.cer", c), "key_file": ("f.key", k)},
            data={"password": test_password, "nombre": "Mi Empresa"},
        )
    assert r.status_code == 200 and r.json()["rfc"] == test_rfc

    empresas = client.get("/empresas").json()["empresas"]
    assert empresas[0]["metodos"] == ["fiel"]

    # Activar carga la e.firma en sesión.
    act = client.post(f"/empresas/{test_rfc}/activar").json()
    assert act["efirma_lista"] is True
    health = client.get("/health").json()
    assert health["efirma_lista"] is True and health["rfc_cargado"] == test_rfc

    # Baja: desaparece del catálogo.
    assert client.delete(f"/empresas/{test_rfc}").status_code == 200
    assert client.get("/empresas").json()["empresas"] == []


def test_activar_inexistente_404(client):
    assert client.post("/empresas/RFCNOEXISTE000/activar").status_code == 404


def test_default_cambia_predeterminada(client):
    client.post("/empresas/ciec", json={"rfc": "AAA010101AAA", "nombre": "A", "ciec": "x"})
    client.post("/empresas/ciec", json={"rfc": "BBB020202BBB", "nombre": "B", "ciec": "y"})
    # La primera registrada es la predeterminada.
    empresas = {e["rfc"]: e["default"] for e in client.get("/empresas").json()["empresas"]}
    assert empresas["AAA010101AAA"] is True and empresas["BBB020202BBB"] is False
    # Cambiar la predeterminada a la segunda.
    assert client.post("/empresas/BBB020202BBB/default").status_code == 200
    empresas = {e["rfc"]: e["default"] for e in client.get("/empresas").json()["empresas"]}
    assert empresas["BBB020202BBB"] is True and empresas["AAA010101AAA"] is False
    # Inexistente → 404.
    assert client.post("/empresas/NOEXISTE000/default").status_code == 404


def test_descargas_dir_get_y_set(client, tmp_path):
    # Default = ~/Documents/TodoConta (termina en TodoConta).
    assert client.get("/config/descargas-dir").json()["dir"].endswith("TodoConta")
    # Cambiar y releer.
    nueva = str(tmp_path / "MisDescargas")
    assert client.put("/config/descargas-dir", json={"dir": nueva}).json()["dir"] == nueva
    assert client.get("/config/descargas-dir").json()["dir"] == nueva


def test_solicitudes_historial(client):
    config_store.add_empresa_ciec("CAUI890921DAA", "X", "ciec")
    config_store.save_solicitud(
        rfc="CAUI890921DAA", id_solicitud="abc-1",
        fecha_inicio="2026-01-01", fecha_fin="2026-03-31", tipo="E",
    )
    sols = client.get("/empresas/CAUI890921DAA/solicitudes").json()["solicitudes"]
    assert len(sols) == 1 and sols[0]["id_solicitud"] == "abc-1"

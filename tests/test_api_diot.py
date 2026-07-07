"""Endpoints /diot/* del agente local (TestClient)."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402
from sat_descarga.diot import fila_vacia  # noqa: E402
from sat_descarga.procesador import parse_cfdi  # noqa: E402
from sat_descarga.procesador import db as db_mod  # noqa: E402

from .test_diot import MI_RFC, PROV_A, _xml  # noqa: E402

PERIODO = "2026-05"


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    # Siembra el singleton del procesador con una DB temporal.
    db_mod.resetear_singleton_para_tests()
    db = db_mod.abrir_db(tmp_path / "procesador.db")
    db.agregar([parse_cfdi(_xml("API-1"))], mi_rfc=MI_RFC)
    yield
    db_mod.resetear_singleton_para_tests()


@pytest.fixture
def client():
    return TestClient(server.app)


def test_estado_vacio(client):
    r = client.get("/diot/estado", params={"rfc": MI_RFC, "periodo": PERIODO})
    assert r.status_code == 200
    body = r.json()
    assert body["filas"] == [] and body["errores"] == []


def test_flujo_prellenar_editar_exportar(client):
    # Prellenar desde el buffer del procesador.
    r = client.post("/diot/prellenar", json={"rfc": MI_RFC, "periodo": PERIODO})
    assert r.status_code == 200
    body = r.json()
    assert body["resumen"]["proveedores"] == 1
    (fila,) = body["filas"]
    assert fila["rfc"] == PROV_A and fila["valor_16"] == 1000

    # Editar: el usuario ajusta un monto y agrega un renglón manual.
    fila["valor_16"] = 1200
    manual = fila_vacia()
    manual.update(rfc="CCC030303CC9", valor_16=500, acred_excl_16=80, origen="manual")
    r = client.put(
        "/diot/estado",
        json={"rfc": MI_RFC, "periodo": PERIODO, "filas": [fila, manual]},
    )
    assert r.status_code == 200
    assert len(r.json()["filas"]) == 2

    # El estado editado persiste.
    r = client.get("/diot/estado", params={"rfc": MI_RFC, "periodo": PERIODO})
    assert r.json()["filas"][0]["valor_16"] == 1200

    # Re-prellenar pisa la fila CFDI (vuelve a 1000) pero conserva la manual.
    r = client.post("/diot/prellenar", json={"rfc": MI_RFC, "periodo": PERIODO})
    filas = r.json()["filas"]
    assert {f["rfc"] for f in filas} == {PROV_A, "CCC030303CC9"}
    assert next(f for f in filas if f["rfc"] == PROV_A)["valor_16"] == 1000

    # Exportar el TXT.
    r = client.get("/diot/exportar", params={"rfc": MI_RFC, "periodo": PERIODO})
    assert r.status_code == 200
    assert r.headers["content-disposition"] == (
        f'attachment; filename="{MI_RFC}_diot_{PERIODO}.txt"'
    )
    assert r.content.startswith(b"\xef\xbb\xbf")
    assert r.content.count(b"\r\n") == 2


def test_exportar_sin_filas_400(client):
    r = client.get("/diot/exportar", params={"rfc": MI_RFC, "periodo": "2026-01"})
    assert r.status_code == 400


def test_exportar_con_errores_400(client):
    fila = fila_vacia()
    fila.update(rfc="", valor_16=100)  # nacional sin RFC → error duro
    client.put("/diot/estado", json={"rfc": MI_RFC, "periodo": PERIODO, "filas": [fila]})
    r = client.get("/diot/exportar", params={"rfc": MI_RFC, "periodo": PERIODO})
    assert r.status_code == 400
    assert r.json()["detail"]["errores"]


def test_rfc_y_periodo_invalidos_400(client):
    assert client.get("/diot/estado", params={"rfc": "MALO", "periodo": PERIODO}).status_code == 400
    assert client.get("/diot/estado", params={"rfc": MI_RFC, "periodo": "2026-13"}).status_code == 400


def test_catalogos(client):
    r = client.get("/diot/catalogos")
    assert r.status_code == 200
    body = r.json()
    assert body["tipo_tercero"]["04"] == "Proveedor Nacional"
    assert body["operaciones_por_tercero"]["15"] == ["87"]
    assert body["paises"]["ZZZ"] == "Otro"
    assert len(body["campos"]) == 54

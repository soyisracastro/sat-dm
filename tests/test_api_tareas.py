"""Endpoints /tareas* del agente local (TestClient) + store."""

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402
from sat_descarga.tareas import store  # noqa: E402


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")


@pytest.fixture
def client():
    return TestClient(server.app)


def test_estado_inicial_vacio(client):
    r = client.get("/tareas")
    assert r.status_code == 200
    body = r.json()
    assert body["tareas"] == [] and body["sugerencias_descartadas"] == []


def test_flujo_crear_editar_completar_eliminar(client):
    # Crear con lo mínimo: defaults manual/pendiente/media.
    r = client.post("/tareas", json={"titulo": "  Presentar DIOT de junio  "})
    assert r.status_code == 200
    tarea = r.json()
    assert tarea["titulo"] == "Presentar DIOT de junio"
    assert tarea["tipo"] == "manual" and tarea["estado"] == "pendiente"
    assert tarea["prioridad"] == "media" and tarea["fecha"] is None
    assert tarea["origen"] == "manual" and tarea["gcal_event_id"] is None

    # Crear otra completa, vinculada a empresa (rfc se normaliza a mayúsculas).
    r = client.post(
        "/tareas",
        json={
            "titulo": "Descargar CFDIs de junio",
            "rfc": "xaxx010101000",
            "tipo": "fiscal",
            "prioridad": "alta",
            "fecha": "2026-07-15",
        },
    )
    assert r.status_code == 200
    fiscal = r.json()
    assert fiscal["rfc"] == "XAXX010101000"

    # La más reciente queda al inicio.
    tareas = client.get("/tareas").json()["tareas"]
    assert [t["titulo"] for t in tareas][0] == "Descargar CFDIs de junio"

    # Patch parcial: solo cambia lo enviado.
    r = client.patch(f"/tareas/{tarea['id']}", json={"estado": "curso"})
    assert r.status_code == 200
    assert r.json()["estado"] == "curso"
    assert r.json()["titulo"] == "Presentar DIOT de junio"

    # Completar estampa completado_en; reabrir lo limpia.
    r = client.patch(f"/tareas/{tarea['id']}", json={"estado": "hecho"})
    assert r.json()["completado_en"] is not None
    r = client.patch(f"/tareas/{tarea['id']}", json={"estado": "pendiente"})
    assert r.json()["completado_en"] is None

    # Quitar la fecha límite explícitamente (null sí viaja en el patch).
    r = client.patch(f"/tareas/{fiscal['id']}", json={"fecha": None})
    assert r.json()["fecha"] is None

    # Eliminar.
    assert client.delete(f"/tareas/{tarea['id']}").status_code == 200
    assert client.delete(f"/tareas/{tarea['id']}").status_code == 404
    assert len(client.get("/tareas").json()["tareas"]) == 1


def test_validaciones(client):
    assert client.post("/tareas", json={"titulo": "   "}).status_code == 400
    assert (
        client.post(
            "/tareas", json={"titulo": "x", "fecha": "15/07/2026"}
        ).status_code
        == 400
    )
    # Literales inválidos los rechaza Pydantic (422).
    assert (
        client.post("/tareas", json={"titulo": "x", "tipo": "otro"}).status_code
        == 422
    )
    assert client.patch("/tareas/no-existe", json={"titulo": "x"}).status_code == 404


def test_sugerencias_aceptar_y_descartar(client):
    # Aceptar una sugerencia = crear tarea con sugerencia_id (origen sugerencia).
    r = client.post(
        "/tareas",
        json={
            "titulo": "Renovar e.firma de Norma",
            "sugerencia_id": "efirma-REAN741122K85-2026-07-11",
            "tipo": "fiscal",
        },
    )
    assert r.json()["origen"] == "sugerencia"

    # Descartar es idempotente y persiste.
    r = client.post("/tareas/sugerencias/descartar", json={"id": "diot-2026-06"})
    assert r.status_code == 200
    r = client.post("/tareas/sugerencias/descartar", json={"id": "diot-2026-06"})
    assert r.json()["sugerencias_descartadas"] == ["diot-2026-06"]
    assert client.get("/tareas").json()["sugerencias_descartadas"] == [
        "diot-2026-06"
    ]


def test_store_persiste_en_disco(tmp_path):
    tarea = store.crear("Conciliar mayo", fecha="2026-07-20")
    # Releyendo desde disco (otra "sesión" del store).
    datos = store.listar()
    assert datos["tareas"][0]["id"] == tarea["id"]
    ruta = config_store.CONFIG_DIR / "tareas.json"
    assert ruta.exists()
    assert "Conciliar mayo" in ruta.read_text(encoding="utf-8")

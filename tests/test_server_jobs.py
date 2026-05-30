"""Tests de los endpoints de jobs CIEC del agente (sat_descarga/api/server.py).

Prueban el plumbing HTTP (estado de job, entrega del captcha, 404s, guard de
'un job a la vez') SIN abrir Playwright: el scrape se monkeypatchea. El
suspend/resume del captcha en sí está cubierto por tests/test_jobs.py.
"""

import threading
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import jobs, server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402


@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch, tmp_path):
    """Registry limpio + catálogo en tmp (no toca ~/.sat-descarga ni el real)."""
    monkeypatch.setattr(jobs, "registry", jobs.JobRegistry())
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")


@pytest.fixture
def client():
    return TestClient(server.app)


def test_job_no_encontrado(client):
    assert client.get("/jobs/noexiste").status_code == 404
    assert client.post("/jobs/noexiste/captcha", json={"solution": "X"}).status_code == 404
    assert client.get("/events/noexiste").status_code == 404


def test_captcha_endpoint_entrega_solucion(client):
    job = jobs.registry.crear()
    r = client.post(f"/jobs/{job.id}/captcha", json={"solution": "ABC123"})
    assert r.status_code == 200 and r.json()["ok"] is True
    assert job._captcha_resp.get_nowait() == "ABC123"


def test_captcha_endpoint_cancelar(client):
    job = jobs.registry.crear()
    r = client.post(f"/jobs/{job.id}/captcha", json={"solution": None})
    assert r.status_code == 200
    assert job._captcha_resp.get_nowait() is None


def test_estado_job(client):
    job = jobs.registry.crear()
    job.estado = "captcha"
    data = client.get(f"/jobs/{job.id}").json()
    assert data["id"] == job.id and data["estado"] == "captcha"


def test_un_job_ciec_a_la_vez(client, monkeypatch):
    # El scrape se bloquea para mantener el job vivo y probar el guard 409.
    liberar = threading.Event()

    def stub(**kwargs):
        liberar.wait(timeout=5)
        return [Path("/tmp/a.xml")]

    monkeypatch.setattr("sat_descarga.portal.cfdi.descargar_cfdi_ciec", stub)
    payload = {
        "rfc": "CAUI890921DAA", "ciec": "x",
        "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
    }
    r1 = client.post("/ciec/cfdi", json=payload)
    assert r1.status_code == 200 and "job_id" in r1.json()

    r2 = client.post("/ciec/cfdi", json=payload)  # ya hay uno en curso
    assert r2.status_code == 409

    liberar.set()
    # El job debe terminar en 'done'.
    job_id = r1.json()["job_id"]
    fin = time.time() + 5
    while time.time() < fin:
        if client.get(f"/jobs/{job_id}").json()["estado"] == "done":
            break
        time.sleep(0.05)
    assert client.get(f"/jobs/{job_id}").json()["estado"] == "done"


def test_ciec_sin_password_usa_catalogo(client, monkeypatch):
    # Empresa registrada con CIEC → /ciec/cfdi sin `ciec` toma la del keychain.
    config_store.add_empresa_ciec("CAUI890921DAA", "Cliente", "miCiecGuardada")
    recibido = {}

    def stub(**kwargs):
        recibido.update(kwargs)
        return []

    monkeypatch.setattr("sat_descarga.portal.cfdi.descargar_cfdi_ciec", stub)
    r = client.post("/ciec/cfdi", json={
        "rfc": "CAUI890921DAA",
        "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
    })
    assert r.status_code == 200 and "job_id" in r.json()
    # El job corre en un thread; esperar a que use el stub.
    fin = time.time() + 3
    while time.time() < fin and "ciec" not in recibido:
        time.sleep(0.02)
    assert recibido.get("ciec") == "miCiecGuardada"


def test_ciec_sin_password_ni_catalogo_400(client):
    r = client.post("/ciec/cfdi", json={
        "rfc": "ZZZ991231ZZZ",
        "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
    })
    assert r.status_code == 400


def test_cfdi_fiel_sin_efirma_cargada_401(client):
    # Sin /auth/cargar-fiel previo, _get_fiel() rechaza con 401.
    server._session["fiel"] = None
    r = client.post("/cfdi/fiel", json={
        "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
    })
    assert r.status_code == 401


def test_cfdi_fiel_lanza_job_con_credenciales_de_sesion(client, monkeypatch):
    # Con la FIEL en sesión, /cfdi/fiel crea un job y pasa cer/key/password al scrape.
    server._session.update({
        "fiel": object(), "rfc": "CAUI890921DAA",
        "cer_path": "/tmp/x.cer", "key_path": "/tmp/x.key",
        "password": "pw", "es_temp": False,
    })
    recibido = {}

    def stub(**kwargs):
        recibido.update(kwargs)
        return []
    monkeypatch.setattr("sat_descarga.portal.cfdi.descargar_cfdi_fiel", stub)

    r = client.post("/cfdi/fiel", json={
        "fecha_inicio": "2026-01-01", "fecha_fin": "2026-01-31",
        "tipo_comprobante": "R", "max_registros": 3,
    })
    assert r.status_code == 200 and "job_id" in r.json()
    fin = time.time() + 3
    while time.time() < fin and "cer_path" not in recibido:
        time.sleep(0.02)
    assert recibido["cer_path"] == "/tmp/x.cer"
    assert recibido["key_path"] == "/tmp/x.key"
    assert recibido["password"] == "pw"
    assert recibido["tipo_comprobante"] == "R"
    assert recibido["max_registros"] == 3

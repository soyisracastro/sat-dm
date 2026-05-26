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


@pytest.fixture(autouse=True)
def fresh_registry(monkeypatch):
    """Cada test arranca con un registry limpio (evita fugas entre tests)."""
    monkeypatch.setattr(jobs, "registry", jobs.JobRegistry())


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

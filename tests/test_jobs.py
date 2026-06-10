"""Tests del bridge de jobs (sat_descarga/api/jobs.py).

Verifican la pieza crítica del desktop: el captcha CIEC suspend/resume (el worker
thread se bloquea hasta que llega la solución por "HTTP"), más cancelar, timeout, el
formato del stream SSE y el manejo de errores. Usa threads reales pero determinista.
"""

import json
import queue
import time

import pytest

from sat_descarga.api import jobs


def test_registry_poda_jobs_terminados():
    """Los jobs terminados se podan al crear nuevos (conserva MAX_TERMINADOS);
    sin esto el registry crece con cada descarga de la sesión."""
    registro = jobs.JobRegistry()
    for _ in range(registro.MAX_TERMINADOS + 5):
        job = registro.crear()
        job.estado = "done"
    activo = registro.crear()  # dispara la poda

    terminados = [j for j in registro._jobs.values() if j.estado == "done"]
    assert len(terminados) == registro.MAX_TERMINADOS
    assert registro.get(activo.id) is activo


def test_poda_no_toca_jobs_activos():
    registro = jobs.JobRegistry()
    activos = [registro.crear() for _ in range(registro.MAX_TERMINADOS + 10)]  # pending
    registro.crear()
    assert all(registro.get(j.id) is not None for j in activos)


def _leer(job, tipo, timeout=3):
    """Lee eventos del job hasta encontrar `tipo` (ignora los previos)."""
    fin = time.time() + timeout
    while time.time() < fin:
        try:
            ev = job._eventos.get(timeout=max(0.01, fin - time.time()))
        except queue.Empty:
            break
        if ev is jobs._FIN:
            raise AssertionError(f"el stream terminó sin el evento '{tipo}'")
        if ev.get("event") == tipo:
            return ev
    raise AssertionError(f"no llegó el evento '{tipo}'")


@pytest.fixture
def reg():
    return jobs.JobRegistry()


def test_captcha_suspend_resume(reg):
    job = reg.crear()
    assert job.estado == "pending"
    cb = reg.pedir_captcha_callback(job)

    def fn():
        sol = cb(b"\xff\xd8\xff\xe0imagen-captcha", 1, 3)
        from pathlib import Path
        return {"captcha": sol, "archivos": [Path("/tmp/a.xml")]}

    t = reg.ejecutar(job, fn)
    ev = _leer(job, "captcha_required")
    assert ev["imagen"].startswith("data:image/jpeg;base64,")
    assert ev["intento"] == 1 and ev["max"] == 3
    assert job.estado == "captcha"

    reg.responder_captcha(job, "ABC123")
    done = _leer(job, "done")
    t.join(timeout=3)
    assert job.estado == "done"
    assert done["resultado"]["captcha"] == "ABC123"
    assert done["resultado"]["archivos"] == ["/tmp/a.xml"]  # Path serializado a str


def test_captcha_cancelar(reg):
    job = reg.crear()
    cb = reg.pedir_captcha_callback(job)

    def fn():
        sol = cb(b"img", 1, 3)
        if sol is None:
            raise RuntimeError("Captcha cancelado por el usuario; operación abortada.")
        return sol

    t = reg.ejecutar(job, fn)
    _leer(job, "captcha_required")
    reg.responder_captcha(job, None)  # el usuario cierra el modal
    ev = _leer(job, "cancelled")
    t.join(timeout=3)
    assert job.estado == "cancelled"
    assert "cancel" in ev["mensaje"].lower()


def test_captcha_timeout(reg, monkeypatch):
    monkeypatch.setattr(jobs, "CAPTCHA_TIMEOUT_S", 0.2)
    job = reg.crear()
    cb = reg.pedir_captcha_callback(job)

    def fn():
        return {"sol": cb(b"img", 1, 3)}  # nadie responde → timeout → None

    t = reg.ejecutar(job, fn)
    _leer(job, "captcha_required")
    _leer(job, "captcha_timeout", timeout=2)
    done = _leer(job, "done")
    t.join(timeout=3)
    assert done["resultado"]["sol"] is None


def test_stream_sse_formato(reg):
    job = reg.crear()
    reg.ejecutar(job, lambda: {"ok": True, "total": 3})
    lineas = list(reg.stream(job))  # bloquea hasta _FIN
    assert lineas, "el stream no emitió nada"
    for ln in lineas:
        assert ln.startswith("data: ") and ln.endswith("\n\n")
        json.loads(ln[len("data: "):].strip())  # cada línea es JSON válido
    payloads = [json.loads(ln[6:].strip()) for ln in lineas]
    eventos = [p["event"] for p in payloads]
    assert eventos[0] == "estado" and payloads[0]["estado"] == "running"
    assert eventos[-1] == "done"
    assert payloads[-1]["resultado"] == {"ok": True, "total": 3}


def test_error_se_reporta(reg):
    job = reg.crear()

    def fn():
        raise ValueError("explotó el scraper")

    t = reg.ejecutar(job, fn)
    ev = _leer(job, "error")
    t.join(timeout=3)
    assert job.estado == "error"
    assert "explotó" in ev["mensaje"]
    assert job.error and "explotó" in job.error

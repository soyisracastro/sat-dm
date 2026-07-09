"""Tests de los endpoints de Certifica (renovación de e.firma + CSD) del agente.

Prueban el plumbing HTTP y la persistencia (pendientes, sustitución de la
e.firma, csds[], contraseña del CSD) SIN abrir Playwright: el envío/recuperación
del portal se monkeypatchea. El núcleo de generación (.ren/.sdg reales) está
cubierto por tests/test_certifica.py.
"""

import json
import shutil
import time
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import jobs, server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402
from sat_descarga.core import secretos  # noqa: E402
from sat_descarga.core.fiel import FIEL  # noqa: E402


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "registry", jobs.JobRegistry())
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")
    monkeypatch.setattr(config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta"))
    # El worker verifica el navegador del portal; en tests no hay Playwright.
    monkeypatch.setattr("sat_descarga.portal.setup.navegador_listo", lambda: True)
    yield
    server._limpiar_session()


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def vigente(monkeypatch):
    """El cert de pruebas puede estar vencido: fuerza vigente=True."""
    monkeypatch.setattr(FIEL, "vigente", property(lambda self: True))


def _alta_fiel(client, test_cer, test_key, test_password):
    with open(test_cer, "rb") as c, open(test_key, "rb") as k:
        r = client.post(
            "/empresas/fiel",
            files={"cer_file": ("f.cer", c), "key_file": ("f.key", k)},
            data={"password": test_password, "nombre": "Mi Empresa"},
        )
    assert r.status_code == 200
    return r.json()["rfc"]


def _esperar_job(client, job_id, timeout_s=8.0):
    limite = time.monotonic() + timeout_s
    while time.monotonic() < limite:
        data = client.get(f"/jobs/{job_id}").json()
        if data["estado"] in ("done", "error", "cancelled"):
            return data
        time.sleep(0.03)
    pytest.fail(f"El job {job_id} no terminó en {timeout_s}s: {data}")


def _fases_del_stream(client, job_id):
    """Drena el SSE del job (ya terminado) y devuelve la lista de eventos."""
    eventos = []
    with client.stream("GET", f"/events/{job_id}") as r:
        for linea in r.iter_lines():
            if linea.startswith("data: "):
                eventos.append(json.loads(linea[len("data: "):]))
    return eventos


# ---------------------------------------------------------------------------
# POST /renovar — validaciones síncronas
# ---------------------------------------------------------------------------

class TestRenovarValidaciones:

    def test_falta_confirmacion(self, client, test_cer, test_key, test_password):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        r = client.post("/renovar", json={"rfc": rfc, "password": test_password})
        assert r.status_code == 400 and "confirmación" in r.json()["detail"]

    def test_empresa_inexistente(self, client):
        r = client.post("/renovar", json={
            "rfc": "XAXX010101000", "password": "x", "confirmar": True,
        })
        assert r.status_code == 404

    def test_sin_efirma(self, client):
        client.post("/empresas/ciec", json={"rfc": "CAUI890921DAA", "ciec": "x"})
        r = client.post("/renovar", json={
            "rfc": "CAUI890921DAA", "password": "x", "confirmar": True,
        })
        assert r.status_code == 400 and "e.firma" in r.json()["detail"]

    def test_password_incorrecta(self, client, test_cer, test_key, test_password):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        r = client.post("/renovar", json={
            "rfc": rfc, "password": "incorrecta", "confirmar": True,
        })
        assert r.status_code == 400 and "Contraseña incorrecta" in r.json()["detail"]

    def test_efirma_vencida(self, client, test_cer, test_key, test_password, monkeypatch):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        monkeypatch.setattr(FIEL, "vigente", property(lambda self: False))
        r = client.post("/renovar", json={
            "rfc": rfc, "password": test_password, "confirmar": True,
        })
        assert r.status_code == 400 and "vencida" in r.json()["detail"]

    def test_409_si_ya_hay_pendiente(self, client, test_cer, test_key, test_password, vigente):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        config_store.set_renovacion_pendiente(rfc, {
            "numero_operacion": "1", "acuse_pdf": None, "key_path": "/tmp/k",
        })
        r = client.post("/renovar", json={
            "rfc": rfc, "password": test_password, "confirmar": True,
        })
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# POST /renovar — flujo completo (envío monkeypatcheado)
# ---------------------------------------------------------------------------

class TestRenovarFlujo:

    def _fakes(self, monkeypatch, tmp_path, test_cer, test_key, *, con_cer=True):
        """generar → copia test_key como .key nueva; enviar → emite fases y
        devuelve el .cer 'nuevo' (el mismo de pruebas: empareja con la .key)."""

        def fake_generar(fiel, correo=None, password=None, salida_dir=None):
            d = Path(salida_dir); d.mkdir(parents=True, exist_ok=True)
            key = d / "Claveprivada_FIEL_nueva.key"
            shutil.copy2(test_key, key)
            ren = d / "Renovacion_FIEL.ren"
            ren.write_bytes(b"REN")
            return {"key": key, "ren": ren}

        def fake_enviar(cer, key, password, ren, directorio_salida=None,
                        key_nueva_path=None, recuperar=True, intentos_cert=6,
                        espera_cert_s=30, on_progreso=None, **kw):
            on_progreso("login_ok", {})
            on_progreso("numero_operacion", {"numero": "112233"})
            acuse = Path(directorio_salida) / "Acuse_renovacion.pdf"
            acuse.write_bytes(b"%PDF")
            on_progreso("acuse", {"estado": "Aceptada", "acuse_pdf": str(acuse)})
            cer_res = None
            if con_cer:
                on_progreso("recuperando", {"intento": 1, "max": intentos_cert})
                cer_res = Path(test_cer)
            return {"numero_operacion": "112233", "acuse_pdf": acuse,
                    "estado": "Aceptada", "cer": cer_res}

        monkeypatch.setattr("sat_descarga.certifica.generar_renovacion_fiel", fake_generar)
        monkeypatch.setattr("sat_descarga.portal.renovacion.enviar_renovacion_fiel", fake_enviar)

    def test_happy_path_sustituye_efirma(self, client, monkeypatch, tmp_path,
                                         test_cer, test_key, test_password, test_rfc, vigente):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        self._fakes(monkeypatch, tmp_path, test_cer, test_key, con_cer=True)

        r = client.post("/renovar", json={
            "rfc": rfc, "password": test_password, "confirmar": True,
        })
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        data = _esperar_job(client, job_id)
        assert data["estado"] == "done", data
        res = data["resultado"]
        assert res["renovada"] is True and res["cer_pendiente"] is False
        assert res["numero_operacion"] == "112233"

        # Fases por SSE, en orden.
        fases = [e["fase"] for e in _fases_del_stream(client, job_id) if e["event"] == "fase"]
        assert fases[:3] == ["generando", "firmando", "enviando"]
        assert "numero_operacion" in fases and "guardando" in fases

        # Catálogo: sin pendiente, con respaldo de la e.firma anterior.
        assert config_store.get_renovacion_pendiente(rfc) is None
        respaldos = list((tmp_path / "efirma" / rfc).glob("anterior_*"))
        assert respaldos and (respaldos[0] / "fiel.cer").exists()

        # Historial: quedó registrada la renovación.
        descargas = client.get(f"/empresas/{rfc}/historial").json()["descargas"]
        assert any(d["tipo"] == "renovacion" for d in descargas)

    def test_cert_no_listo_deja_pendiente(self, client, monkeypatch, tmp_path,
                                          test_cer, test_key, test_password, vigente):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        self._fakes(monkeypatch, tmp_path, test_cer, test_key, con_cer=False)

        r = client.post("/renovar", json={
            "rfc": rfc, "password": test_password, "confirmar": True,
        })
        data = _esperar_job(client, r.json()["job_id"])
        res = data["resultado"]
        assert res["renovada"] is False and res["cer_pendiente"] is True

        pendiente = config_store.get_renovacion_pendiente(rfc)
        assert pendiente["numero_operacion"] == "112233"
        assert pendiente["acuse_pdf"]  # el acuse sí llegó
        assert Path(pendiente["key_path"]).exists()

        # La UI lo ve en el payload de /empresas.
        emp = client.get("/empresas").json()["empresas"][0]
        assert emp["renovacion_pendiente"]["numero_operacion"] == "112233"

    def test_recuperar_completa_la_sustitucion(self, client, monkeypatch, tmp_path,
                                               test_cer, test_key, test_password, vigente):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        self._fakes(monkeypatch, tmp_path, test_cer, test_key, con_cer=False)
        r = client.post("/renovar", json={
            "rfc": rfc, "password": test_password, "confirmar": True,
        })
        _esperar_job(client, r.json()["job_id"])
        pendiente = config_store.get_renovacion_pendiente(rfc)

        def fake_recuperar(cer, key, password, directorio_salida=None,
                           key_nueva_path=None, intentos=10, espera_s=30,
                           on_progreso=None, **kw):
            assert key_nueva_path == pendiente["key_path"]
            on_progreso("recuperando", {"intento": 1, "max": intentos})
            return {"cer": Path(test_cer)}

        monkeypatch.setattr(
            "sat_descarga.portal.renovacion.recuperar_renovacion_fiel", fake_recuperar,
        )
        r2 = client.post("/renovar/recuperar", json={"rfc": rfc})
        assert r2.status_code == 200
        data = _esperar_job(client, r2.json()["job_id"])
        assert data["resultado"]["renovada"] is True
        assert config_store.get_renovacion_pendiente(rfc) is None

    def test_recuperar_sin_pendiente_404(self, client, test_cer, test_key, test_password):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        assert client.post("/renovar/recuperar", json={"rfc": rfc}).status_code == 404


# ---------------------------------------------------------------------------
# POST /csd — flujo completo (envío monkeypatcheado)
# ---------------------------------------------------------------------------

class TestCsd:

    def _fakes(self, monkeypatch, test_key, *, con_cer=True):
        def fake_generar(fiel, sucursal, password, salida_dir=None):
            d = Path(salida_dir); d.mkdir(parents=True, exist_ok=True)
            key = d / "Claveprivada_CSD.key"
            shutil.copy2(test_key, key)
            sdg = d / "Solicitud_CSD.sdg"
            sdg.write_bytes(b"SDG")
            return {"key": key, "sdg": sdg}

        def fake_enviar(cer, key, password, sdg, directorio_salida=None,
                        key_nueva_path=None, recuperar=True, intentos_cert=3,
                        espera_cert_s=20, on_progreso=None, **kw):
            on_progreso("numero_operacion", {"numero": "554433"})
            acuse = Path(directorio_salida) / "Acuse_GeneracionSellos.pdf"
            acuse.write_bytes(b"%PDF")
            on_progreso("acuse", {"estado": "Aceptada", "acuse_pdf": str(acuse)})
            cer_res = None
            if con_cer:
                cer_res = Path(directorio_salida) / "00001000000512345678.cer"
                cer_res.write_bytes(b"CER")
            return {"numero_operacion": "554433", "acuse_pdf": acuse,
                    "estado": "Aceptada", "cer": cer_res}

        monkeypatch.setattr("sat_descarga.certifica.generar_solicitud_csd", fake_generar)
        monkeypatch.setattr("sat_descarga.portal.csd.enviar_solicitud_csd_fiel", fake_enviar)

    def test_password_csd_corta_422(self, client, test_cer, test_key, test_password):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        r = client.post("/csd", json={
            "rfc": rfc, "password": test_password, "password_csd": "corta", "uso": "Matriz",
        })
        assert r.status_code == 422

    def test_happy_path(self, client, monkeypatch, test_cer, test_key, test_password):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        self._fakes(monkeypatch, test_key, con_cer=True)

        r = client.post("/csd", json={
            "rfc": rfc, "password": test_password,
            "password_csd": "sello2026!", "uso": "Facturación general",
        })
        assert r.status_code == 200
        data = _esperar_job(client, r.json()["job_id"])
        assert data["estado"] == "done", data
        res = data["resultado"]
        assert res["cert_pendiente"] is False and res["numero_operacion"] == "554433"

        # csds[] del catálogo quedó emitido, visible para la UI.
        emp = client.get("/empresas").json()["empresas"][0]
        assert emp["csds"][0]["estado"] == "emitido"
        assert emp["csds"][0]["uso"] == "Facturación general"

        # Contraseña del CSD: keychain + copia .txt junto a la .key (decisión 2026-07-09).
        assert secretos.obtener(rfc, secretos.CSD) == "sello2026!"
        txts = list(Path(res["carpeta"]).glob("*_contraseña.txt"))
        assert txts and "sello2026!" in txts[0].read_text(encoding="utf-8")

    def test_cert_pendiente_y_recuperar(self, client, monkeypatch, test_cer, test_key, test_password):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        self._fakes(monkeypatch, test_key, con_cer=False)

        r = client.post("/csd", json={
            "rfc": rfc, "password": test_password,
            "password_csd": "sello2026!", "uso": "Sucursal Norte",
        })
        data = _esperar_job(client, r.json()["job_id"])
        assert data["resultado"]["cert_pendiente"] is True
        entry = config_store.get_csd_pendiente(rfc)
        assert entry["numero_operacion"] == "554433"

        def fake_recuperar(cer, key, password, directorio_salida=None,
                           key_nueva_path=None, intentos=10, espera_s=30,
                           on_progreso=None, **kw):
            assert key_nueva_path == entry["key_path"]
            nuevo = Path(directorio_salida) / "00001000000512345678.cer"
            nuevo.write_bytes(b"CER")
            return {"cer": nuevo}

        monkeypatch.setattr(
            "sat_descarga.portal.csd.recuperar_ultimo_csd_fiel", fake_recuperar,
        )
        r2 = client.post("/csd/recuperar", json={"rfc": rfc})
        data2 = _esperar_job(client, r2.json()["job_id"])
        assert data2["resultado"]["cert_pendiente"] is False
        assert config_store.get_csd_pendiente(rfc) is None
        emp = client.get("/empresas").json()["empresas"][0]
        assert emp["csds"][0]["estado"] == "emitido"

    def test_recuperar_sin_pendiente_404(self, client, test_cer, test_key, test_password):
        rfc = _alta_fiel(client, test_cer, test_key, test_password)
        assert client.post("/csd/recuperar", json={"rfc": rfc}).status_code == 404

"""Endpoints /descargas/* (versión web) + comportamiento hosted de /abrir y /health."""

import zipfile
from io import BytesIO

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")


@pytest.fixture
def client():
    return TestClient(server.app)


def _descarga_en_historial(tmp_path, nombre="cfdi_XAXX", con_pdf=False):
    """Crea una carpeta (o archivo) de descarga y la registra en el historial."""
    if con_pdf:
        objetivo = tmp_path / "constancia.pdf"
        objetivo.write_bytes(b"%PDF-1.4 fake")
    else:
        objetivo = tmp_path / nombre
        (objetivo / "sub").mkdir(parents=True)
        (objetivo / "a.xml").write_text("<cfdi/>", encoding="utf-8")
        (objetivo / "sub" / "b.xml").write_text("<cfdi/>", encoding="utf-8")
    config_store.registrar_descarga(
        "XAXX010101000",
        canal="ws",
        tipo="cfdi" if not con_pdf else "constancia",
        ruta=str(objetivo),
    )
    return objetivo


class TestDescargasArchivo:
    def test_sirve_archivo_del_historial(self, client, tmp_path):
        pdf = _descarga_en_historial(tmp_path, con_pdf=True)
        r = client.get("/descargas/archivo", params={"ruta": str(pdf)})
        assert r.status_code == 200
        assert r.content == b"%PDF-1.4 fake"
        assert "attachment" in r.headers["content-disposition"]
        assert "constancia.pdf" in r.headers["content-disposition"]

    def test_carpeta_pide_zip(self, client, tmp_path):
        carpeta = _descarga_en_historial(tmp_path)
        r = client.get("/descargas/archivo", params={"ruta": str(carpeta)})
        assert r.status_code == 400

    def test_ruta_fuera_del_historial_403(self, client, tmp_path):
        _descarga_en_historial(tmp_path)
        intrusa = tmp_path / "secreto.txt"
        intrusa.write_text("no", encoding="utf-8")
        r = client.get("/descargas/archivo", params={"ruta": str(intrusa)})
        assert r.status_code == 403

    def test_ruta_borrada_404(self, client, tmp_path):
        pdf = _descarga_en_historial(tmp_path, con_pdf=True)
        pdf.unlink()
        r = client.get("/descargas/archivo", params={"ruta": str(pdf)})
        assert r.status_code == 404


class TestDescargasZip:
    def test_zip_de_carpeta(self, client, tmp_path):
        carpeta = _descarga_en_historial(tmp_path)
        r = client.get("/descargas/zip", params={"ruta": str(carpeta)})
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"
        assert "cfdi_XAXX.zip" in r.headers["content-disposition"]
        with zipfile.ZipFile(BytesIO(r.content)) as zf:
            assert sorted(zf.namelist()) == ["a.xml", "sub/b.xml"]

    def test_zip_de_archivo_suelto(self, client, tmp_path):
        pdf = _descarga_en_historial(tmp_path, con_pdf=True)
        r = client.get("/descargas/zip", params={"ruta": str(pdf)})
        assert r.status_code == 200
        with zipfile.ZipFile(BytesIO(r.content)) as zf:
            assert zf.namelist() == ["constancia.pdf"]

    def test_whitelist_tambien_aplica(self, client, tmp_path):
        _descarga_en_historial(tmp_path)
        r = client.get("/descargas/zip", params={"ruta": str(tmp_path)})
        assert r.status_code == 403


class TestModoHosted:
    def test_health_reporta_modo(self, client, monkeypatch):
        assert client.get("/health").json()["modo"] == "desktop"
        monkeypatch.setenv("SAT_DM_MODO", "hosted")
        assert client.get("/health").json()["modo"] == "hosted"

    def test_abrir_deshabilitado_en_hosted(self, client, tmp_path, monkeypatch):
        pdf = _descarga_en_historial(tmp_path, con_pdf=True)
        monkeypatch.setenv("SAT_DM_MODO", "hosted")
        r = client.post("/abrir", json={"ruta": str(pdf), "modo": "archivo"})
        assert r.status_code == 501

    def test_adopt_session_404_en_desktop(self, client):
        r = client.post(
            "/auth/adopt-session",
            json={"access_token": "t", "user_id": "u1"},
        )
        assert r.status_code == 404

    def test_adopt_session_persiste_en_hosted(self, client, tmp_path, monkeypatch):
        monkeypatch.setenv("SAT_DM_MODO", "hosted")
        from sat_descarga.api import license_client as lc

        monkeypatch.setattr(lc, "LICENSE_CACHE_PATH", tmp_path / "license-cache.json")
        r = client.post(
            "/auth/adopt-session",
            json={
                "access_token": "tok",
                "refresh_token": "ref",
                "user_id": "u1",
                "email": "a@b.c",
            },
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True, "user": {"id": "u1", "email": "a@b.c"}}
        s = lc.load_session()
        assert s is not None and s.access_token == "tok" and s.refresh_token == "ref"

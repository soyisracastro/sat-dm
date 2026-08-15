"""Estado consultable y respaldo descargable del trámite de renovación.

El trámite tiene un punto de no retorno: una vez que el SAT recibe el `.ren`,
la llave privada NUEVA es irremplazable — el `.cer` se vuelve a bajar de
«Recuperación de certificados», la `.key` no. Estos endpoints existen para que
el usuario (a) sepa siempre en qué etapa quedó su trámite y (b) pueda sacar la
llave nueva de la máquina ANTES de que el SAT reciba nada.
"""

import io
import zipfile

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import jobs, server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402
from sat_descarga.core import paths  # noqa: E402


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "registry", jobs.JobRegistry())
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")
    monkeypatch.setattr(
        config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta")
    )
    monkeypatch.setattr("sat_descarga.portal.setup.navegador_listo", lambda: True)
    yield
    server._limpiar_session()


@pytest.fixture
def client():
    return TestClient(server.app)


@pytest.fixture
def rfc(client, test_cer, test_key, test_password):
    with open(test_cer, "rb") as c, open(test_key, "rb") as k:
        r = client.post(
            "/empresas/fiel",
            files={"cer_file": ("f.cer", c), "key_file": ("f.key", k)},
            data={"password": test_password, "nombre": "Mi Empresa"},
        )
    assert r.status_code == 200
    return r.json()["rfc"]


def _sembrar_archivos(rfc, **archivos):
    """Escribe archivos en la carpeta canónica del trámite de renovación."""
    carpeta = paths.dir_documento(
        paths.TIPO_RENOVACION, rfc, salida_base=config_store.descargas_dir_default(),
    )
    carpeta.mkdir(parents=True, exist_ok=True)
    for nombre, contenido in archivos.items():
        (carpeta / nombre).write_bytes(contenido)
    return carpeta


class TestEstado:
    def test_rfc_desconocido_da_404(self, client):
        assert client.get("/renovar/estado?rfc=XAXX010101000").status_code == 404

    def test_sin_tramite_responde_200_y_vacio(self, client, rfc):
        d = client.get(f"/renovar/estado?rfc={rfc}").json()
        assert d["pendiente"] is False
        assert d["etapa"] is None
        assert d["siguiente_paso"] is None
        assert d["respaldo_disponible"] is False

    def test_etapa_generada_el_reintento_es_seguro(self, client, rfc):
        # El SAT aún no recibe nada: regenerar no duplica el trámite.
        config_store.set_renovacion_pendiente(rfc, {
            "etapa": "generada", "numero_operacion": None,
            "ren_path": "/x/a.ren", "key_path": "/x/a.key",
        })
        d = client.get(f"/renovar/estado?rfc={rfc}").json()
        assert d["pendiente"] is True
        assert d["reintento_seguro"] is True
        assert d["siguiente_paso"] == "reintentar"

    def test_etapa_enviada_manda_a_recuperar(self, client, rfc):
        # El SAT YA tiene el trámite: regenerar lo duplicaría.
        config_store.set_renovacion_pendiente(rfc, {
            "etapa": "enviada", "numero_operacion": "230500502463",
            "ren_path": "/x/a.ren", "key_path": "/x/a.key",
        })
        d = client.get(f"/renovar/estado?rfc={rfc}").json()
        assert d["reintento_seguro"] is False
        assert d["siguiente_paso"] == "recuperar"
        assert d["numero_operacion"] == "230500502463"

    def test_reporta_los_archivos_en_disco(self, client, rfc):
        _sembrar_archivos(rfc, **{"nueva.key": b"k", "sol.ren": b"r"})
        d = client.get(f"/renovar/estado?rfc={rfc}").json()
        assert d["respaldo_disponible"] is True
        assert sorted(d["archivos"]) == ["nueva.key", "sol.ren"]


class TestRespaldo:
    def test_sin_archivos_da_404(self, client, rfc):
        assert client.get(f"/renovar/respaldo?rfc={rfc}").status_code == 404

    def test_zip_trae_los_archivos_y_el_leeme(self, client, rfc):
        _sembrar_archivos(rfc, **{
            "nueva.key": b"llave-privada-nueva",
            "sol.ren": b"solicitud",
            "acuse.pdf": b"%PDF-",
        })
        r = client.get(f"/renovar/respaldo?rfc={rfc}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/zip"

        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            nombres = set(zf.namelist())
            assert {"nueva.key", "sol.ren", "acuse.pdf"} <= nombres
            assert zf.read("nueva.key") == b"llave-privada-nueva"
            leeme = zf.read("LÉEME.txt").decode("utf-8")

        # El LÉEME es la parte que evita la pérdida irreversible: tiene que
        # decir CUÁL archivo no se puede recuperar y qué pasa si se pierde.
        assert ".key" in leeme
        assert "PRESENCIAL" in leeme
        assert rfc in leeme

    def test_disponible_desde_la_etapa_generada(self, client, rfc):
        # Antes de que el SAT reciba nada. Es el momento en que sirve.
        _sembrar_archivos(rfc, **{"nueva.key": b"k", "sol.ren": b"r"})
        config_store.set_renovacion_pendiente(rfc, {
            "etapa": "generada", "numero_operacion": None,
            "ren_path": "/x/a.ren", "key_path": "/x/a.key",
        })
        assert client.get(f"/renovar/respaldo?rfc={rfc}").status_code == 200

    def test_no_sirve_archivos_ajenos_al_tramite(self, client, rfc):
        # La carpeta se deriva del RFC, y solo salen extensiones del trámite.
        carpeta = _sembrar_archivos(rfc, **{"nueva.key": b"k"})
        (carpeta / "notas.txt").write_bytes(b"algo que no es del tramite")
        r = client.get(f"/renovar/respaldo?rfc={rfc}")
        with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
            assert "notas.txt" not in zf.namelist()

    def test_rfc_desconocido_da_404(self, client):
        assert client.get("/renovar/respaldo?rfc=XAXX010101000").status_code == 404

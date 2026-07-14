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
    # Evita crear el ~/Documents/TodoConta real al asegurar la carpeta.
    monkeypatch.setattr(config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta"))
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


# ---------------------------------------------------------------------------
# Solicitudes: vencimiento local + actividad global (watcher multi-empresa)
# ---------------------------------------------------------------------------

def _envejecer_solicitud(rfc, id_solicitud, horas=100):
    """Retro-fecha el timestamp de una solicitud en el JSON (simula colgada)."""
    import json
    from datetime import datetime, timedelta

    path = config_store._solicitudes_path(rfc)
    data = json.loads(path.read_text(encoding="utf-8"))
    for s in data["solicitudes"]:
        if s["id_solicitud"] == id_solicitud:
            s["timestamp"] = (
                datetime.now() - timedelta(hours=horas)
            ).isoformat(timespec="seconds")
    path.write_text(json.dumps(data), encoding="utf-8")


def test_solicitudes_listado_marca_vencidas(client):
    """GET /empresas/{rfc}/solicitudes aplica el vencimiento local (>72 h)."""
    config_store.add_empresa_ciec("CAUI890921DAA", "X", "ciec")
    config_store.save_solicitud(
        rfc="CAUI890921DAA", id_solicitud="colgada-1",
        fecha_inicio="2026-01-01", fecha_fin="2026-06-30", tipo="CFDI · recibidos",
    )
    config_store.update_solicitud("CAUI890921DAA", "colgada-1", "2")
    _envejecer_solicitud("CAUI890921DAA", "colgada-1")

    sols = client.get("/empresas/CAUI890921DAA/solicitudes").json()["solicitudes"]
    assert sols[0]["estado"] == "vencida"
    assert "72 horas" in sols[0]["mensaje"]


def test_solicitudes_actividad_global(client):
    """/solicitudes/actividad junta las solicitudes de todas las empresas no
    archivadas, con rfc + nombre, y aplica el vencimiento local."""
    client.post("/empresas/ciec", json={"rfc": "AAA010101AAA", "nombre": "Uno", "ciec": "x"})
    client.post("/empresas/ciec", json={"rfc": "BBB020202BBB", "nombre": "Dos", "ciec": "y"})
    client.post("/empresas/ciec", json={"rfc": "CCC030303CCC", "nombre": "Tres", "ciec": "z"})

    config_store.save_solicitud(
        rfc="AAA010101AAA", id_solicitud="id-a",
        fecha_inicio="2026-01-01", fecha_fin="2026-01-31", tipo="CFDI · recibidos",
    )
    config_store.save_solicitud(
        rfc="BBB020202BBB", id_solicitud="id-b",
        fecha_inicio="2026-01-01", fecha_fin="2026-01-31", tipo="CFDI · emitidos",
    )
    config_store.update_solicitud("BBB020202BBB", "id-b", "2")
    _envejecer_solicitud("BBB020202BBB", "id-b")
    config_store.save_solicitud(
        rfc="CCC030303CCC", id_solicitud="id-c",
        fecha_inicio="2026-01-01", fecha_fin="2026-01-31", tipo="CFDI · recibidos",
    )
    # Empresa archivada: sus solicitudes NO deben aparecer.
    client.post("/empresas/CCC030303CCC/archive")

    sols = client.get("/solicitudes/actividad").json()["solicitudes"]
    por_id = {s["id_solicitud"]: s for s in sols}

    assert set(por_id) == {"id-a", "id-b"}
    assert por_id["id-a"]["rfc"] == "AAA010101AAA"
    assert por_id["id-a"]["nombre"] == "Uno"
    assert por_id["id-a"]["estado"] == "solicitada"
    # La colgada >72 h sale ya como vencida (sin esperar al poller).
    assert por_id["id-b"]["estado"] == "vencida"


# ---------------------------------------------------------------------------
# POST /empresas/{rfc}/parsear-csf — rellenar desde la constancia ya descargada
# ---------------------------------------------------------------------------

def _alta_con_csf(client, tmp_path, rfc="SAJ0205248A9"):
    """Empresa con una CSF 'descargada' (archivo dummy en tmp)."""
    client.post("/empresas/ciec", json={"rfc": rfc, "nombre": "", "ciec": "x"})
    pdf = tmp_path / f"constancia_{rfc}.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    config_store.set_csf_descargada(rfc, str(pdf))
    return pdf


def test_parsear_csf_empresa_inexistente_404(client):
    r = client.post("/empresas/XXXX010101XXX/parsear-csf")
    assert r.status_code == 404


def test_parsear_csf_sin_constancia_409(client):
    client.post("/empresas/ciec", json={"rfc": "SAJ0205248A9", "nombre": "", "ciec": "x"})
    r = client.post("/empresas/SAJ0205248A9/parsear-csf")
    assert r.status_code == 409
    assert "no tiene una constancia" in r.json()["detail"]


def test_parsear_csf_archivo_borrado_409(client, tmp_path):
    pdf = _alta_con_csf(client, tmp_path)
    pdf.unlink()
    r = client.post("/empresas/SAJ0205248A9/parsear-csf")
    assert r.status_code == 409
    assert "ya no está en el equipo" in r.json()["detail"]


def test_parsear_csf_pdf_ilegible_500(client, tmp_path):
    # El dummy no es un PDF válido → error de lectura controlado en español.
    _alta_con_csf(client, tmp_path)
    r = client.post("/empresas/SAJ0205248A9/parsear-csf")
    assert r.status_code == 500
    assert "No se pudo leer la constancia" in r.json()["detail"]


def test_parsear_csf_aplica_datos(client, tmp_path, monkeypatch):
    from sat_descarga.utils import csf_parser
    from sat_descarga.utils.csf_parser import ActividadCsf, DatosCsf, RegimenCsf

    _alta_con_csf(client, tmp_path)
    monkeypatch.setattr(csf_parser, "parsear_csf", lambda _ruta: DatosCsf(
        rfc="SAJ0205248A9",
        nombre="SUPERSERVICIO AJUCHITLAN",
        tipo_persona="PM",
        regimenes=[RegimenCsf(clave="601", descripcion="Régimen General de Ley Personas Morales")],
        actividades=[
            ActividadCsf(descripcion="Gasolina y diésel", porcentaje=99, principal=True),
            ActividadCsf(descripcion="Lubricantes", porcentaje=1, principal=False),
        ],
    ))

    r = client.post("/empresas/SAJ0205248A9/parsear-csf")
    assert r.status_code == 200
    body = r.json()
    assert body["nombre"] == "SUPERSERVICIO AJUCHITLAN"
    assert body["regimenes_fiscales"][0]["clave"] == "601"
    assert body["actividades_economicas"][0] == {
        "descripcion": "Gasolina y diésel", "principal": True, "porcentaje": 99,
    }

    # Y quedó persistido en el catálogo (el alta dejó el RFC como placeholder).
    emp = client.get("/empresas").json()["empresas"][0]
    assert emp["nombre"] == "SUPERSERVICIO AJUCHITLAN"
    assert emp["regimenes_fiscales"][0]["clave"] == "601"
    assert emp["actividades_economicas"][0]["porcentaje"] == 99


def test_parsear_csf_de_otro_rfc_409(client, tmp_path, monkeypatch):
    from sat_descarga.utils import csf_parser
    from sat_descarga.utils.csf_parser import DatosCsf

    _alta_con_csf(client, tmp_path)
    monkeypatch.setattr(csf_parser, "parsear_csf", lambda _ruta: DatosCsf(
        rfc="OTRO010101AAA", nombre="OTRA EMPRESA", tipo_persona="PM",
    ))
    r = client.post("/empresas/SAJ0205248A9/parsear-csf")
    assert r.status_code == 409
    assert "otro RFC" in r.json()["detail"]


# ---------------------------------------------------------------------------
# POST /empresas/{rfc}/parsear-opinion — sentido + motivos de la 32-D
# ---------------------------------------------------------------------------

def _alta_con_opinion(client, tmp_path, rfc="CAUI890921DAA"):
    client.post("/empresas/ciec", json={"rfc": rfc, "nombre": "", "ciec": "x"})
    pdf = tmp_path / f"opinion32d_{rfc}.pdf"
    pdf.write_bytes(b"%PDF-1.4 dummy")
    config_store.set_opinion_descargada(rfc, str(pdf))
    return pdf


def test_parsear_opinion_empresa_inexistente_404(client):
    assert client.post("/empresas/XXXX010101XXX/parsear-opinion").status_code == 404


def test_parsear_opinion_sin_opinion_409(client):
    client.post("/empresas/ciec", json={"rfc": "CAUI890921DAA", "nombre": "", "ciec": "x"})
    r = client.post("/empresas/CAUI890921DAA/parsear-opinion")
    assert r.status_code == 409
    assert "no tiene una opinión" in r.json()["detail"]


def test_parsear_opinion_archivo_borrado_409(client, tmp_path):
    pdf = _alta_con_opinion(client, tmp_path)
    pdf.unlink()
    r = client.post("/empresas/CAUI890921DAA/parsear-opinion")
    assert r.status_code == 409
    assert "ya no está en el equipo" in r.json()["detail"]


def test_parsear_opinion_pdf_ilegible_500(client, tmp_path):
    _alta_con_opinion(client, tmp_path)
    r = client.post("/empresas/CAUI890921DAA/parsear-opinion")
    assert r.status_code == 500
    assert "No se pudo leer la opinión" in r.json()["detail"]


def test_parsear_opinion_negativa_aplica(client, tmp_path, monkeypatch):
    from sat_descarga.utils import opinion_parser
    from sat_descarga.utils.opinion_parser import DatosOpinion, MotivoOpinion

    _alta_con_opinion(client, tmp_path)
    monkeypatch.setattr(opinion_parser, "parsear_opinion", lambda _r: DatosOpinion(
        rfc="CAUI890921DAA", sentido="negativa", folio="26ND5008217",
        motivos=[MotivoOpinion(titulo="Créditos fiscales",
                               descripcion="Se ubican ...:", detalles=["234910013510"])],
    ))
    r = client.post("/empresas/CAUI890921DAA/parsear-opinion")
    assert r.status_code == 200
    body = r.json()
    assert body["opinion_status"] == "negativa"
    assert body["opinion_motivos"][0]["titulo"] == "Créditos fiscales"

    emp = client.get("/empresas").json()["empresas"][0]
    assert emp["opinion_status"] == "negativa"
    assert emp["opinion_motivos"][0]["detalles"] == ["234910013510"]


def test_parsear_opinion_de_otro_rfc_409(client, tmp_path, monkeypatch):
    from sat_descarga.utils import opinion_parser
    from sat_descarga.utils.opinion_parser import DatosOpinion

    _alta_con_opinion(client, tmp_path)
    monkeypatch.setattr(opinion_parser, "parsear_opinion", lambda _r: DatosOpinion(
        rfc="OTRO010101AAA", sentido="positiva", folio="x", motivos=[]))
    r = client.post("/empresas/CAUI890921DAA/parsear-opinion")
    assert r.status_code == 409
    assert "otro RFC" in r.json()["detail"]

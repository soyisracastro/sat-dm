"""Endpoints /ce/* y la presentación DIOT del agente local (TestClient).

Sin browser (convención del repo): se prueban las vallas de entrada — la
confirmación obligatoria, la limitante de estímulos como contrato, la revisión
previa de ZIPs, el 409 de job activo — y la lectura de la cola de pendientes.
"""

import zipfile

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import jobs, server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402

RFC = "SSA980330HU1"

XML_BALANZA = (
    '<?xml version="1.0"?>\n'
    '<BCE:Balanza Version="1.3" RFC="{rfc}" Mes="{mes}" Anio="{anio}" '
    'TipoEnvio="N" xmlns:BCE="http://www.sat.gob.mx/esquemas/ContabilidadE/'
    '1_3/BalanzaComprobacion"><BCE:Ctas NumCta="100-01" SaldoIni="1.0" '
    'Debe="0.0" Haber="0.0" SaldoFin="1.0"/></BCE:Balanza>'
)


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "get_config_dir",
                        lambda: tmp_path / ".sat-descarga")
    yield


@pytest.fixture
def client():
    return TestClient(server.app)


def _zip_valido(tmp_path, rfc=RFC, anio="2026", mes="01"):
    path = tmp_path / f"{rfc}{anio}{mes}BN.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(path.stem + ".xml",
                    XML_BALANZA.format(rfc=rfc, anio=anio, mes=mes))
    return path


# --- /ce/enviar: vallas ------------------------------------------------------

def test_enviar_sin_confirmar_es_400(client, tmp_path):
    r = client.post("/ce/enviar", json={
        "rfc": RFC, "archivos": [str(_zip_valido(tmp_path))]})
    assert r.status_code == 400
    assert "confirmar" in r.json()["detail"]


def test_enviar_archivo_inexistente_es_400(client):
    r = client.post("/ce/enviar", json={
        "rfc": RFC, "archivos": ["/no/existe.zip"], "solo_validar": True})
    assert r.status_code == 400
    assert "No existe" in r.json()["detail"]


def test_enviar_zip_que_no_pasa_revision_es_400(client, tmp_path):
    # nombre dice 2026-01 pero el XML trae otro RFC: no debe llegar al portal
    path = tmp_path / f"{RFC}202601BN.zip"
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(path.stem + ".xml", XML_BALANZA.format(
            rfc="SAJ0205248A9", anio="2026", mes="01"))
    r = client.post("/ce/enviar", json={
        "rfc": RFC, "archivos": [str(path)], "solo_validar": True})
    assert r.status_code == 400
    assert "revisión previa" in r.json()["detail"]["mensaje"]


def test_enviar_sin_efirma_en_catalogo_falla_limpio(client, tmp_path):
    # empresa no registrada → 404 (contrato de _empresa_con_fiel en certifica)
    r = client.post("/ce/enviar", json={
        "rfc": "XAXX010101000", "archivos": [str(_zip_valido(
            tmp_path, rfc="XAXX010101000"))], "solo_validar": True})
    assert r.status_code == 404


def test_enviar_con_job_activo_es_409(client, tmp_path, monkeypatch):
    monkeypatch.setattr(jobs.registry, "hay_activo", lambda: True)
    monkeypatch.setattr(
        "sat_descarga.api.routers.ce._credenciales_keychain",
        lambda rfc: {"cer_path": "x", "key_path": "y", "password": "z"})
    r = client.post("/ce/enviar", json={
        "rfc": RFC, "archivos": [str(_zip_valido(tmp_path))],
        "solo_validar": True})
    assert r.status_code == 409


# --- /ce/acuses --------------------------------------------------------------

def test_acuses_rango_invalido_es_400(client):
    r = client.post("/ce/acuses", json={
        "rfc": RFC, "anio": 2026, "mes_ini": 5, "mes_fin": 2})
    assert r.status_code == 400


# --- /ce/pendientes y /ce/reanudar ------------------------------------------

def test_pendientes_refleja_el_store(client):
    assert client.get("/ce/pendientes").json() == {"pendientes": []}
    config_store.save_envio_pendiente(RFC, "ce", ["/a/x.zip"], error="timeout")
    body = client.get("/ce/pendientes", params={"rfc": RFC}).json()
    assert len(body["pendientes"]) == 1
    assert body["pendientes"][0]["rfc"] == RFC


def test_reanudar_sin_pendientes_es_404(client):
    r = client.post("/ce/reanudar", json={"rfc": RFC})
    assert r.status_code == 404


# --- /diot/presentar: vallas -------------------------------------------------

def test_presentar_sin_estimulos_es_contrato(client, tmp_path):
    """La limitante de estímulos NO es una nota: sin sin_estimulos=true → 400,
    para que la UI esté obligada a preguntárselo al usuario."""
    txt = tmp_path / "diot.txt"
    txt.write_text("x")
    r = client.post("/diot/presentar", json={
        "rfc": RFC, "ejercicio": 2026, "periodo": 7,
        "txt_path": str(txt), "solo_validar": True})
    assert r.status_code == 400
    assert "estímulos" in r.json()["detail"]


def test_presentar_sin_confirmar_es_400(client, tmp_path):
    txt = tmp_path / "diot.txt"
    txt.write_text("x")
    r = client.post("/diot/presentar", json={
        "rfc": RFC, "ejercicio": 2026, "periodo": 7,
        "txt_path": str(txt), "sin_estimulos": True})
    assert r.status_code == 400
    assert "confirmar" in r.json()["detail"]


def test_presentar_periodo_invalido_es_400(client, tmp_path):
    txt = tmp_path / "diot.txt"
    txt.write_text("x")
    r = client.post("/diot/presentar", json={
        "rfc": RFC, "ejercicio": 2026, "periodo": 13,
        "txt_path": str(txt), "sin_estimulos": True, "solo_validar": True})
    assert r.status_code == 400


def test_presentar_sin_txt_es_400(client):
    r = client.post("/diot/presentar", json={
        "rfc": RFC, "ejercicio": 2026, "periodo": 7,
        "sin_estimulos": True, "solo_validar": True})
    assert r.status_code == 400
    assert "txt_path" in r.json()["detail"]

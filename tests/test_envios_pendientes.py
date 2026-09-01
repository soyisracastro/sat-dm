"""Tests del store de envíos pendientes (cola de reintento diferido).

Sin browser: solo el ciclo de vida del JSON en ~/.sat-descarga/envios/
(redirigido a tmp_path vía monkeypatch de get_config_dir).
"""

import json

import pytest

from sat_descarga.cli import config_store
from sat_descarga.cli.config_store import (
    get_envios_pendientes,
    save_envio_pendiente,
    update_envio,
)

RFC = "SSA980330HU1"


@pytest.fixture(autouse=True)
def config_dir_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "get_config_dir", lambda: tmp_path)
    yield tmp_path


def test_roundtrip_completo():
    eid = save_envio_pendiente(RFC, "ce", ["/a/x.zip", "/a/y.zip"],
                               params={"sellar": True}, error="timeout")
    [e] = get_envios_pendientes(RFC)
    assert e["id"] == eid
    assert e["estado"] == "pendiente"
    assert e["intentos"] == 0
    assert e["ultimo_intento"] is None
    assert e["ultimo_error"] == "timeout"

    # pasar a curso estampa el intento
    assert update_envio(RFC, eid, estado="curso")
    data = config_store._load_envios(RFC)
    e = data["envios"][0]
    assert e["estado"] == "curso"
    assert e["intentos"] == 1
    assert e["ultimo_intento"] is not None

    # completar con resultado
    update_envio(RFC, eid, estado="completado", resultado={"folios": {"x": "1"}})
    assert get_envios_pendientes(RFC) == []          # ya no está pendiente
    e = config_store._load_envios(RFC)["envios"][0]
    assert e["resultado"] == {"folios": {"x": "1"}}


def test_dedup_fusiona_archivos():
    id1 = save_envio_pendiente(RFC, "ce", ["/a/x.zip"], error="e1")
    id2 = save_envio_pendiente(RFC, "ce", ["/a/y.zip", "/a/x.zip"], error="e2")
    assert id1 == id2                                # mismo registro
    [e] = get_envios_pendientes(RFC)
    assert e["archivos"] == ["/a/x.zip", "/a/y.zip"]  # sin duplicar x
    assert e["ultimo_error"] == "e2"


def test_tramites_distintos_no_se_fusionan():
    id_ce = save_envio_pendiente(RFC, "ce", ["/a/x.zip"])
    id_diot = save_envio_pendiente(RFC, "diot", ["/a/d.txt"])
    assert id_ce != id_diot
    assert len(get_envios_pendientes(RFC)) == 2


def test_get_global_recorre_todas_las_empresas():
    save_envio_pendiente(RFC, "ce", ["/a/x.zip"])
    save_envio_pendiente("SAJ0205248A9", "ce", ["/b/z.zip"])
    todos = get_envios_pendientes()
    assert {e["rfc"] for e in todos} == {RFC, "SAJ0205248A9"}
    assert len(get_envios_pendientes("SAJ0205248A9")) == 1


def test_estado_invalido_truena():
    eid = save_envio_pendiente(RFC, "ce", ["/a/x.zip"])
    with pytest.raises(ValueError):
        update_envio(RFC, eid, estado="volando")


def test_update_de_id_inexistente_devuelve_false():
    assert update_envio(RFC, "noexiste", estado="curso") is False


def test_json_corrupto_se_recupera(config_dir_temporal):
    # un write race viejo / disco lleno deja basura: el store no debe tronar
    path = config_dir_temporal / "envios" / f"{RFC}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{esto no es json", encoding="utf-8")
    assert get_envios_pendientes(RFC) == []
    eid = save_envio_pendiente(RFC, "ce", ["/a/x.zip"])
    assert get_envios_pendientes(RFC)[0]["id"] == eid
    # y el archivo quedó reescrito como JSON válido
    json.loads(path.read_text(encoding="utf-8"))

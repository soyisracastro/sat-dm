"""Tests del poller en background de solicitudes WS (api/poller.py).

Cubre una pasada (`_una_pasada`/`_procesar_empresa`) con el SAT simulado:
verificación multi-empresa, persistencia de estados de falla, vencimiento
local, auto-descarga al quedar lista y dedup contra el endpoint /descargar.
"""

import json
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")

from sat_descarga.api import poller  # noqa: E402
from sat_descarga.api import state  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402
from sat_descarga.webservice.verificacion import EstadoSolicitud  # noqa: E402


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")
    monkeypatch.setattr(
        config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta")
    )
    # Cache de FIELs limpia entre tests.
    monkeypatch.setattr(poller, "_fiel_cache", {})


class FielFake:
    def __init__(self, rfc):
        self.rfc = rfc


def _estado(cod, package_ids=None, numero=0, mensaje="", estatus="5000"):
    return EstadoSolicitud(
        cod_estado=cod, cod_estatus=estatus, mensaje=mensaje,
        numero_cfdis=numero, package_ids=package_ids or [],
        terminada=(cod == "3"),
    )


def _empresa_con_pendiente(rfc, id_sol, estado="2", horas=None):
    config_store.add_empresa_ciec(rfc, f"Empresa {rfc}", "ciec")
    config_store.save_solicitud(
        rfc=rfc, id_solicitud=id_sol,
        fecha_inicio="2026-01-01", fecha_fin="2026-06-30",
        tipo="CFDI · recibidos", tipo_comprobante="R",
    )
    if estado != "solicitada":
        config_store.update_solicitud(rfc, id_sol, estado)
    if horas is not None:
        path = config_store._solicitudes_path(rfc)
        data = json.loads(path.read_text(encoding="utf-8"))
        for s in data["solicitudes"]:
            if s["id_solicitud"] == id_sol:
                s["timestamp"] = (
                    datetime.now() - timedelta(hours=horas)
                ).isoformat(timespec="seconds")
        path.write_text(json.dumps(data), encoding="utf-8")
    return {"rfc": rfc, "metodos": ["fiel"], "archived_at": None}


def _con_fiel_simulada(monkeypatch, verificaciones, descargas):
    """Parchea la red del SAT: la verificación devuelve lo indicado por id y
    `descargar_todos` solo registra la llamada."""
    monkeypatch.setattr(poller, "_fiel_de", lambda rfc: FielFake(rfc))
    monkeypatch.setattr(poller, "obtener_token", lambda fiel: "token")
    monkeypatch.setattr(
        poller, "consultar_solicitud",
        lambda token, rfc, id_sol, fiel: verificaciones[id_sol],
    )
    monkeypatch.setattr(
        poller, "descargar_todos",
        lambda **kw: descargas.append(kw) or [],
    )


def test_pendiente_que_queda_lista_se_descarga_sola(monkeypatch):
    emp = _empresa_con_pendiente("AAA010101AAA", "id-1", estado="2")
    descargas = []
    _con_fiel_simulada(
        monkeypatch,
        {"id-1": _estado("3", package_ids=["PKG_01"], numero=42)},
        descargas,
    )

    poller._procesar_empresa("AAA010101AAA", emp)

    sol = config_store.get_solicitud("AAA010101AAA", "id-1")
    assert sol["estado"] == "descargada"
    assert sol["package_ids"] == ["PKG_01"]
    assert len(descargas) == 1 and descargas[0]["package_ids"] == ["PKG_01"]
    # Quedó en el historial de descargas completadas.
    historial = config_store.list_descargas("AAA010101AAA")
    assert len(historial) == 1 and historial[0]["canal"] == "ws"


def test_rechazada_se_persiste_como_terminal(monkeypatch):
    emp = _empresa_con_pendiente("AAA010101AAA", "id-1", estado="2")
    descargas = []
    _con_fiel_simulada(
        monkeypatch,
        {"id-1": _estado("5", mensaje="Solicitud rechazada por el SAT")},
        descargas,
    )

    poller._procesar_empresa("AAA010101AAA", emp)

    sol = config_store.get_solicitud("AAA010101AAA", "id-1")
    assert sol["estado"] == "5"
    assert sol["mensaje"] == "Solicitud rechazada por el SAT"
    assert descargas == []


def test_colgada_72h_vence_sin_ir_al_sat(monkeypatch):
    emp = _empresa_con_pendiente("AAA010101AAA", "id-1", estado="2", horas=100)

    def explota(*a, **kw):
        raise AssertionError("no debió tocar la red del SAT")

    monkeypatch.setattr(poller, "_fiel_de", explota)

    poller._procesar_empresa("AAA010101AAA", emp)

    sol = config_store.get_solicitud("AAA010101AAA", "id-1")
    assert sol["estado"] == "vencida"


def test_lista_huerfana_se_retoma(monkeypatch):
    """Una solicitud que quedó en "3" (la app se cerró sin bajarla) se descarga."""
    emp = _empresa_con_pendiente("AAA010101AAA", "id-1", estado="3")
    path = config_store._solicitudes_path("AAA010101AAA")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["solicitudes"][0]["package_ids"] = ["PKG_09"]
    path.write_text(json.dumps(data), encoding="utf-8")

    descargas = []
    _con_fiel_simulada(monkeypatch, {}, descargas)

    poller._procesar_empresa("AAA010101AAA", emp)

    assert config_store.get_solicitud("AAA010101AAA", "id-1")["estado"] == "descargada"
    assert len(descargas) == 1


def test_dedup_contra_descarga_en_curso(monkeypatch):
    """Si el endpoint /descargar ya tomó la solicitud, el poller no la duplica."""
    emp = _empresa_con_pendiente("AAA010101AAA", "id-1", estado="3")
    descargas = []
    _con_fiel_simulada(monkeypatch, {}, descargas)

    assert state._iniciar_descarga_ws("id-1") is True  # simula al endpoint
    try:
        poller._procesar_empresa("AAA010101AAA", emp)
    finally:
        state._terminar_descarga_ws("id-1")

    assert descargas == []
    assert config_store.get_solicitud("AAA010101AAA", "id-1")["estado"] == "3"


def test_empresa_sin_fiel_no_verifica(monkeypatch):
    emp = _empresa_con_pendiente("AAA010101AAA", "id-1", estado="2")
    emp["metodos"] = ["ciec"]

    def explota(rfc):
        raise AssertionError("no debió cargar FIEL")

    monkeypatch.setattr(poller, "_fiel_de", explota)
    poller._procesar_empresa("AAA010101AAA", emp)
    assert config_store.get_solicitud("AAA010101AAA", "id-1")["estado"] == "2"


def test_error_de_red_no_cambia_estado(monkeypatch):
    emp = _empresa_con_pendiente("AAA010101AAA", "id-1", estado="2")
    monkeypatch.setattr(poller, "_fiel_de", lambda rfc: FielFake(rfc))
    monkeypatch.setattr(poller, "obtener_token", lambda fiel: "token")

    def falla_ssl(*a, **kw):
        raise RuntimeError("SSL: UNEXPECTED_EOF_WHILE_READING")

    monkeypatch.setattr(poller, "consultar_solicitud", falla_ssl)

    poller._procesar_empresa("AAA010101AAA", emp)  # no debe lanzar
    assert config_store.get_solicitud("AAA010101AAA", "id-1")["estado"] == "2"


def test_una_pasada_salta_archivadas(monkeypatch):
    _empresa_con_pendiente("AAA010101AAA", "id-1", estado="2")
    config_store.archive_empresa("AAA010101AAA")
    procesadas = []
    monkeypatch.setattr(
        poller, "_procesar_empresa", lambda rfc, emp: procesadas.append(rfc)
    )
    poller._una_pasada()
    assert procesadas == []

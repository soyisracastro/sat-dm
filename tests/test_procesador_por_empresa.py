"""Tests del aislamiento por empresa del procesador de comprobantes.

Cubre la migración 007 (datos legacy → dueño o purga), el scoping por
`mi_rfc` (buffer, stats, borrado con cascade compuesto), el doble dueño del
mismo uuid y el contrato del API (rfc explícito + restricción de RFC en la
carga).
"""

import pytest

from sat_descarga.procesador import ProcesadorDB, parse_cfdi
from sat_descarga.procesador import db as db_mod
from sat_descarga.procesador.reportes_cfdi import stats_generales
from sat_descarga.procesador.reportes_pagos import stats_pagos
from sat_descarga.procesador.validaciones import validar_y_anotar

from .test_procesador_cfdi import _cfdi_ingreso_xml
from .test_procesador_pagos import _complemento, _ppd

RFC_A = "AAA010101AAA"  # emisor de los fixtures
RFC_B = "BBB020202BBB"  # receptor de los fixtures


@pytest.fixture()
def db(tmp_path):
    db_mod.resetear_singleton_para_tests()
    inst = ProcesadorDB(tmp_path / "test.db")
    yield inst
    inst.close()
    db_mod.resetear_singleton_para_tests()


# ---------------------------------------------------------------------------
# Scoping por empresa en la DB
# ---------------------------------------------------------------------------


def test_mismo_uuid_bajo_dos_empresas_con_direccion_distinta(db):
    """El mismo CFDI puede vivir bajo la emisora (E) y la receptora (R)."""
    cfdi_a = validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml()))
    cfdi_b = validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml()))

    r_a = db.agregar([cfdi_a], mi_rfc=RFC_A)
    r_b = db.agregar([cfdi_b], mi_rfc=RFC_B)
    assert r_a["agregados"] == 1 and r_b["agregados"] == 1

    items_a = db.listar({"mi_rfc": RFC_A})["items"]
    items_b = db.listar({"mi_rfc": RFC_B})["items"]
    assert len(items_a) == 1 and items_a[0]["direccion"] == "E"
    assert len(items_b) == 1 and items_b[0]["direccion"] == "R"

    # Dedupe POR empresa: recargar bajo A es duplicado, no error.
    r_a2 = db.agregar([validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml()))], mi_rfc=RFC_A)
    assert r_a2 == {"agregados": 0, "duplicados": 1}


def test_agregar_exige_mi_rfc_valido(db):
    cfdi = validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml()))
    with pytest.raises(ValueError):
        db.agregar([cfdi], mi_rfc=None)
    with pytest.raises(ValueError):
        db.agregar([cfdi], mi_rfc="../../etc")


def test_listar_y_stats_acotados_por_empresa(db):
    db.agregar([validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml()))], mi_rfc=RFC_A)
    db.agregar([
        validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml(
            uuid="B1111111-1111-2222-3333-444444444444"))),
        validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml(
            uuid="B2222222-1111-2222-3333-444444444444"))),
    ], mi_rfc=RFC_B)

    assert db.listar({"mi_rfc": RFC_A})["total"] == 1
    assert db.listar({"mi_rfc": RFC_B})["total"] == 2

    s_a = stats_generales(db, {"mi_rfc": RFC_A})
    assert s_a["total_comprobantes"] == 1
    assert s_a["total_global"] == 1  # el "global" también es de LA empresa


def test_stats_pagos_acotados_incluyendo_huerfanos(db):
    # A: complemento huérfano (referencia un PPD nunca cargado).
    db.agregar([
        _complemento(
            "PAG0AAAA-1111-1111-1111-111111111111",
            [("FANTASMA-0000-0000-0000-000000000000", 500.0, 1)],
        ),
    ], mi_rfc=RFC_A)
    # B: PPD conciliado sano.
    db.agregar([
        _ppd("PPD0BBBB-1111-1111-1111-111111111111", total=1000.0),
        _complemento(
            "PAG0BBBB-1111-1111-1111-111111111111",
            [("PPD0BBBB-1111-1111-1111-111111111111", 1000.0, 1)],
        ),
    ], mi_rfc=RFC_B)

    s_a = stats_pagos(db, {"mi_rfc": RFC_A})
    s_b = stats_pagos(db, {"mi_rfc": RFC_B})
    assert s_a["pagos_huerfanos"] == 1 and s_a["total_global_ppd"] == 0
    assert s_b["pagos_huerfanos"] == 0 and s_b["total_global_ppd"] == 1
    assert s_b["pagos_completos"] == 1


def test_borrar_una_empresa_no_toca_la_otra(db):
    """El cascade compuesto limpia las hijas de A sin rozar las de B."""
    for dueno in (RFC_A, RFC_B):
        db.agregar([
            _ppd("PPD11111-1111-1111-1111-111111111111", total=1000.0),
            _complemento(
                "PAGO1111-1111-1111-1111-111111111111",
                [("PPD11111-1111-1111-1111-111111111111", 1000.0, 1)],
            ),
        ], mi_rfc=dueno)

    db.borrar(RFC_A)

    assert db.count({"mi_rfc": RFC_A}) == 0
    assert db.count({"mi_rfc": RFC_B}) == 2
    with db.cursor() as cur:
        cur.execute(
            "SELECT COUNT(*) FROM pagos_relaciones WHERE mi_rfc = ?", (RFC_A,)
        )
        assert cur.fetchone()[0] == 0
        cur.execute(
            "SELECT COUNT(*) FROM pagos_relaciones WHERE mi_rfc = ?", (RFC_B,)
        )
        assert cur.fetchone()[0] == 1


def test_uuids_sin_validar_por_empresa(db):
    db.agregar([validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml()))], mi_rfc=RFC_A)
    db.agregar([validar_y_anotar(parse_cfdi(_cfdi_ingreso_xml(
        uuid="B1111111-1111-2222-3333-444444444444")))], mi_rfc=RFC_B)

    assert db.uuids_sin_validar(RFC_A) == ["AAAAAAAA-1111-2222-3333-444444444444"]
    assert db.uuids_sin_validar(RFC_B) == ["B1111111-1111-2222-3333-444444444444"]


# ---------------------------------------------------------------------------
# Migración 007: datos legacy
# ---------------------------------------------------------------------------


def _crear_db_legacy_v6(path):
    """Crea una DB en schema v6 (pre-aislamiento) con filas y filtros legacy.

    Con sqlite3 plano — no con ProcesadorDB — porque el código nuevo asume
    la columna `mi_rfc` (v7) en sus hooks y aquí queremos el estado exacto
    en el que quedó una instalación vieja.
    """
    import sqlite3

    conn = sqlite3.connect(str(path))
    try:
        for version, sql_path in db_mod._listar_migraciones():
            if version > 6:
                continue
            conn.executescript(sql_path.read_text(encoding="utf-8"))
        conn.execute(
            "INSERT INTO _meta (key, value) VALUES ('schema_version', '6')"
        )
        conn.execute(
            "INSERT INTO cfdis (uuid, tipo, fecha, total, emisor_rfc, receptor_rfc)"
            " VALUES ('U1', 'I', '2026-01-01T00:00:00', 100.0, ?, ?)",
            (RFC_A, RFC_B),
        )
        conn.execute(
            "INSERT INTO conceptos (cfdi_uuid, descripcion) VALUES ('U1', 'x')"
        )
        conn.execute(
            "INSERT INTO pagos_relaciones "
            "(cfdi_pago_uuid, cfdi_pago_fecha_pago, docto_uuid)"
            " VALUES ('U1', '2026-01-01', 'U9')"
        )
        conn.execute(
            """INSERT INTO filtros (key, value) VALUES ('actuales', '{"tipo": "I"}')"""
        )
        conn.commit()
    finally:
        conn.close()


def test_migracion_007_asigna_legacy_a_la_default(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    _crear_db_legacy_v6(path)

    monkeypatch.setattr(db_mod.config_store, "get_default", lambda: RFC_A)
    db = ProcesadorDB(path)
    try:
        assert db.count({"mi_rfc": RFC_A}) == 1
        with db.cursor() as cur:
            for tabla in ("conceptos", "pagos_relaciones"):
                cur.execute(f"SELECT mi_rfc FROM {tabla}")
                assert cur.fetchone()[0] == RFC_A
        # La key de filtros migró a `actuales:{RFC}` y la vieja desapareció.
        assert db.filtros_get(key=f"actuales:{RFC_A}") == {"tipo": "I"}
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM filtros WHERE key = 'actuales'")
            assert cur.fetchone()[0] == 0
    finally:
        db.close()

    # Idempotencia: reabrir con schema ya en v7 no truena ni re-migra.
    db2 = ProcesadorDB(path)
    try:
        assert db2.count({"mi_rfc": RFC_A}) == 1
    finally:
        db2.close()


def test_migracion_007_purga_legacy_sin_default(tmp_path, monkeypatch):
    path = tmp_path / "legacy.db"
    _crear_db_legacy_v6(path)

    monkeypatch.setattr(db_mod.config_store, "get_default", lambda: None)
    db = ProcesadorDB(path)
    try:
        assert db.count() == 0
        with db.cursor() as cur:
            for tabla in ("conceptos", "pagos_relaciones", "filtros"):
                cur.execute(f"SELECT COUNT(*) FROM {tabla}")
                assert cur.fetchone()[0] == 0
    finally:
        db.close()


# ---------------------------------------------------------------------------
# API: contrato rfc + restricción de carga
# ---------------------------------------------------------------------------

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402
from sat_descarga.cli import config_store  # noqa: E402


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")
    monkeypatch.setattr(
        config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta")
    )
    monkeypatch.setattr(db_mod, "DEFAULT_DB_PATH", tmp_path / "procesador.db")
    db_mod.resetear_singleton_para_tests()
    config_store.add_empresa_ciec(RFC_A, "Empresa A", "ciec123")
    yield TestClient(server.app)
    server._limpiar_session()
    db_mod.resetear_singleton_para_tests()


def _files(*xmls: bytes):
    return [("files", (f"cfdi_{i}.xml", xml, "text/xml")) for i, xml in enumerate(xmls)]


def test_cargar_omite_xmls_de_otro_rfc(client):
    propio = _cfdi_ingreso_xml()  # emisor RFC_A
    ajeno = _cfdi_ingreso_xml(
        uuid="AJEN0000-1111-2222-3333-444444444444",
        emisor_rfc="XXX990101XX9", receptor_rfc="YYY990101YY9",
    )
    r = client.post(
        "/procesador/cfdi/cargar", files=_files(propio, ajeno), data={"rfc": RFC_A},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["agregados"] == 1
    assert body["omitidos_rfc"] == 1
    assert body["errores"] == []


def test_cargar_acepta_rfc_en_minusculas_y_autofactura(client):
    minusculas = _cfdi_ingreso_xml(
        uuid="MINUSCUL-1111-2222-3333-444444444444",
        emisor_rfc="aaa010101aaa",  # el SAT a veces lo trae así
    )
    autofactura = _cfdi_ingreso_xml(
        uuid="AUT0FACT-1111-2222-3333-444444444444",
        emisor_rfc=RFC_A, receptor_rfc=RFC_A,
    )
    r = client.post(
        "/procesador/cfdi/cargar",
        files=_files(minusculas, autofactura),
        data={"rfc": RFC_A},
    )
    assert r.json()["agregados"] == 2

    items = client.get("/procesador/cfdi", params={"rfc": RFC_A}).json()["items"]
    por_uuid = {i["uuid"]: i for i in items}
    assert por_uuid["AUT0FACT-1111-2222-3333-444444444444"]["direccion"] == "E"


def test_cargar_sin_rfc_es_422_y_no_registrado_400(client):
    r = client.post("/procesador/cfdi/cargar", files=_files(_cfdi_ingreso_xml()))
    assert r.status_code == 422  # falta el Form obligatorio

    r = client.post(
        "/procesador/cfdi/cargar",
        files=_files(_cfdi_ingreso_xml()),
        data={"rfc": "ZZZ990101ZZ9"},  # shape válido pero fuera del catálogo
    )
    assert r.status_code == 400


def test_get_exige_rfc_y_valida_shape(client):
    assert client.get("/procesador/cfdi").status_code == 422
    assert client.get("/procesador/cfdi", params={"rfc": "no-es-rfc"}).status_code == 400
    assert client.get("/procesador/cfdi", params={"rfc": RFC_A}).status_code == 200


def test_filtros_api_por_empresa(client):
    r = client.put(
        "/procesador/cfdi/filtros", json={"rfc": RFC_A, "tipo": "I"},
    )
    assert r.status_code == 200

    f_a = client.get("/procesador/cfdi/filtros", params={"rfc": RFC_A}).json()
    assert f_a["tipo"] == "I"
    # El rfc es la key, no un filtro: no se persiste dentro del JSON.
    assert "rfc" not in f_a

    # Otra empresa (shape válido) arranca con filtros default.
    f_b = client.get("/procesador/cfdi/filtros", params={"rfc": RFC_B}).json()
    assert f_b["tipo"] is None


def test_delete_borra_solo_la_empresa(client):
    client.post(
        "/procesador/cfdi/cargar", files=_files(_cfdi_ingreso_xml()), data={"rfc": RFC_A},
    )
    # B también registrada, con su propio buffer (mismo XML: A emisor, B receptor).
    config_store.add_empresa_ciec(RFC_B, "Empresa B", "ciec456")
    client.post(
        "/procesador/cfdi/cargar", files=_files(_cfdi_ingreso_xml()), data={"rfc": RFC_B},
    )

    assert client.delete("/procesador/cfdi", params={"rfc": RFC_A}).status_code == 200
    assert client.get("/procesador/cfdi", params={"rfc": RFC_A}).json()["total"] == 0
    assert client.get("/procesador/cfdi", params={"rfc": RFC_B}).json()["total"] == 1

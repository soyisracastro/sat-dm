"""Persistencia de calculadoras por RFC — aislamiento entre empresas."""

import json

import pytest

from sat_descarga.calculadoras import store
from sat_descarga.cli import config_store


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")


RFC_A = "CAUI890921DAA"
RFC_B = "XAXX010101000"


def test_estado_vacio():
    data = store.get_estado(RFC_A)
    assert data == {"version": 1, "estados": {}, "guardados": []}
    assert store.get_estado_calculadora(RFC_A, "finiquito") is None


def test_aislamiento_entre_rfcs():
    """El requisito central: el estado de A jamás pisa el de B."""
    store.set_estado_calculadora(RFC_A, "finiquito", {"salario": 100}, {"neto": 90}, 2026)
    store.set_estado_calculadora(RFC_B, "finiquito", {"salario": 200}, {"neto": 180}, 2026)

    a = store.get_estado_calculadora(RFC_A, "finiquito")
    b = store.get_estado_calculadora(RFC_B, "finiquito")
    assert a["inputs"]["salario"] == 100
    assert b["inputs"]["salario"] == 200

    # Archivos separados por RFC
    dir_calc = config_store.get_config_dir() / "calculadoras"
    assert (dir_calc / f"{RFC_A}.json").exists()
    assert (dir_calc / f"{RFC_B}.json").exists()


def test_estado_por_calculadora_independiente():
    store.set_estado_calculadora(RFC_A, "finiquito", {"x": 1}, {"y": 1}, 2026)
    store.set_estado_calculadora(RFC_A, "aguinaldo", {"x": 2}, {"y": 2}, 2026)
    assert store.get_estado_calculadora(RFC_A, "finiquito")["inputs"] == {"x": 1}
    assert store.get_estado_calculadora(RFC_A, "aguinaldo")["inputs"] == {"x": 2}


def test_sin_rfc_usa_general():
    store.set_estado_calculadora(None, "sbc", {"s": 1}, {"r": 1}, 2026)
    assert store.get_estado_calculadora(None, "sbc")["inputs"] == {"s": 1}
    assert (config_store.get_config_dir() / "calculadoras" / "__general__.json").exists()


def test_rfc_invalido_rechazado():
    with pytest.raises(ValueError, match="RFC inválido"):
        store.set_estado_calculadora("../../etc/passwd", "sbc", {}, {}, 2026)
    with pytest.raises(ValueError, match="RFC inválido"):
        store.get_estado("no-es-rfc")


def test_calculadora_desconocida():
    with pytest.raises(ValueError, match="desconocida"):
        store.set_estado_calculadora(RFC_A, "bitcoin", {}, {}, 2026)


def test_guardados_lifo_y_filtro():
    store.add_guardado(RFC_A, "finiquito", "Juan", {"a": 1}, {"b": 1}, 2026)
    store.add_guardado(RFC_A, "liquidacion", "Ana", {"a": 2}, {"b": 2}, 2026)
    store.add_guardado(RFC_A, "finiquito", "Luis", {"a": 3}, {"b": 3}, 2026)

    todos = store.list_guardados(RFC_A)
    assert [g["nombre"] for g in todos] == ["Luis", "Ana", "Juan"]  # recientes primero

    finiquitos = store.list_guardados(RFC_A, "finiquito")
    assert [g["nombre"] for g in finiquitos] == ["Luis", "Juan"]

    # Los guardados de A no aparecen en B
    assert store.list_guardados(RFC_B) == []


def test_delete_guardado():
    g = store.add_guardado(RFC_A, "ptu", "PTU 2025", {}, {}, 2026)
    assert store.delete_guardado(RFC_A, g["id"]) is True
    assert store.delete_guardado(RFC_A, g["id"]) is False
    assert store.list_guardados(RFC_A) == []


def test_cap_de_guardados(monkeypatch):
    monkeypatch.setattr(store, "MAX_GUARDADOS", 5)
    for i in range(8):
        store.add_guardado(RFC_A, "sbc", f"g{i}", {}, {}, 2026)
    guardados = store.list_guardados(RFC_A)
    assert len(guardados) == 5
    assert guardados[0]["nombre"] == "g7"  # se conservan los más recientes


def test_archivo_corrupto_resiliente():
    store.set_estado_calculadora(RFC_A, "sbc", {"s": 1}, {"r": 1}, 2026)
    path = config_store.get_config_dir() / "calculadoras" / f"{RFC_A}.json"
    path.write_bytes(b"\x00" * 64)  # corrupción real (apagado abrupto)
    data = store.get_estado(RFC_A)
    assert data["estados"] == {}  # fallback limpio, sin explotar


def test_persistencia_en_disco():
    store.set_estado_calculadora(RFC_A, "isr", {"ingreso": 15000}, {"isr": 1402.82}, 2026)
    path = config_store.get_config_dir() / "calculadoras" / f"{RFC_A}.json"
    en_disco = json.loads(path.read_text(encoding="utf-8"))
    assert en_disco["version"] == 1
    assert en_disco["estados"]["isr"]["anio"] == 2026
    assert "actualizado_en" in en_disco["estados"]["isr"]

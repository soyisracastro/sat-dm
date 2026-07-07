"""Tests del subcomando `sat-dm diot` (CliRunner)."""

import pytest
from click.testing import CliRunner

from sat_descarga.cli import config_store
from sat_descarga.cli.main import cli
from sat_descarga.procesador import parse_cfdi
from sat_descarga.procesador import db as db_mod

from .test_diot import MI_RFC, PROV_A, _xml


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "get_descargas_dir", lambda: str(tmp_path / "descargas"))
    db_mod.resetear_singleton_para_tests()
    db_mod.abrir_db(tmp_path / "procesador.db")
    yield
    db_mod.resetear_singleton_para_tests()


def test_diot_en_help():
    out = CliRunner().invoke(cli, ["--help"]).output
    assert "diot" in out


def test_diot_genera_txt(tmp_path):
    db_mod.abrir_db().agregar([parse_cfdi(_xml("CLI-1"))], mi_rfc=MI_RFC)
    salida = tmp_path / "salida" / "mi_diot.txt"
    r = CliRunner().invoke(
        cli, ["diot", "--rfc", MI_RFC, "--periodo", "2026-05", "--salida", str(salida)]
    )
    assert r.exit_code == 0, r.output
    data = salida.read_bytes()
    assert data.startswith(b"\xef\xbb\xbf")
    assert PROV_A.encode() in data


def test_diot_sin_cfdis_falla_con_mensaje():
    r = CliRunner().invoke(cli, ["diot", "--rfc", MI_RFC, "--periodo", "2026-05"])
    assert r.exit_code == 1
    assert "No hay CFDIs recibidos" in r.output


def test_diot_periodo_invalido():
    r = CliRunner().invoke(cli, ["diot", "--rfc", MI_RFC, "--periodo", "05-2026"])
    assert r.exit_code == 1
    assert "Periodo inválido" in r.output

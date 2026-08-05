"""Tests de la presentación DIOT en el portal (lógica pura, sin browser).

El flujo con Playwright no se prueba e2e (convención del repo): se prueban los
helpers puros (totales del TXT, claves de periodo, comparación contra el
portal) y la superficie del CLI.
"""

from pathlib import Path

import pytest
from click.testing import CliRunner

from sat_descarga.cli.main import cli
from sat_descarga.portal.diot_presentacion import (
    DIOT_HOST,
    DIOT_URL_ENTRADA,
    clave_periodo,
    comparar_totales,
    numero_de_texto,
    totales_de_txt,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _linea(rfc="AAA010101AAA", iva_16=0, ret=0, valor_16=0):
    campos = ["0"] * 54
    campos[0], campos[1], campos[2] = "04", "85", rfc
    for i in (3, 4, 5, 6):          # campos 4-7 (id fiscal/extranjero) vacíos
        campos[i] = ""
    campos[11] = str(valor_16)      # campo 12: valor actos 16%
    campos[21] = str(iva_16)        # campo 22: IVA acreditable 16% exclusivo
    campos[47] = str(ret)           # campo 48: IVA retenido
    campos[53] = "01"               # campo 54: manifiesto
    return "|".join(campos)


# --- totales_de_txt --------------------------------------------------------

def test_totales_de_txt(tmp_path):
    txt = tmp_path / "diot.txt"
    contenido = "\r\n".join([
        _linea(rfc="AAA010101AAA", iva_16=100, ret=7, valor_16=625),
        _linea(rfc="BBB010101BBB", iva_16=50, ret=0, valor_16=313),
    ]) + "\r\n"
    txt.write_bytes(b"\xef\xbb\xbf" + contenido.encode("utf-8"))

    t = totales_de_txt(txt)
    assert t == {"operaciones": 2, "iva_acreditable": 150, "iva_retenido": 7,
                 "layout": "2025"}


def _linea_v24(rfc="AAA010101AAA", valor_16=0, ret=0, dev=0):
    campos = [""] * 23
    campos[0] = "04"
    campos[1] = "85"
    campos[2] = rfc
    campos[7] = str(valor_16)    # campo 8: valor de actos 16% (BASE)
    campos[8] = "0"
    campos[21] = str(ret)        # campo 22: IVA retenido
    campos[22] = str(dev)        # campo 23: IVA devoluciones/bonificaciones
    return "|".join(campos)


def test_totales_de_txt_layout_v24(tmp_path):
    # ejercicios 2024-y-anteriores: 23 campos, reporta BASES; el IVA
    # trasladado se deriva como round(16% × valor) por renglón
    txt = tmp_path / "diot_2021.txt"
    contenido = "\r\n".join([
        _linea_v24(rfc="AAA010101AAA", valor_16=3016879, ret=0, dev=1158),
        _linea_v24(rfc="BBB010101BBB", valor_16=650, ret=104, dev=104),
    ]) + "\r\n"
    txt.write_bytes(b"\xef\xbb\xbf" + contenido.encode("utf-8"))

    t = totales_de_txt(txt)
    assert t["layout"] == "v24"
    assert t["operaciones"] == 2
    assert t["iva_trasladado"] == round(3016879 * 0.16) + round(650 * 0.16)
    assert t["iva_devoluciones"] == 1262
    assert t["iva_retenido"] == 104
    assert t["iva_acreditable"] == t["iva_trasladado"] - 1262


def test_totales_de_txt_layout_desconocido(tmp_path):
    txt = tmp_path / "malo.txt"
    txt.write_text("04|85|AAA010101AAA|1|2", encoding="utf-8")
    try:
        totales_de_txt(txt)
        assert False, "debió rechazar un layout de 5 campos"
    except ValueError as e:
        assert "Layout desconocido" in str(e)


def test_totales_de_txt_suma_toda_la_seccion_acreditable(tmp_path):
    # el campo 19 (proporción RF norte) también cuenta como IVA acreditable
    campos = _linea(iva_16=100).split("|")
    campos[18] = "25"  # campo 19
    txt = tmp_path / "diot.txt"
    txt.write_text("|".join(campos), encoding="utf-8")
    assert totales_de_txt(txt)["iva_acreditable"] == 125


def test_totales_de_txt_rechaza_lineas_malformadas(tmp_path):
    txt = tmp_path / "malo.txt"
    txt.write_text("04|85|AAA010101AAA", encoding="utf-8")
    with pytest.raises(ValueError, match="campos"):
        totales_de_txt(txt)


def test_totales_de_txt_con_golden_del_exportador():
    """El TXT que genera nuestro propio exportador debe ser parseable."""
    golden = FIXTURES / "diot_esperado.txt"
    if not golden.exists():
        pytest.skip("no está el golden del exportador")
    t = totales_de_txt(golden)
    assert t["operaciones"] > 0


# --- clave_periodo / numero_de_texto ---------------------------------------

@pytest.mark.parametrize("entrada,esperado", [
    (1, "001"), ("4", "004"), ("04", "004"), ("012", "012"), (12, "012"),
])
def test_clave_periodo(entrada, esperado):
    assert clave_periodo(entrada) == esperado


@pytest.mark.parametrize("entrada", [0, 13, "x", None, ""])
def test_clave_periodo_invalido(entrada):
    with pytest.raises(ValueError):
        clave_periodo(entrada)


@pytest.mark.parametrize("texto,esperado", [
    ("$1,209,655.00", 1209655),
    ("1,209,655", 1209655),
    ("9645", 9645),
    ("", 0),
    ("  $0.00 ", 0),
])
def test_numero_de_texto(texto, esperado):
    assert numero_de_texto(texto) == esperado


# --- comparar_totales ------------------------------------------------------

def test_comparar_totales_tolera_redondeo():
    esperado = {"operaciones": 15, "iva_acreditable": 1209655, "iva_retenido": 9645}
    portal = {"operaciones": 15, "iva_acreditable": 1209653, "iva_retenido": 9647}
    assert comparar_totales(esperado, portal) == []


def test_comparar_totales_detecta_diferencias():
    esperado = {"operaciones": 15, "iva_acreditable": 1209655, "iva_retenido": 9645}
    portal = {"operaciones": 14, "iva_acreditable": 1209600, "iva_retenido": 9645}
    discrepancias = comparar_totales(esperado, portal)
    assert len(discrepancias) == 2
    assert any("Operaciones" in d for d in discrepancias)
    assert any("IVA acreditable" in d for d in discrepancias)


# --- superficie del CLI ----------------------------------------------------

def test_diot_group_tiene_subcomandos():
    out = CliRunner().invoke(cli, ["diot", "--help"]).output
    assert "generar" in out
    assert "presentar" in out


def test_diot_presentar_documenta_limitante_estimulos():
    out = CliRunner().invoke(cli, ["diot", "presentar", "--help"]).output
    assert "estímulos" in out
    assert "--enviar" in out


def test_diot_sin_opciones_muestra_ayuda():
    r = CliRunner().invoke(cli, ["diot"])
    assert r.exit_code == 0
    assert "generar" in r.output


# --- constantes del portal -------------------------------------------------

def test_constantes_portal():
    assert DIOT_URL_ENTRADA.startswith("https://")
    assert DIOT_HOST in DIOT_URL_ENTRADA

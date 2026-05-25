"""Tests de las constantes/flujo de la Constancia de Situación Fiscal.

Verifican decisiones clave del flujo (entrada por el lanzador, selectores), sin
tocar red/browser.
"""

from sat_descarga.portal import constancia as C


def test_entrada_fiel_usa_el_mismo_lanzador_ciec():
    # e.firma entra por el MISMO lanzador (tipoLogeo=c) y de ahí cambia con #buttonFiel;
    # tipoLogeo=e daba pantalla en blanco.
    assert "tipoLogeo=c" in C.CSF_URL_ENTRADA
    assert C.CSF_URL_ENTRADA_FIEL == C.CSF_URL_ENTRADA
    assert "operacion/43824" in C.CSF_URL_ENTRADA


def test_landing_y_boton():
    assert C.CSF_LANDING == "wwwmat.sat.gob.mx/operacion/43824"
    assert "Generar Constancia" in C.CSF_BTN


def test_api_publica_constancia():
    assert callable(C.descargar_constancia_ciec)
    assert callable(C.descargar_constancia_fiel)

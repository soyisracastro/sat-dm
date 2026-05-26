"""Tests del helper de rutas de salida (sat_descarga/core/paths.py).

Lógica pura, sin red ni FS: solo composición de Paths del layout `descargas/`.
"""

from datetime import date
from pathlib import Path

import pytest

from sat_descarga.core import paths


DESDE = date(2026, 1, 1)
HASTA = date(2026, 3, 31)
RANGO = "2026-01-01_a_2026-03-31"


def test_etiqueta_rango():
    assert paths.etiqueta_rango(DESDE, HASTA) == RANGO


def test_dir_cfdi_emitidos_y_recibidos_con_rango():
    assert paths.dir_cfdi("CAUI890921DAA", "E", DESDE, HASTA) == Path(
        f"descargas/cfdi/CAUI890921DAA/emitidos/{RANGO}"
    )
    assert paths.dir_cfdi("CAUI890921DAA", "R", DESDE, HASTA) == Path(
        f"descargas/cfdi/CAUI890921DAA/recibidos/{RANGO}"
    )


def test_dir_cfdi_normaliza_rfc_y_tipo():
    # RFC en minúsculas y tipo en minúscula se normalizan.
    assert paths.dir_cfdi("caui890921daa", "e", DESDE, HASTA) == Path(
        f"descargas/cfdi/CAUI890921DAA/emitidos/{RANGO}"
    )


def test_dir_cfdi_salida_base_override():
    assert paths.dir_cfdi("RFC", "E", DESDE, HASTA, salida_base="/tmp/x") == Path(
        f"/tmp/x/cfdi/RFC/emitidos/{RANGO}"
    )
    # None → usa descargas/
    assert paths.dir_cfdi("RFC", "E", DESDE, HASTA, salida_base=None) == Path(
        f"descargas/cfdi/RFC/emitidos/{RANGO}"
    )


def test_dir_cfdi_sin_fechas_omite_carpeta_de_evento():
    # Aunque AGRUPAR_POR_EVENTO sea True, sin fechas no hay carpeta de solicitud.
    assert paths.dir_cfdi("RFC", "E") == Path("descargas/cfdi/RFC/emitidos")


def test_dir_cfdi_toggle_apagado(monkeypatch):
    monkeypatch.setattr(paths, "AGRUPAR_POR_EVENTO", False)
    assert paths.dir_cfdi("RFC", "R", DESDE, HASTA) == Path(
        "descargas/cfdi/RFC/recibidos"
    )


def test_dir_cfdi_base():
    assert paths.dir_cfdi_base("rfc") == Path("descargas/cfdi/RFC")
    assert paths.dir_cfdi_base("rfc", salida_base="/tmp/x") == Path("/tmp/x/cfdi/RFC")


def test_dir_documento_constancia_y_opinion():
    assert paths.dir_documento(paths.TIPO_CONSTANCIA, "rfc") == Path(
        "descargas/constancia/RFC"
    )
    assert paths.dir_documento(paths.TIPO_OPINION, "rfc") == Path(
        "descargas/opinion/RFC"
    )


def test_dir_documento_sin_rfc():
    # FIEL sin RFC resuelto → carpeta sin_rfc (el PDF embebe el RFC en el nombre).
    assert paths.dir_documento(paths.TIPO_CONSTANCIA, "") == Path(
        "descargas/constancia/sin_rfc"
    )


def test_singular_plural_es_un_solo_edit():
    # El segmento de tipo se deriva de la constante: cambiarla mueve todo el árbol.
    d = paths.dir_cfdi("RFC", "E", DESDE, HASTA)
    assert d.parts[1] == paths.TIPO_CFDI
    assert paths.base() == Path(paths.BASE_DIR)

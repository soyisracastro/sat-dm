"""Tests de la lógica pura del scraper de CFDIs por portal (sat_descarga.portal.cfdi).

No tocan red ni browser: solo helpers deterministas. El flujo end-to-end (login +
captura de PDF) se prueba manualmente con credenciales.
"""

from datetime import date

from sat_descarga.portal import cfdi
from sat_descarga.portal.cfdi import _normalizar_tipos, _es_uuid, _dias


def test_login_pasa_pedir_captcha(monkeypatch):
    # El callback de captcha (bridge del agente) debe llegar a iniciar_sesion_ciec.
    capturado = {}
    monkeypatch.setattr(cfdi, "iniciar_sesion_ciec", lambda *a, **k: capturado.update(k))
    cliente = cfdi.CIECClient("CAUI890921DAA", "ciec")
    centinela = object()
    cliente._login(object(), pedir_captcha=centinela)
    assert capturado.get("pedir_captcha") is centinela


def test_normalizar_tipos():
    assert _normalizar_tipos("R") == ["R"]
    assert _normalizar_tipos("E") == ["E"]
    assert _normalizar_tipos("r") == ["R"]
    assert _normalizar_tipos("RE") == ["R", "E"]
    assert _normalizar_tipos("ER") == ["R", "E"]
    assert _normalizar_tipos("") == ["R", "E"]
    assert _normalizar_tipos("ambos") == ["R", "E"]
    assert _normalizar_tipos(None) == ["R", "E"]


def test_es_uuid():
    assert _es_uuid("28424F1E-CE4F-4B41-AE9F-E56645B6A2EE")
    assert _es_uuid("28424f1e-ce4f-4b41-ae9f-e56645b6a2ee")  # case-insensitive
    assert _es_uuid("  28424F1E-CE4F-4B41-AE9F-E56645B6A2EE  ")  # trim
    assert not _es_uuid("not-a-uuid")
    assert not _es_uuid("")
    assert not _es_uuid("28424F1E-CE4F-4B41-AE9F")  # incompleto


def test_dias():
    assert list(_dias(date(2025, 1, 1), date(2025, 1, 3))) == [
        date(2025, 1, 1), date(2025, 1, 2), date(2025, 1, 3),
    ]
    assert list(_dias(date(2025, 1, 10), date(2025, 1, 10))) == [date(2025, 1, 10)]
    assert list(_dias(date(2025, 1, 5), date(2025, 1, 1))) == []  # rango invertido

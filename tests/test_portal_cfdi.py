"""Tests de la lógica pura del scraper de CFDIs por portal (sat_descarga.portal.cfdi).

No tocan red ni browser: solo helpers deterministas. El flujo end-to-end (login +
captura de PDF) se prueba manualmente con credenciales.
"""

from datetime import date

import pytest

from sat_descarga.portal import cfdi
from sat_descarga.portal.cfdi import (
    _normalizar_tipos,
    _es_uuid,
    _dias,
    _verificar_sesion_portal,
)
from sat_descarga.portal.login import SesionPortalInvalida

URL_ERROR_ASPX = (
    "https://portalcfdi.facturaelectronica.sat.gob.mx/Error.aspx"
    "?aspxerrorpath=/ConsultaReceptor.aspx"
)


def test_login_ciec_pasa_pedir_captcha(monkeypatch):
    # El callback de captcha (bridge del agente) debe llegar a iniciar_sesion_ciec.
    capturado = {}
    monkeypatch.setattr(cfdi, "iniciar_sesion_ciec", lambda *a, **k: capturado.update(k))
    cliente = cfdi.CIECClient("CAUI890921DAA", "ciec")
    centinela = object()
    cliente._login_ciec(object(), pedir_captcha=centinela)
    assert capturado.get("pedir_captcha") is centinela


def test_login_ciec_apunta_al_portal_cfdi(monkeypatch):
    # url_entrada y predicado `exito` no deben cambiar al introducir login inyectable.
    capturado = {}
    monkeypatch.setattr(cfdi, "iniciar_sesion_ciec", lambda *a, **k: capturado.update(k))
    cfdi.CIECClient("CAUI890921DAA", "ciec")._login_ciec(object())
    assert capturado["url_entrada"].startswith(cfdi.PORTAL_URL)
    exito = capturado["exito"]
    assert exito("https://portalcfdi.facturaelectronica.sat.gob.mx/Consulta.aspx") is True
    assert exito("https://cfdiau.sat.gob.mx/nidp/wsfed/ep") is False


def test_descargar_cfdi_fiel_arma_login_lambda(monkeypatch):
    # `descargar_cfdi_fiel` debe construir un `login` que llame a iniciar_sesion_fiel
    # con la URL del portal CFDI, y delegar todo lo demás al cliente compartido.
    capturado_fiel = {}
    monkeypatch.setattr(cfdi, "iniciar_sesion_fiel",
                        lambda *a, **k: capturado_fiel.update(args=a, kwargs=k))

    # Stub del FIEL para no leer un .cer real.
    class FielStub:
        def __init__(self, *_a, **_k):
            self.rfc = "CAUI890921DAA"
    monkeypatch.setattr("sat_descarga.core.fiel.FIEL", FielStub)

    capturado_descarga = {}

    def descargar_stub(self, **kwargs):
        capturado_descarga.update(kwargs)
        # Disparamos el login que armó descargar_cfdi_fiel para verificarlo.
        kwargs["login"](page=object())
        return []
    monkeypatch.setattr(cfdi.CIECClient, "descargar", descargar_stub)

    cfdi.descargar_cfdi_fiel(
        cer_path="/tmp/x.cer", key_path="/tmp/x.key", password="pw",
        fecha_inicio=date(2026, 4, 1), fecha_fin=date(2026, 4, 30),
        tipo_comprobante="R", directorio_salida="/tmp/out", max_registros=5,
    )
    # El cliente compartido recibió los args correctos, vía la rama `login=`.
    assert capturado_descarga["tipo_comprobante"] == "R"
    assert capturado_descarga["max_registros"] == 5
    assert callable(capturado_descarga.get("login"))
    # El lambda llamó a iniciar_sesion_fiel con cer/key/password + URL/exito del portal.
    args = capturado_fiel["args"]
    assert args[1] == "/tmp/x.cer" and args[2] == "/tmp/x.key" and args[3] == "pw"
    kwargs = capturado_fiel["kwargs"]
    assert kwargs["url_entrada"].startswith(cfdi.PORTAL_URL)
    assert kwargs["exito"]("https://portalcfdi.facturaelectronica.sat.gob.mx/x") is True
    assert kwargs["exito"]("https://cfdiau.sat.gob.mx/x") is False


def test_descargar_bifurca_segun_login_inyectado(monkeypatch):
    # Cuando se pasa login=, NO se debe llamar _login_ciec; y viceversa.
    # `monkeypatch.setattr("playwright.sync_api…")` requiere que el módulo
    # se pueda importar — playwright vive en el extra opcional `ciec`, así
    # que en CI base lo saltamos. La cobertura local con el extra `ciec`
    # instalado sigue siendo válida.
    pytest.importorskip("playwright")
    llamadas = {"ciec": 0, "inyectado": 0}
    monkeypatch.setattr(cfdi.CIECClient, "_login_ciec",
                        lambda self, page, pedir_captcha=None: llamadas.__setitem__("ciec", llamadas["ciec"] + 1))
    # Cortocircuitar el resto de descargar() apenas pase el login, para no abrir Playwright.
    monkeypatch.setattr(cfdi.CIECClient, "_descargar_tipo",
                        lambda *a, **k: [])

    # Atajo: stubbear sync_playwright para no abrir browser real.
    class CtxStub:
        def __enter__(self): return self
        def __exit__(self, *a): pass
        def chromium(self):  # no-op
            return self
    class PageStub:
        pass
    class BrowserStub:
        def new_context(self, **_k): return self
        def new_page(self): return PageStub()
        def close(self): pass
    class PStub:
        chromium = type("c", (), {"launch": staticmethod(lambda **_k: BrowserStub())})()
    import contextlib
    @contextlib.contextmanager
    def pw_stub():
        yield PStub
    monkeypatch.setattr("playwright.sync_api.sync_playwright", pw_stub, raising=False)

    cliente = cfdi.CIECClient("CAUI890921DAA", "ciec")
    cliente.descargar(date(2026, 1, 1), date(2026, 1, 1), tipo_comprobante="R")
    assert llamadas["ciec"] == 1 and llamadas["inyectado"] == 0

    cliente.descargar(date(2026, 1, 1), date(2026, 1, 1), tipo_comprobante="R",
                      login=lambda page: llamadas.__setitem__("inyectado", llamadas["inyectado"] + 1))
    assert llamadas["ciec"] == 1 and llamadas["inyectado"] == 1


class _PageUrl:
    """Page mínima: solo la URL (y sin botón de búsqueda)."""

    def __init__(self, url):
        self.url = url

    def query_selector(self, _sel):
        return None


def test_verificar_sesion_portal_detecta_error_aspx():
    # Rebote del portal a Error.aspx (sesión e.firma inválida, DESKTOP-1E)
    # → error claro y reintenable, no el genérico del botón.
    with pytest.raises(SesionPortalInvalida, match="rechazó la sesión"):
        _verificar_sesion_portal(_PageUrl(URL_ERROR_ASPX))
    # Página normal de consulta → no pasa nada.
    _verificar_sesion_portal(_PageUrl(f"{cfdi.PORTAL_URL}/ConsultaReceptor.aspx"))


def test_buscar_distingue_error_aspx_de_boton_ausente():
    pytest.importorskip("playwright")
    cliente = cfdi.CIECClient("CAUI890921DAA", "ciec")
    # Sin botón + parado en Error.aspx → diagnóstico de sesión inválida.
    with pytest.raises(SesionPortalInvalida):
        cliente._buscar(_PageUrl(URL_ERROR_ASPX))
    # Sin botón en una página normal → se conserva el error genérico.
    with pytest.raises(RuntimeError, match="botón de búsqueda"):
        cliente._buscar(_PageUrl(f"{cfdi.PORTAL_URL}/ConsultaReceptor.aspx"))


def _stub_navegador(monkeypatch):
    """Stubbea Chromium/Playwright para correr descargar() sin browser real."""
    pytest.importorskip("playwright")
    import contextlib

    class PageStub:
        url = f"{cfdi.PORTAL_URL}/"

    class BrowserStub:
        def new_context(self, **_k):
            return self

        def new_page(self):
            return PageStub()

        def close(self):
            pass

    monkeypatch.setattr("sat_descarga.portal.setup.asegurar_chromium", lambda: None)
    monkeypatch.setattr(
        "sat_descarga.portal.setup.lanzar_chromium",
        lambda p, **_k: BrowserStub(),
    )

    @contextlib.contextmanager
    def pw_stub():
        yield object()

    monkeypatch.setattr("playwright.sync_api.sync_playwright", pw_stub, raising=False)


def test_descargar_reintenta_login_ante_sesion_invalida(monkeypatch, tmp_path):
    # Primer intento rebota (Error.aspx) → un re-login y reintento del mismo
    # tipo; el rebote transitorio no debe tronar la descarga.
    _stub_navegador(monkeypatch)
    logins = {"n": 0}
    intentos = {"n": 0}

    def tipo_stub(self, *_a, **_k):
        intentos["n"] += 1
        if intentos["n"] == 1:
            raise SesionPortalInvalida("rebote a Error.aspx")
        return []

    monkeypatch.setattr(cfdi.CIECClient, "_descargar_tipo", tipo_stub)

    res = cfdi.CIECClient("CAUI890921DAA", "ciec").descargar(
        date(2026, 1, 1), date(2026, 1, 1), tipo_comprobante="R",
        directorio_salida=str(tmp_path),
        login=lambda page: logins.__setitem__("n", logins["n"] + 1),
    )
    assert res == []
    assert logins["n"] == 2    # login inicial + reintento
    assert intentos["n"] == 2  # la búsqueda se reintentó una vez


def test_descargar_solo_reintenta_una_vez(monkeypatch, tmp_path):
    # Si el rebote persiste tras el re-login, el error claro sube al caller.
    _stub_navegador(monkeypatch)
    logins = {"n": 0}
    monkeypatch.setattr(
        cfdi.CIECClient, "_descargar_tipo",
        lambda self, *_a, **_k: (_ for _ in ()).throw(
            SesionPortalInvalida("rebote persistente")
        ),
    )

    with pytest.raises(SesionPortalInvalida):
        cfdi.CIECClient("CAUI890921DAA", "ciec").descargar(
            date(2026, 1, 1), date(2026, 1, 1), tipo_comprobante="R",
            directorio_salida=str(tmp_path),
            login=lambda page: logins.__setitem__("n", logins["n"] + 1),
        )
    assert logins["n"] == 2  # inicial + UN reintento, no más


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

"""Tools MCP que entregan archivos (deploy/gateway/main.py): CSF, Opinión
32-D, ZIP de CFDIs y Excel del procesador ahora se adjuntan embebidos
(EmbeddedResource + blob base64) en la misma respuesta de la tool, en vez de
solo devolver un link que requiere la API key del usuario — el asistente no
tiene esa key, así que un link por sí solo dejaba al usuario sin el archivo
en el chat."""

import asyncio
import base64
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("mcp")
from fastapi import HTTPException  # noqa: E402
from mcp.types import EmbeddedResource, TextContent  # noqa: E402

GATEWAY_DIR = Path(__file__).parent.parent / "deploy" / "gateway"

PDF_FALSO = b"%PDF-1.4 contenido de prueba"
ZIP_FALSO = b"PK\x03\x04 contenido de prueba"
XLSX_FALSO = b"contenido de prueba xlsx"
RFC = "CAMY89051862A"


@pytest.fixture(scope="module")
def gw(tmp_path_factory):
    previos = {k: os.environ.get(k) for k in ("OAUTH_DB_PATH", "EXIGIR_LICENCIA")}
    os.environ["OAUTH_DB_PATH"] = str(tmp_path_factory.mktemp("oauth") / "oauth.db")
    os.environ["EXIGIR_LICENCIA"] = "0"
    sys.path.insert(0, str(GATEWAY_DIR))
    for mod in ("main", "oauth"):
        sys.modules.pop(mod, None)
    main_mod = importlib.import_module("main")
    yield main_mod
    sys.path.remove(str(GATEWAY_DIR))
    for mod in ("main", "oauth"):
        sys.modules.pop(mod, None)
    for k, v in previos.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


@pytest.fixture(autouse=True)
def usuario(gw):
    token = gw.ctx_user.set({"user_id": "user-1", "scopes": ["mcp"], "email": "prueba@todoconta.com"})
    yield
    gw.ctx_user.reset(token)


@pytest.fixture(autouse=True)
def agente(gw, monkeypatch):
    monkeypatch.setattr(gw, "_agente_de", lambda user: ("http://agente-fake:8787", {"X-Agent-Token": "t"}))


def _call(gw, nombre, args):
    # asyncio.run() ejecuta la corrutina en un Task nuevo que copia el
    # contexto actual (verificado: contextvars.set() en el hilo del test SÍ
    # se propaga), así que ctx_user llega intacto a la tool.
    return asyncio.run(gw.mcp_srv.call_tool(nombre, args))


def _blob_pdf(resultado):
    assert len(resultado) == 2
    assert isinstance(resultado[0], TextContent)
    recurso = resultado[1]
    assert isinstance(recurso, EmbeddedResource)
    assert recurso.resource.mimeType == "application/pdf"
    return base64.b64decode(recurso.resource.blob)


class TestDescargarCsf:
    def test_generada_ahora_se_adjunta(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": ["fiel"], "efirma_lista": True})
        monkeypatch.setattr(gw.requests, "post", lambda url, **kw: SimpleNamespace(status_code=200, json=lambda: {"path": "constancia/x.pdf"}))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "recién" not in resultado[0].text  # solo lleva nota cuando es del archivo
        assert RFC in resultado[0].text

    def test_sin_efirma_cae_a_la_copia_archivada(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": [], "efirma_lista": False})
        monkeypatch.setattr(gw, "_csf_archivada", lambda base, h, rfc: ("archivo/vieja.pdf", "2026-01-05T00:00:00Z"))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "2026-01-05" in resultado[0].text
        assert "archivo" in resultado[0].text

    def test_sin_efirma_ni_archivo_solo_texto(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": [], "efirma_lista": False})
        monkeypatch.setattr(gw, "_csf_archivada", lambda base, h, rfc: (None, None))

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert len(resultado) == 1
        assert isinstance(resultado[0], TextContent)
        assert "e.firma" in resultado[0].text

    def test_efirma_invalida_409_cae_a_archivo(self, gw, monkeypatch):
        def _activar(base, h, rfc):
            raise HTTPException(status_code=409, detail="La e.firma no es válida.")
        monkeypatch.setattr(gw, "_activar_empresa", _activar)
        monkeypatch.setattr(gw, "_csf_archivada", lambda base, h, rfc: ("archivo/vieja.pdf", None))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO

    def test_empresa_inexistente_sin_archivo_pasa_el_detalle(self, gw, monkeypatch):
        def _activar(base, h, rfc):
            raise HTTPException(status_code=404, detail=f"La empresa {rfc} no existe.")
        monkeypatch.setattr(gw, "_activar_empresa", _activar)
        monkeypatch.setattr(gw, "_csf_archivada", lambda base, h, rfc: (None, None))

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert len(resultado) == 1
        assert "no existe" in resultado[0].text


class TestDescargarOpinion:
    def test_generada_se_adjunta(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": ["fiel"], "efirma_lista": True})
        monkeypatch.setattr(gw.requests, "post", lambda url, **kw: SimpleNamespace(status_code=200, json=lambda: {"path": "opinion/x.pdf"}))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_opinion", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO

    def test_sin_efirma_NO_cae_a_archivo(self, gw, monkeypatch):
        """A diferencia de la CSF, la Opinión 32-D nunca usa una copia vieja: es
        una foto de cumplimiento puntual y una vieja podría engañar."""
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": [], "efirma_lista": False})
        llamada = {"hecha": False}

        def _archivada_no_deberia_llamarse(base, h, rfc):
            llamada["hecha"] = True
            return ("no-debe-usarse.pdf", None)

        monkeypatch.setattr(gw, "_csf_archivada", _archivada_no_deberia_llamarse)
        resultado = _call(gw, "descargar_opinion", {"rfc": RFC})
        assert len(resultado) == 1
        assert isinstance(resultado[0], TextContent)
        assert not llamada["hecha"]


class TestDescargarZipCfdis:
    def test_lista_se_adjunta(self, gw, monkeypatch):
        def _fake_get_solicitudes(url, headers=None, timeout=None):
            return SimpleNamespace(status_code=200, json=lambda: {
                "solicitudes": [{"id_solicitud": "sid-1", "ruta_descarga": "cfdi/sid-1.zip"}]
            })
        monkeypatch.setattr(gw.requests, "get", _fake_get_solicitudes)
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: ZIP_FALSO if zip_ else (_ for _ in ()).throw(AssertionError("debe pedir zip_=True")))

        resultado = _call(gw, "descargar_zip_cfdis", {"rfc": RFC, "id_solicitud": "sid-1"})
        assert len(resultado) == 2
        recurso = resultado[1]
        assert recurso.resource.mimeType == "application/zip"
        assert base64.b64decode(recurso.resource.blob) == ZIP_FALSO

    def test_no_lista_todavia(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, timeout=None: SimpleNamespace(status_code=200, json=lambda: {"solicitudes": []}))
        resultado = _call(gw, "descargar_zip_cfdis", {"rfc": RFC, "id_solicitud": "sid-nope"})
        assert len(resultado) == 1
        assert "estado_solicitud" in resultado[0].text

    def test_zip_gigante_cae_al_link(self, gw, monkeypatch):
        def _fake_get_solicitudes(url, headers=None, timeout=None):
            return SimpleNamespace(status_code=200, json=lambda: {
                "solicitudes": [{"id_solicitud": "sid-grande", "ruta": "cfdi/grande.zip"}]
            })
        gigante = b"0" * (21 * 1024 * 1024)
        monkeypatch.setattr(gw.requests, "get", _fake_get_solicitudes)
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: gigante)

        resultado = _call(gw, "descargar_zip_cfdis", {"rfc": RFC, "id_solicitud": "sid-grande"})
        assert len(resultado) == 1
        assert "MB" in resultado[0].text
        assert "X-Api-Key" in resultado[0].text


class TestExcelCfdis:
    def test_se_adjunta(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, params=None, timeout=None: SimpleNamespace(status_code=200, content=XLSX_FALSO))
        resultado = _call(gw, "excel_cfdis", {"rfc": RFC})
        assert len(resultado) == 2
        recurso = resultado[1]
        assert "spreadsheet" in recurso.resource.mimeType
        assert base64.b64decode(recurso.resource.blob) == XLSX_FALSO

    def test_csv_usa_mime_csv(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, params=None, timeout=None: SimpleNamespace(status_code=200, content=b"a,b,c"))
        resultado = _call(gw, "excel_cfdis", {"rfc": RFC, "formato": "csv"})
        assert resultado[1].resource.mimeType == "text/csv"

    def test_error_del_procesador_es_solo_texto(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, params=None, timeout=None: SimpleNamespace(status_code=502, json=lambda: {"detail": "sin datos procesados"}))
        resultado = _call(gw, "excel_cfdis", {"rfc": RFC})
        assert len(resultado) == 1
        assert "sin datos procesados" in resultado[0].text

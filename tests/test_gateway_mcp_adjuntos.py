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
from datetime import datetime, timedelta
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
    previos = {k: os.environ.get(k) for k in ("OAUTH_DB_PATH", "EXIGIR_LICENCIA", "SAT_DM_MASTER_KEY")}
    os.environ["OAUTH_DB_PATH"] = str(tmp_path_factory.mktemp("oauth") / "oauth.db")
    os.environ["EXIGIR_LICENCIA"] = "0"
    os.environ["SAT_DM_MASTER_KEY"] = base64.b64encode(b"0" * 32).decode()  # firma de enlaces
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


def _hace_dias(n: int) -> str:
    return (datetime.now() - timedelta(days=n)).isoformat(timespec="seconds")


def _sin_archivada(gw, monkeypatch):
    monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": (None, None))


def _post_prohibido(gw, monkeypatch):
    """El portal del SAT NO debe tocarse cuando la copia reciente basta."""
    def _explota(url, **kw):
        raise AssertionError("no debía generar una nueva (requests.post llamado)")
    monkeypatch.setattr(gw.requests, "post", _explota)


class TestDescargarCsf:
    def test_generada_ahora_se_adjunta(self, gw, monkeypatch):
        """El agente responde {"ok": True, "archivo": ruta} — la forma REAL de
        routers/portal.py (el gateway buscaba path/ruta y nunca la encontraba)."""
        _sin_archivada(gw, monkeypatch)
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": ["fiel"], "efirma_lista": True})
        monkeypatch.setattr(gw.requests, "post", lambda url, **kw: SimpleNamespace(status_code=200, json=lambda: {"ok": True, "archivo": "constancia/x.pdf"}))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "copia" not in resultado[0].text  # sin nota: es recién generada
        assert RFC in resultado[0].text
        # Enlace firmado en el texto (para clientes que no pintan el PDF embebido).
        assert "/v1/descargas/firmada?t=" in resultado[0].text

    def test_copia_reciente_se_entrega_al_instante(self, gw, monkeypatch):
        """Copia de ≤90 días → se entrega sin scrapear el portal, declarando la
        antigüedad y cómo pedir una nueva (forzar_nueva)."""
        monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": ("csf/reciente.pdf", _hace_dias(10)))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)
        _post_prohibido(gw, monkeypatch)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "hace 10 días" in resultado[0].text
        assert "forzar_nueva" in resultado[0].text

    def test_forzar_nueva_ignora_la_copia_reciente(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": ("csf/reciente.pdf", _hace_dias(10)))
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": ["fiel"], "efirma_lista": True})
        monkeypatch.setattr(gw.requests, "post", lambda url, **kw: SimpleNamespace(status_code=200, json=lambda: {"ok": True, "archivo": "constancia/nueva.pdf"}))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC, "forzar_nueva": True})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "forzar_nueva" not in resultado[0].text  # recién generada, sin nota

    def test_copia_vieja_no_cuenta_como_reciente(self, gw, monkeypatch):
        """>90 días → se genera una nueva (la copia solo queda como fallback)."""
        monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": ("csf/vieja.pdf", _hace_dias(197)))
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": ["fiel"], "efirma_lista": True})
        monkeypatch.setattr(gw.requests, "post", lambda url, **kw: SimpleNamespace(status_code=200, json=lambda: {"ok": True, "archivo": "constancia/nueva.pdf"}))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "copia" not in resultado[0].text

    def test_sin_efirma_cae_a_la_copia_archivada(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": [], "efirma_lista": False})
        monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": ("archivo/vieja.pdf", "2026-01-05T00:00:00"))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "2026-01-05" in resultado[0].text
        assert "archivo" in resultado[0].text

    def test_sin_efirma_ni_archivo_solo_texto(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": [], "efirma_lista": False})
        _sin_archivada(gw, monkeypatch)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert len(resultado) == 1
        assert isinstance(resultado[0], TextContent)
        assert "e.firma" in resultado[0].text

    def test_efirma_invalida_409_cae_a_archivo(self, gw, monkeypatch):
        def _activar(base, h, rfc):
            raise HTTPException(status_code=409, detail="La e.firma no es válida.")
        monkeypatch.setattr(gw, "_activar_empresa", _activar)
        monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": ("archivo/vieja.pdf", None))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO

    def test_empresa_inexistente_sin_archivo_pasa_el_detalle(self, gw, monkeypatch):
        def _activar(base, h, rfc):
            raise HTTPException(status_code=404, detail=f"La empresa {rfc} no existe.")
        monkeypatch.setattr(gw, "_activar_empresa", _activar)
        _sin_archivada(gw, monkeypatch)

        resultado = _call(gw, "descargar_csf", {"rfc": RFC})
        assert len(resultado) == 1
        assert "no existe" in resultado[0].text


class TestDescargarOpinion:
    def test_generada_se_adjunta(self, gw, monkeypatch):
        _sin_archivada(gw, monkeypatch)
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": ["fiel"], "efirma_lista": True})
        monkeypatch.setattr(gw.requests, "post", lambda url, **kw: SimpleNamespace(status_code=200, json=lambda: {"ok": True, "archivo": "opinion/x.pdf"}))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)

        resultado = _call(gw, "descargar_opinion", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO

    def test_copia_dentro_de_30_dias_al_instante(self, gw, monkeypatch):
        monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": ("op/reciente.pdf", _hace_dias(7)))
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: PDF_FALSO)
        _post_prohibido(gw, monkeypatch)

        resultado = _call(gw, "descargar_opinion", {"rfc": RFC})
        assert _blob_pdf(resultado) == PDF_FALSO
        assert "hace 7 días" in resultado[0].text

    def test_copia_fuera_de_30_dias_NO_se_entrega(self, gw, monkeypatch):
        """Una opinión de >30 días no sirve ni como cache ni como fallback: es una
        foto de cumplimiento puntual y una vieja podría engañar."""
        monkeypatch.setattr(gw, "_doc_archivado", lambda base, h, rfc, prefijo="csf": ("op/vieja.pdf", _hace_dias(45)))
        monkeypatch.setattr(gw, "_activar_empresa", lambda base, h, rfc: {"metodos": [], "efirma_lista": False})

        resultado = _call(gw, "descargar_opinion", {"rfc": RFC})
        assert len(resultado) == 1
        assert isinstance(resultado[0], TextContent)
        assert "e.firma" in resultado[0].text


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

    def test_ruta_desde_el_historial(self, gw, monkeypatch):
        """update_solicitud NUNCA persiste la ruta — la fuente real es el historial
        (el poller registra "Descarga WS · solicitud {id[:8]}…" con la ruta)."""
        def _fake_get(url, headers=None, timeout=None):
            if url.endswith("/historial"):
                return SimpleNamespace(status_code=200, json=lambda: {"descargas": [
                    {"canal": "portal", "descripcion": "CSF", "ruta": "no/es.zip"},
                    {"canal": "ws", "descripcion": "Descarga WS · solicitud abcd1234… (automática)", "ruta": "cfdi/ws.zip"},
                ]})
            return SimpleNamespace(status_code=200, json=lambda: {
                "solicitudes": [{"id_solicitud": "abcd1234-5678", "estado": "descargada"}]  # sin ruta
            })
        monkeypatch.setattr(gw.requests, "get", _fake_get)
        monkeypatch.setattr(gw, "_bytes_de_agente", lambda base, h, ruta, zip_=False: ZIP_FALSO if ruta == "cfdi/ws.zip" and zip_ else b"")

        resultado = _call(gw, "descargar_zip_cfdis", {"rfc": RFC, "id_solicitud": "abcd1234-5678"})
        assert len(resultado) == 2
        assert base64.b64decode(resultado[1].resource.blob) == ZIP_FALSO

    def test_no_lista_todavia(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, timeout=None: SimpleNamespace(status_code=200, json=lambda: {"solicitudes": [], "descargas": []}))
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
        assert len(resultado) == 1  # sin blob: solo el enlace firmado
        assert "MB" in resultado[0].text
        assert "/v1/descargas/firmada?t=" in resultado[0].text
        assert "X-Api-Key" not in resultado[0].text  # el enlace ya NO necesita API key


class TestExcelCfdis:
    def test_se_adjunta(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, params=None, timeout=None: SimpleNamespace(status_code=200, content=XLSX_FALSO))
        resultado = _call(gw, "excel_cfdis", {"rfc": RFC})
        assert len(resultado) == 2
        recurso = resultado[1]
        assert "spreadsheet" in recurso.resource.mimeType
        assert base64.b64decode(recurso.resource.blob) == XLSX_FALSO
        assert "/v1/descargas/firmada?t=" in resultado[0].text  # enlace de export firmado

    def test_csv_usa_mime_csv(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, params=None, timeout=None: SimpleNamespace(status_code=200, content=b"a,b,c"))
        resultado = _call(gw, "excel_cfdis", {"rfc": RFC, "formato": "csv"})
        assert resultado[1].resource.mimeType == "text/csv"

    def test_error_del_procesador_es_solo_texto(self, gw, monkeypatch):
        monkeypatch.setattr(gw.requests, "get", lambda url, headers=None, params=None, timeout=None: SimpleNamespace(status_code=502, json=lambda: {"detail": "sin datos procesados"}))
        resultado = _call(gw, "excel_cfdis", {"rfc": RFC})
        assert len(resultado) == 1
        assert "sin datos procesados" in resultado[0].text

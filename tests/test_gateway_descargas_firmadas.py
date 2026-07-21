"""Enlaces de descarga firmados del gateway (deploy/gateway/main.py).

Los emiten las tools MCP para que el usuario baje el PDF/ZIP/Excel en su
navegador SIN API key, cuando su cliente no renderiza el recurso embebido
(claude.ai web hoy: "Resources of type 'application/pdf' are not currently
supported"). El token HMAC lleva su propia autorización (user_id + qué bajar +
expiración) y no se puede falsificar sin la master key."""

import base64
import importlib
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("mcp")
from fastapi.testclient import TestClient  # noqa: E402

GATEWAY_DIR = Path(__file__).parent.parent / "deploy" / "gateway"
RUTA = "constancia/CAMY/x.pdf"
USER = "user-firma-1"


@pytest.fixture(scope="module")
def gw(tmp_path_factory):
    previos = {k: os.environ.get(k) for k in ("OAUTH_DB_PATH", "EXIGIR_LICENCIA", "SAT_DM_MASTER_KEY")}
    os.environ["OAUTH_DB_PATH"] = str(tmp_path_factory.mktemp("oauth") / "oauth.db")
    os.environ["EXIGIR_LICENCIA"] = "0"
    os.environ["SAT_DM_MASTER_KEY"] = base64.b64encode(b"1" * 32).decode()
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


@pytest.fixture(scope="module")
def client(gw):
    with TestClient(gw.app, base_url="http://localhost") as c:
        yield c


class TestToken:
    def test_ida_y_vuelta_archivo(self, gw):
        tok = gw._firmar_token({"u": USER, "r": RUTA, "z": 0}, 9999999999)
        datos = gw._verificar_descarga(tok, 1000)
        assert datos["u"] == USER and datos["r"] == RUTA and not datos.get("x")

    def test_ida_y_vuelta_export(self, gw):
        tok = gw._firmar_token({"u": USER, "x": {"rfc": "CAMY", "formato": "xlsx"}}, 9999999999)
        datos = gw._verificar_descarga(tok, 1000)
        assert datos["x"]["formato"] == "xlsx"

    def test_expirado(self, gw):
        tok = gw._firmar_token({"u": USER, "r": RUTA}, 500)
        assert gw._verificar_descarga(tok, 1000) is None  # exp 500 < ahora 1000

    def test_firma_alterada(self, gw):
        tok = gw._firmar_token({"u": USER, "r": RUTA}, 9999999999)
        payload, _ = tok.split(".", 1)
        # payload manipulado (otra ruta) con una firma cualquiera → inválido.
        falso = gw._b64u(b'{"u":"otro","r":"secreto/ajeno.pdf","e":9999999999}')
        assert gw._verificar_descarga(f"{falso}.{payload}", 1000) is None

    def test_basura(self, gw):
        assert gw._verificar_descarga("no-es-un-token", 1000) is None
        assert gw._verificar_descarga("", 1000) is None


class TestEndpoint:
    def test_archivo_streamea_del_agente(self, gw, client, monkeypatch):
        monkeypatch.setattr(gw, "_asegurar_agente", lambda uid: ("http://ag:8787", {"X-Agent-Token": "t"}))
        monkeypatch.setattr(gw, "_descargar_de_agente",
                            lambda base, h, ruta, zip_: gw.Response(content=b"PDF:" + ruta.encode(), media_type="application/pdf"))
        tok = gw._firmar_token({"u": USER, "r": RUTA, "z": 0}, 9999999999)

        r = client.get(f"/v1/descargas/firmada?t={tok}")
        assert r.status_code == 200
        assert r.content == b"PDF:" + RUTA.encode()

    def test_export_reejecuta_la_consulta(self, gw, client, monkeypatch):
        monkeypatch.setattr(gw, "_asegurar_agente", lambda uid: ("http://ag:8787", {"X-Agent-Token": "t"}))
        vistos = {}

        def _fake_get(url, headers=None, params=None, timeout=None, stream=None):
            vistos["url"] = url
            vistos["params"] = params
            return SimpleNamespace(status_code=200, headers={"content-type": "text/csv"},
                                   iter_content=lambda chunk_size: iter([b"a,b,c"]))
        monkeypatch.setattr(gw.requests, "get", _fake_get)
        tok = gw._firmar_token({"u": USER, "x": {"rfc": "CAMY", "formato": "csv"}}, 9999999999)

        r = client.get(f"/v1/descargas/firmada?t={tok}")
        assert r.status_code == 200
        assert r.content == b"a,b,c"
        assert vistos["url"].endswith("/procesador/cfdi/exportar")
        assert vistos["params"] == {"rfc": "CAMY", "formato": "csv"}

    def test_token_invalido_403_sin_tocar_al_agente(self, gw, client, monkeypatch):
        def _no_deberia(uid):
            raise AssertionError("no debía derivar el agente con un token inválido")
        monkeypatch.setattr(gw, "_asegurar_agente", _no_deberia)
        r = client.get("/v1/descargas/firmada?t=basura.basura")
        assert r.status_code == 403

    def test_sin_token_403(self, gw, client):
        r = client.get("/v1/descargas/firmada")
        assert r.status_code == 403

    def test_no_aparece_en_el_openapi(self, client):
        """El endpoint firmado NO se documenta (include_in_schema=False)."""
        paths = client.get("/v1/openapi.json").json()["paths"]
        assert "/v1/descargas/firmada" not in paths

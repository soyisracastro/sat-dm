"""OAuth 2.1 del gateway (deploy/gateway/oauth.py): descubrimiento, DCR,
authorize (login + consentimiento), token con PKCE, rotación de refresh y el
middleware de /mcp aceptando el Bearer OAuth."""

import base64
import hashlib
import importlib
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("mcp")
from fastapi.testclient import TestClient  # noqa: E402

GATEWAY_DIR = Path(__file__).parent.parent / "deploy" / "gateway"

VERIFIER = "v" * 60
CHALLENGE = (
    base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest())
    .rstrip(b"=")
    .decode()
)
REDIRECT = "https://claude.ai/api/mcp/auth_callback"


@pytest.fixture(scope="module")
def gw(tmp_path_factory):
    """Importa el gateway con SQLite en tmp y sin validación de licencia."""
    previos = {
        k: os.environ.get(k) for k in ("OAUTH_DB_PATH", "EXIGIR_LICENCIA")
    }
    os.environ["OAUTH_DB_PATH"] = str(tmp_path_factory.mktemp("oauth") / "oauth.db")
    os.environ["EXIGIR_LICENCIA"] = "0"
    sys.path.insert(0, str(GATEWAY_DIR))
    for mod in ("main", "oauth"):
        sys.modules.pop(mod, None)
    oauth_mod = importlib.import_module("oauth")
    main_mod = importlib.import_module("main")
    yield main_mod, oauth_mod
    sys.path.remove(str(GATEWAY_DIR))
    for mod in ("main", "oauth"):
        sys.modules.pop(mod, None)
    for k, v in previos.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


# Alcance módulo: el session manager del SDK MCP solo puede arrancar una vez
# por instancia, así que el lifespan se abre una sola vez para todos los tests.
@pytest.fixture(scope="module")
def client(gw):
    main_mod, _ = gw
    # base_url localhost: el Host queda dentro de los allowed_hosts del MCP.
    with TestClient(main_mod.app, base_url="http://localhost") as c:
        yield c


@pytest.fixture
def gotrue_ok(gw, monkeypatch):
    _, oauth_mod = gw
    monkeypatch.setattr(
        oauth_mod,
        "_gotrue_post",
        lambda path, payload, params=None: {
            "access_token": "sesion-supabase",
            "user": {"id": "user-oauth-1", "email": "prueba@todoconta.com"},
        },
    )


def _registrar(client) -> str:
    r = client.post(
        "/oauth/register",
        json={"redirect_uris": [REDIRECT], "client_name": "Claude"},
    )
    assert r.status_code == 201
    body = r.json()
    assert body["client_id"].startswith("tcc_")
    assert body["token_endpoint_auth_method"] == "none"
    return body["client_id"]


def _autorizar(client, client_id: str) -> str:
    """Login + consentimiento → devuelve el authorization code."""
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": REDIRECT,
        "state": "estado-xyz",
        "code_challenge": CHALLENGE,
        "code_challenge_method": "S256",
        "resource": "https://agente.todoconta.com/mcp",
    }
    r = client.get("/oauth/authorize", params=params)
    assert r.status_code == 200
    assert "Claude" in r.text and "Autorizar" in r.text
    # OTP-first: el código al correo es el modo default; la contraseña, la alterna.
    assert "var conOtp = true" in r.text

    r = client.post(
        "/oauth/authorize",
        data={**params, "email": "prueba@todoconta.com", "password": "secreta"},
        follow_redirects=False,
    )
    assert r.status_code == 303
    destino = urlparse(r.headers["location"])
    q = parse_qs(destino.query)
    assert destino.netloc == "claude.ai"
    assert q["state"] == ["estado-xyz"]
    return q["code"][0]


def _canjear(client, client_id: str, code: str, verifier: str = VERIFIER):
    return client.post(
        "/oauth/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
        },
    )


def test_descubrimiento(client):
    r = client.get("/.well-known/oauth-protected-resource")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"].endswith("/mcp")
    assert body["authorization_servers"]
    # Variante con el path del recurso (los conectores prueban ambas).
    assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 200

    r = client.get("/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    meta = r.json()
    assert meta["code_challenge_methods_supported"] == ["S256"]
    assert meta["grant_types_supported"] == ["authorization_code", "refresh_token"]
    assert meta["authorization_endpoint"].endswith("/oauth/authorize")
    assert meta["registration_endpoint"].endswith("/oauth/register")
    # CORS para clientes de navegador (Inspector).
    assert r.headers.get("access-control-allow-origin") == "*"


def test_registro_rechaza_redirect_insegura(client):
    r = client.post("/oauth/register", json={"redirect_uris": ["http://evil.com/cb"]})
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_redirect_uri"
    # http sí se permite en localhost (Inspector, desarrollo).
    r = client.post("/oauth/register", json={"redirect_uris": ["http://localhost:6274/cb"]})
    assert r.status_code == 201


def test_authorize_cliente_desconocido_no_redirige(client):
    r = client.get(
        "/oauth/authorize",
        params={"response_type": "code", "client_id": "tcc_nope", "redirect_uri": REDIRECT},
        follow_redirects=False,
    )
    assert r.status_code == 400  # página de error, nunca redirect


def test_authorize_sin_pkce_redirige_con_error(client):
    client_id = _registrar(client)
    r = client.get(
        "/oauth/authorize",
        params={"response_type": "code", "client_id": client_id, "redirect_uri": REDIRECT, "state": "s1"},
        follow_redirects=False,
    )
    assert r.status_code == 302
    q = parse_qs(urlparse(r.headers["location"]).query)
    assert q["error"] == ["invalid_request"]
    assert q["state"] == ["s1"]


def test_mcp_sin_auth_401_con_www_authenticate(client):
    r = client.post("/mcp", json={})
    assert r.status_code == 401
    assert 'resource_metadata="' in r.headers.get("www-authenticate", "")


def test_flujo_completo(client, gotrue_ok):
    client_id = _registrar(client)
    code = _autorizar(client, client_id)

    r = _canjear(client, client_id, code)
    assert r.status_code == 200
    tokens = r.json()
    assert tokens["token_type"] == "Bearer"
    assert tokens["access_token"].startswith("mcp_at_")
    assert tokens["refresh_token"].startswith("mcp_rt_")
    assert r.headers["cache-control"] == "no-store"

    # Con el access token el middleware de /mcp deja pasar (lo que responda el
    # transporte MCP a un POST mínimo no importa: basta con que no sea 401).
    r = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        headers={
            "Authorization": f"Bearer {tokens['access_token']}",
            "Accept": "application/json, text/event-stream",
        },
    )
    assert r.status_code != 401

    # PKCE incorrecto en un canje nuevo → invalid_grant.
    code2 = _autorizar(client, client_id)
    r = _canjear(client, client_id, code2, verifier="w" * 60)
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_grant"


def test_code_replay_revoca_familia(client, gotrue_ok):
    client_id = _registrar(client)
    code = _autorizar(client, client_id)
    access = _canjear(client, client_id, code).json()["access_token"]

    r = _canjear(client, client_id, code)  # replay
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_grant"
    # Los tokens que salieron de ese code quedan revocados.
    r = client.post("/mcp", json={}, headers={"Authorization": f"Bearer {access}"})
    assert r.status_code == 401


def test_refresh_rotativo_y_replay(client, gotrue_ok):
    client_id = _registrar(client)
    code = _autorizar(client, client_id)
    tokens = _canjear(client, client_id, code).json()

    r = client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id},
    )
    assert r.status_code == 200
    nuevos = r.json()
    assert nuevos["access_token"] != tokens["access_token"]
    assert nuevos["refresh_token"] != tokens["refresh_token"]

    # Reusar el refresh ya rotado revoca TODA la familia (incluye los nuevos).
    r = client.post(
        "/oauth/token",
        data={"grant_type": "refresh_token", "refresh_token": tokens["refresh_token"], "client_id": client_id},
    )
    assert r.status_code == 400
    assert r.json()["error"] == "invalid_grant"
    r = client.post("/mcp", json={}, headers={"Authorization": f"Bearer {nuevos['access_token']}"})
    assert r.status_code == 401


def test_revoke(client, gotrue_ok):
    client_id = _registrar(client)
    code = _autorizar(client, client_id)
    tokens = _canjear(client, client_id, code).json()
    r = client.post("/oauth/revoke", data={"token": tokens["refresh_token"]})
    assert r.status_code == 200
    r = client.post("/mcp", json={}, headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert r.status_code == 401

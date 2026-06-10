"""
Tests del auth directo contra Supabase (supabase_auth.py) y del refresh de
sesión ante 401 en license_client (antes deslogueaba al usuario aunque el
refresh_token siguiera vigente).

Todo mockeado a nivel requests — nunca se pega a Supabase real.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from sat_descarga.api import license_client, supabase_auth
from sat_descarga.api.license_client import Session
from sat_descarga.api.supabase_auth import SupabaseAuthError


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resp(status: int, payload: dict | None = None) -> MagicMock:
    r = MagicMock()
    r.status_code = status
    r.json.return_value = payload if payload is not None else {}
    r.text = json.dumps(payload or {})
    return r


def _payload_sesion(access="jwt-nuevo", refresh="refresh-nuevo") -> dict:
    return {
        "access_token": access,
        "refresh_token": refresh,
        "user": {"id": "user-1", "email": "test@todoconta.com"},
    }


SESION = Session(
    access_token="jwt-viejo",
    refresh_token="refresh-viejo",
    user_id="user-1",
    email="test@todoconta.com",
)


# ---------------------------------------------------------------------------
# supabase_auth — flujos y traducción de errores
# ---------------------------------------------------------------------------


class TestLoginPassword:

    def test_happy_path_construye_session(self):
        with patch.object(supabase_auth.requests, "post",
                          return_value=_resp(200, _payload_sesion())) as mock_post:
            s = supabase_auth.login_password("test@todoconta.com", "secreta123")
        assert s.access_token == "jwt-nuevo"
        assert s.refresh_token == "refresh-nuevo"
        assert s.user_id == "user-1"
        assert s.email == "test@todoconta.com"
        kwargs = mock_post.call_args.kwargs
        assert kwargs["params"] == {"grant_type": "password"}
        assert kwargs["headers"]["apikey"] == supabase_auth.SUPABASE_ANON_KEY

    def test_credenciales_invalidas_mensaje_espanol(self):
        # El endpoint /token usa formato OAuth {error, error_description}.
        payload = {"error": "invalid_grant", "error_description": "Invalid login credentials"}
        with patch.object(supabase_auth.requests, "post", return_value=_resp(400, payload)):
            with pytest.raises(SupabaseAuthError) as exc:
                supabase_auth.login_password("test@todoconta.com", "mala")
        assert "incorrectos" in exc.value.mensaje
        assert exc.value.error_code == "invalid_credentials"

    def test_error_de_red_es_502(self):
        with patch.object(supabase_auth.requests, "post",
                          side_effect=supabase_auth.requests.ConnectionError("boom")):
            with pytest.raises(SupabaseAuthError) as exc:
                supabase_auth.login_password("a@b.mx", "x")
        assert exc.value.status == 502


class TestOtp:

    def test_send_login_no_crea_usuario(self):
        with patch.object(supabase_auth.requests, "post",
                          return_value=_resp(200, {})) as mock_post:
            supabase_auth.otp_send("test@todoconta.com")
        body = mock_post.call_args.kwargs["json"]
        assert body == {"email": "test@todoconta.com", "create_user": False}

    def test_send_registro_lleva_nombre(self):
        with patch.object(supabase_auth.requests, "post",
                          return_value=_resp(200, {})) as mock_post:
            supabase_auth.otp_send("n@d.mx", crear_cuenta=True, nombre="Daniela Ortega")
        body = mock_post.call_args.kwargs["json"]
        assert body["create_user"] is True
        assert body["data"] == {"full_name": "Daniela Ortega"}

    def test_send_sin_cuenta_traduce_otp_disabled(self):
        payload = {"code": 422, "error_code": "otp_disabled", "msg": "Signups not allowed for otp"}
        with patch.object(supabase_auth.requests, "post", return_value=_resp(422, payload)):
            with pytest.raises(SupabaseAuthError) as exc:
                supabase_auth.otp_send("nadie@d.mx")
        assert "No encontramos una cuenta" in exc.value.mensaje

    def test_verify_devuelve_session(self):
        with patch.object(supabase_auth.requests, "post",
                          return_value=_resp(200, _payload_sesion())) as mock_post:
            s = supabase_auth.otp_verify("test@todoconta.com", "123456")
        assert s.access_token == "jwt-nuevo"
        assert mock_post.call_args.kwargs["json"]["type"] == "email"

    def test_verify_codigo_expirado(self):
        payload = {"code": 403, "error_code": "otp_expired", "msg": "Token has expired or is invalid"}
        with patch.object(supabase_auth.requests, "post", return_value=_resp(403, payload)):
            with pytest.raises(SupabaseAuthError) as exc:
                supabase_auth.otp_verify("test@todoconta.com", "000000")
        assert "expiró" in exc.value.mensaje


class TestSignup:

    def test_con_confirmacion_pendiente(self):
        # Confirmación de email activada: GoTrue no devuelve access_token.
        payload = {"id": "user-2", "email": "n@d.mx", "confirmation_sent_at": "2026-06-10T00:00:00Z"}
        with patch.object(supabase_auth.requests, "post", return_value=_resp(200, payload)):
            session, requiere = supabase_auth.signup("n@d.mx", "secreta123", nombre="Nuevo")
        assert session is None
        assert requiere is True

    def test_con_autoconfirm_devuelve_session(self):
        with patch.object(supabase_auth.requests, "post",
                          return_value=_resp(200, _payload_sesion())):
            session, requiere = supabase_auth.signup("n@d.mx", "secreta123")
        assert session is not None
        assert requiere is False

    def test_password_debil(self):
        payload = {"code": 422, "error_code": "weak_password", "msg": "Password should be at least 8 characters"}
        with patch.object(supabase_auth.requests, "post", return_value=_resp(422, payload)):
            with pytest.raises(SupabaseAuthError) as exc:
                supabase_auth.signup("n@d.mx", "123")
        assert "8 caracteres" in exc.value.mensaje


# ---------------------------------------------------------------------------
# license_client — refresh ante 401 (el fix del deslogueo en vivo)
# ---------------------------------------------------------------------------


class TestRefreshAnte401:

    def test_401_con_refresh_exitoso_no_desloguea(self):
        license_client.save_session(SESION)
        licencia = {"authenticated": True, "is_founder": True}

        def fetch(session):
            if session.access_token == "jwt-viejo":
                raise PermissionError("Bearer inválido o expirado")
            return licencia

        with patch.object(license_client, "fetch_license_remote", side_effect=fetch), \
             patch.object(supabase_auth, "refresh",
                          return_value=Session("jwt-nuevo", "refresh-nuevo", "user-1", "test@todoconta.com")):
            status = license_client.get_license_status(force_refresh=True)

        assert status["is_founder"] is True
        # La sesión renovada quedó persistida en el keyring.
        guardada = license_client.load_session()
        assert guardada.access_token == "jwt-nuevo"
        license_client.clear_session()

    def test_401_sin_refresh_posible_desloguea(self):
        license_client.save_session(Session("jwt-viejo", None, "user-1", None))
        with patch.object(license_client, "fetch_license_remote",
                          side_effect=PermissionError("401")):
            status = license_client.get_license_status(force_refresh=True)
        assert status == {"authenticated": False, "reason": "session_expired"}
        assert license_client.load_session() is None

    def test_401_persistente_tras_refresh_desloguea(self):
        license_client.save_session(SESION)
        with patch.object(license_client, "fetch_license_remote",
                          side_effect=PermissionError("401")), \
             patch.object(supabase_auth, "refresh",
                          return_value=Session("jwt-nuevo", "refresh-nuevo", "user-1", None)):
            status = license_client.get_license_status(force_refresh=True)
        assert status["authenticated"] is False
        assert license_client.load_session() is None

    def test_refresh_preserva_identidad_si_payload_incompleto(self):
        license_client.save_session(SESION)
        with patch.object(supabase_auth, "refresh",
                          return_value=Session("jwt-nuevo", "refresh-nuevo", "", None)):
            nueva = license_client.try_refresh_session(SESION)
        assert nueva.user_id == "user-1"
        assert nueva.email == "test@todoconta.com"
        license_client.clear_session()


# ---------------------------------------------------------------------------
# Endpoints /auth/* del agente (FastAPI)
# ---------------------------------------------------------------------------

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(server, "_AGENT_TOKEN", "")
    return TestClient(server.app)


class TestEndpointsAuth:

    def test_login_password_guarda_sesion(self, client):
        with patch.object(supabase_auth.requests, "post",
                          return_value=_resp(200, _payload_sesion())):
            r = client.post("/auth/login-password",
                            json={"email": "test@todoconta.com", "password": "secreta123"})
        assert r.status_code == 200
        assert r.json()["ok"] is True
        assert r.json()["user"]["email"] == "test@todoconta.com"
        assert license_client.load_session().access_token == "jwt-nuevo"
        license_client.clear_session()

    def test_login_password_credenciales_malas_401(self, client):
        payload = {"error": "invalid_grant", "error_description": "Invalid login credentials"}
        with patch.object(supabase_auth.requests, "post", return_value=_resp(400, payload)):
            r = client.post("/auth/login-password",
                            json={"email": "a@b.mx", "password": "mala"})
        assert r.status_code == 400
        assert "incorrectos" in r.json()["detail"]

    def test_otp_verify_signup_pasa_tipo(self, client):
        with patch.object(supabase_auth.requests, "post",
                          return_value=_resp(200, _payload_sesion())) as mock_post:
            r = client.post("/auth/otp-verify",
                            json={"email": "n@d.mx", "token": "123456", "tipo": "signup"})
        assert r.status_code == 200
        assert mock_post.call_args.kwargs["json"]["type"] == "signup"
        license_client.clear_session()

    def test_signup_requiere_confirmacion(self, client):
        payload = {"id": "u", "email": "n@d.mx", "confirmation_sent_at": "2026-06-10T00:00:00Z"}
        with patch.object(supabase_auth.requests, "post", return_value=_resp(200, payload)):
            r = client.post("/auth/signup",
                            json={"email": "n@d.mx", "password": "secreta123", "nombre": "Nuevo"})
        assert r.status_code == 200
        assert r.json() == {"ok": True, "requiere_confirmacion": True}

"""Backend de secretos en archivo cifrado (modo hosted) + dispatch de core/secretos."""

import base64

import pytest

pytest.importorskip("cryptography")

from sat_descarga.cli import config_store  # noqa: E402
from sat_descarga.core import secretos, secretos_archivo  # noqa: E402

CLAVE = base64.b64encode(b"0" * 32).decode()
RFC = "XAXX010101000"


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setenv("SAT_DM_SECRETS_KEY", CLAVE)


def test_roundtrip_y_no_toca_keyring(tmp_path):
    secretos.guardar(RFC, secretos.FIEL, "hunter2")
    assert secretos.obtener(RFC, secretos.FIEL) == "hunter2"

    # Con la env presente, NADA cae al keyring (backend en memoria de conftest).
    import keyring

    assert keyring.get_password(secretos.SERVICE, f"fiel:{RFC}") is None

    secretos.borrar(RFC, secretos.FIEL)
    assert secretos.obtener(RFC, secretos.FIEL) is None


def test_archivo_cifrado_sin_texto_plano(tmp_path):
    secretos.guardar(RFC, secretos.CIEC, "supersecreta")
    enc = tmp_path / ".sat-descarga" / "secretos.enc"
    assert enc.exists()
    blob = enc.read_bytes()
    assert b"supersecreta" not in blob
    assert RFC.encode() not in blob


def test_varios_secretos_conviven():
    secretos.guardar(RFC, secretos.FIEL, "clave-fiel")
    secretos.guardar(RFC, secretos.CIEC, "clave-ciec")
    secretos.guardar("ABC010101AAA", secretos.FIEL, "otra")
    assert secretos.obtener(RFC, secretos.FIEL) == "clave-fiel"
    assert secretos.obtener(RFC, secretos.CIEC) == "clave-ciec"
    assert secretos.obtener("ABC010101AAA", secretos.FIEL) == "otra"
    # Borrar uno no arrastra a los demás.
    secretos.borrar(RFC, secretos.CIEC)
    assert secretos.obtener(RFC, secretos.CIEC) is None
    assert secretos.obtener(RFC, secretos.FIEL) == "clave-fiel"


def test_clave_incorrecta(monkeypatch):
    secretos.guardar(RFC, secretos.FIEL, "hunter2")
    monkeypatch.setenv("SAT_DM_SECRETS_KEY", base64.b64encode(b"1" * 32).decode())
    # obtener() degrada a None con warning (mismo contrato que un keyring caído)…
    assert secretos.obtener(RFC, secretos.FIEL) is None
    # …pero el backend crudo truena con un mensaje que da la pista.
    with pytest.raises(RuntimeError, match="SAT_DM_SECRETS_KEY"):
        secretos_archivo.obtener(secretos.SERVICE, f"fiel:{RFC}")


def test_clave_invalida(monkeypatch):
    monkeypatch.setenv("SAT_DM_SECRETS_KEY", "no-es-base64!!")
    with pytest.raises(RuntimeError):
        secretos.guardar(RFC, secretos.FIEL, "x")

    monkeypatch.setenv("SAT_DM_SECRETS_KEY", base64.b64encode(b"corta").decode())
    with pytest.raises(RuntimeError, match="32 bytes"):
        secretos.guardar(RFC, secretos.FIEL, "x")


def test_archivo_truncado_se_trata_como_vacio(tmp_path):
    secretos.guardar(RFC, secretos.FIEL, "hunter2")
    enc = tmp_path / ".sat-descarga" / "secretos.enc"
    enc.write_bytes(b"x" * 5)  # menos que el nonce
    assert secretos.obtener(RFC, secretos.FIEL) is None


def test_sin_env_usa_keyring(monkeypatch):
    monkeypatch.delenv("SAT_DM_SECRETS_KEY")
    secretos.guardar(RFC, secretos.FIEL, "hunter2")

    import keyring

    assert keyring.get_password(secretos.SERVICE, f"fiel:{RFC}") == "hunter2"
    assert secretos.obtener(RFC, secretos.FIEL) == "hunter2"


def test_sesion_de_license_client_en_archivo(tmp_path, monkeypatch):
    """La sesión de Supabase (license_client) también cae al archivo cifrado."""
    from sat_descarga.api import license_client as lc

    # El cache de licencia apunta al CONFIG_DIR real (constante de módulo):
    # se redirige para que clear_session() no toque el disco del dev.
    monkeypatch.setattr(lc, "LICENSE_CACHE_PATH", tmp_path / "license-cache.json")

    lc.save_session(
        lc.Session(access_token="tok", refresh_token="ref", user_id="u1", email="a@b.c")
    )
    s = lc.load_session()
    assert s is not None and s.access_token == "tok" and s.user_id == "u1"

    enc = tmp_path / ".sat-descarga" / "secretos.enc"
    assert enc.exists() and b"tok" not in enc.read_bytes()

    lc.clear_session()
    assert lc.load_session() is None

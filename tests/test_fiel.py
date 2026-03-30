"""Tests para sat_descarga.fiel — carga de e-firma, RFC, firma RSA-SHA1."""

import base64
from datetime import datetime, timezone

import pytest
from sat_descarga.fiel import FIEL


class TestFIELLoad:
    """Carga de certificado y llave privada."""

    def test_carga_exitosa(self, test_cer, test_key, test_password):
        fiel = FIEL(test_cer, test_key, test_password)
        assert fiel.rfc is not None

    def test_password_incorrecto(self, test_cer, test_key):
        with pytest.raises(Exception):
            FIEL(test_cer, test_key, "password_malo")

    def test_archivo_no_existe(self, test_key, test_password):
        with pytest.raises(FileNotFoundError):
            FIEL("no_existe.cer", test_key, test_password)


class TestFIELProperties:
    """Propiedades extraídas del certificado."""

    @pytest.fixture(autouse=True)
    def setup(self, test_cer, test_key, test_password):
        self.fiel = FIEL(test_cer, test_key, test_password)

    def test_rfc_extraido(self, test_rfc):
        assert self.fiel.rfc == test_rfc

    def test_numero_serie_es_decimal(self):
        assert self.fiel.numero_serie.isdigit()

    def test_issuer_dn_no_vacio(self):
        assert len(self.fiel.issuer_dn) > 0

    def test_certificate_b64_es_base64_valido(self):
        decoded = base64.b64decode(self.fiel.certificate_b64)
        assert len(decoded) > 100  # Un cert DER tiene al menos unos cientos de bytes

    def test_not_valid_after_es_futuro(self):
        assert self.fiel.not_valid_after > datetime.now(timezone.utc)

    def test_vigente(self):
        assert self.fiel.vigente is True


class TestFIELSign:
    """Firma RSA-SHA1."""

    @pytest.fixture(autouse=True)
    def setup(self, test_cer, test_key, test_password):
        self.fiel = FIEL(test_cer, test_key, test_password)

    def test_sign_retorna_bytes(self):
        signature = self.fiel.sign(b"datos de prueba")
        assert isinstance(signature, bytes)
        assert len(signature) > 0

    def test_sign_b64_retorna_string(self):
        sig_b64 = self.fiel.sign_b64(b"datos de prueba")
        assert isinstance(sig_b64, str)
        # Verificar que es Base64 válido
        decoded = base64.b64decode(sig_b64)
        assert len(decoded) > 0

    def test_sign_determinista(self):
        """Mismo input produce misma firma."""
        data = b"mismo contenido"
        sig1 = self.fiel.sign(data)
        sig2 = self.fiel.sign(data)
        assert sig1 == sig2

    def test_sign_diferente_para_diferente_input(self):
        sig1 = self.fiel.sign(b"contenido A")
        sig2 = self.fiel.sign(b"contenido B")
        assert sig1 != sig2

    def test_digest_sha1_b64(self):
        digest = self.fiel.digest_sha1_b64(b"hola")
        decoded = base64.b64decode(digest)
        assert len(decoded) == 20  # SHA-1 siempre es 20 bytes

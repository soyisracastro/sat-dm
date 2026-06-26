"""Tests para sat_descarga.core.fiel — carga de e-firma, RFC, firma RSA-SHA1."""

import base64
from datetime import datetime, timezone

import pytest
from sat_descarga.core.fiel import (
    FIEL,
    _rfc_desde_valores,
    _valores_oid_en_der,
    _OID_UNIQUE_ID_DER,
)


def _tlv(tag: int, val: bytes) -> bytes:
    """Codifica un TLV ASN.1 en formato corto (para construir DER de prueba)."""
    return bytes([tag, len(val)]) + val


class TestValoresOidEnDer:
    """Fallback DER para certs cuyo subject cryptography no puede parsear.

    Caso real: nombre del titular con Ñ tipado como T61String con bytes UTF-8 →
    el parser estricto truena al leer el subject, aunque el RFC esté limpio.
    """

    def test_toma_el_ultimo_que_es_el_titular(self):
        # En X.509 el issuer (CA del SAT, RFC SAT970701NN3) va antes del subject
        # (titular). Ambos traen OID 2.5.4.45 → el titular es la última aparición.
        oid = _OID_UNIQUE_ID_DER
        der = (
            b"\x30\x10" + oid + _tlv(0x13, b"SAT970701NN3")      # issuer (PrintableString)
            + b"\x30\x11" + oid + _tlv(0x13, b"CEAT951015IW5")   # subject
        )
        valores = _valores_oid_en_der(der, oid)
        assert valores == [b"SAT970701NN3", b"CEAT951015IW5"]
        # La propiedad rfc toma reversed() → el titular gana.
        assert _rfc_desde_valores(reversed(valores)) == "CEAT951015IW5"

    def test_oid_ausente_devuelve_lista_vacia(self):
        assert _valores_oid_en_der(b"\x30\x03\x02\x01\x00", _OID_UNIQUE_ID_DER) == []


class TestRfcDesdeValores:
    """Extracción del RFC del titular a partir de las cadenas candidatas del cert.

    No requiere un cert real: prueba directo la lógica pura, incluyendo el caso
    `bytes` (cryptography devuelve bytes para el OID 2.5.4.45 cuando el SAT lo
    tipa como BIT STRING) que provocaba "No se pudo extraer el RFC".
    """

    def test_texto_persona_fisica(self):
        assert _rfc_desde_valores(["XAXX010101000"]) == "XAXX010101000"

    def test_texto_persona_moral(self):
        assert _rfc_desde_valores(["SAJ0205248A9"]) == "SAJ0205248A9"

    def test_bytes_persona_fisica(self):
        # La regresión: valor como bytes (BIT STRING) en vez de str.
        assert _rfc_desde_valores([b"CEAT951015IW5"]) == "CEAT951015IW5"

    def test_formato_sat_rfc_diagonal_curp(self):
        # "RFC / CURP" → el titular es el primer token, no la CURP.
        assert (
            _rfc_desde_valores(["EMPR990101AAA / GAXX000101HDFXXX01"])
            == "EMPR990101AAA"
        )

    def test_bytes_con_espacio_inicial_y_separador(self):
        assert (
            _rfc_desde_valores([b" CEAT951015IW5 / GAXX000101HDFXXX01"])
            == "CEAT951015IW5"
        )

    def test_minusculas_se_normalizan(self):
        assert _rfc_desde_valores(["ceat951015iw5"]) == "CEAT951015IW5"

    def test_sin_rfc_devuelve_none(self):
        # El CN (nombre) no debe colarse como RFC.
        assert _rfc_desde_valores(["PRUEBA EMPRESA SA DE CV"]) is None

    def test_orden_de_candidatos(self):
        # Toma el primer candidato válido; ignora el nombre previo sin RFC.
        valores = ["PRUEBA EMPRESA SA DE CV", b"CEAT951015IW5"]
        assert _rfc_desde_valores(valores) == "CEAT951015IW5"

    def test_lista_vacia_devuelve_none(self):
        assert _rfc_desde_valores([]) is None


class TestFIELLoad:
    """Carga de certificado y llave privada."""

    def test_carga_exitosa(self, test_cer, test_key, test_password):
        fiel = FIEL(test_cer, test_key, test_password)
        assert fiel.rfc is not None

    def test_password_incorrecto(self, test_cer, test_key):
        # Rechaza una contraseña incorrecta con un mensaje claro (no el críptico
        # "Unable to load PEM file").
        with pytest.raises(ValueError, match="contraseña de la clave privada"):
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

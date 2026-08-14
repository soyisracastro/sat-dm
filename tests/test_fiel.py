"""Tests para sat_descarga.core.fiel — carga de e-firma, RFC, firma RSA-SHA1."""

import base64
from datetime import datetime, timezone
from pathlib import Path

import pytest
from cryptography import x509
from sat_descarga.core.fiel import (
    FIEL,
    _a_texto,
    _der_desde_pem,
    _rfc_desde_valores,
    _reparar_printablestring_en_der,
    _valores_oid_en_der,
    _OID_COMMON_NAME_DER,
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

    def test_nombre_con_n_se_decodifica(self):
        # El nombre con Ñ viene como T61String (tag 0x14) con el byte 0xD1; debe
        # recuperarse decodificado, no perderse. (`_a_texto` cae a latin-1.)
        cn_oid = bytes([0x06, 0x03, 0x55, 0x04, 0x03])
        nombre_bytes = b"TERESA DE JESUS CEDE\xd1O ALMAZAN"
        der = cn_oid + _tlv(0x14, nombre_bytes)  # 0x14 = T61String
        assert _a_texto(_valores_oid_en_der(der, cn_oid)[-1]) == "TERESA DE JESUS CEDEÑO ALMAZAN"


class TestRepararPrintableString:
    """Certs de la CA vieja del SAT: acentos dentro de un PrintableString.

    `A.C. del Servicio de Administración Tributaria` firma con un
    `unstructuredName = "responsable: Administración Central…"` tipado como
    PrintableString pero con bytes UTF-8. OpenSSL lo tolera; el parser estricto
    de `cryptography` truena con ParseError y el .cer no se podía dar de alta.
    """

    def test_retipa_el_valor_con_acento(self):
        # "Administración" con el 0xC3 0xB3 de la ó, tipado 0x13 (PrintableString).
        der = _OID_COMMON_NAME_DER + _tlv(0x13, b"Administraci\xc3\xb3n")
        reparado = _reparar_printablestring_en_der(der)
        assert reparado is not None
        # Solo cambia el byte del tag: 0x13 (Printable) → 0x0C (UTF8String).
        assert reparado[len(_OID_COMMON_NAME_DER)] == 0x0C
        assert len(reparado) == len(der)
        assert reparado[len(_OID_COMMON_NAME_DER) + 1 :] == der[len(_OID_COMMON_NAME_DER) + 1 :]

    def test_no_toca_un_printablestring_limpio(self):
        der = _OID_UNIQUE_ID_DER + _tlv(0x13, b"CEAT951015IW5")
        assert _reparar_printablestring_en_der(der) is None

    def test_no_toca_strings_que_no_siguen_a_un_oid(self):
        # Bytes opacos (llave/firma) que por casualidad parecen un TLV 0x13.
        basura = b"\x30\x82\x01\x0a" + _tlv(0x13, b"\xeb\xb4\x01\x7f")
        assert _reparar_printablestring_en_der(basura) is None

    def test_der_desde_pem(self, test_cer):
        der = Path(test_cer).read_bytes()
        cert = x509.load_der_x509_certificate(der)
        from cryptography.hazmat.primitives import serialization

        pem = cert.public_bytes(serialization.Encoding.PEM)
        assert _der_desde_pem(pem) == der
        assert _der_desde_pem(der) is None  # DER crudo no es PEM


class TestFIELCertConAcentoEnPrintableString:
    """Integración: el .cer de la CA vieja debe cargar y NO alterarse.

    Se simula el defecto sobre el cert de prueba metiéndole la "ó" (0xC3 0xB3)
    en el CN sin cambiar la longitud, para que el archivo siga siendo un DER
    bien formado que solo el parser estricto rechaza.
    """

    @pytest.fixture
    def cer_con_acento(self, test_cer, tmp_path):
        der = bytearray(Path(test_cer).read_bytes())
        i = der.find(_OID_COMMON_NAME_DER)
        assert i != -1, "el cert de prueba debe traer un commonName"
        j = i + len(_OID_COMMON_NAME_DER)
        der[j] = 0x13                       # fuerza el tag PrintableString
        inicio = j + 2
        der[inicio : inicio + 2] = b"\xc3\xb3"  # "ó" — misma longitud
        destino = tmp_path / "acento.cer"
        destino.write_bytes(bytes(der))
        return str(destino)

    def test_cryptography_solo_lo_rechaza_sin_reparar(self, cer_con_acento):
        with pytest.raises(ValueError):
            x509.load_der_x509_certificate(Path(cer_con_acento).read_bytes())

    def test_fiel_lo_carga(self, cer_con_acento, test_key, test_password):
        fiel = FIEL(cer_con_acento, test_key, test_password)
        assert fiel.rfc is not None
        assert fiel.vigente is True

    def test_certificate_b64_conserva_los_bytes_originales(
        self, cer_con_acento, test_key, test_password
    ):
        # Crítico: la CA firmó el tbsCertificate tal cual. Si mandáramos al SAT
        # el DER con el tag corregido, la firma no cuadraría.
        fiel = FIEL(cer_con_acento, test_key, test_password)
        assert base64.b64decode(fiel.certificate_b64) == Path(cer_con_acento).read_bytes()


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

    def test_cer_invalido_da_error_en_espanol_del_cer(
        self, test_key, test_password, tmp_path
    ):
        # Regresión: un .cer ilegible se reportaba con el error crudo del ÚLTIMO
        # intento ("Unable to load PEM file … MalformedFraming"), que hablaba de
        # PEM y hacía pensar que el problema estaba en la .key.
        malo = tmp_path / "malo.cer"
        malo.write_bytes(b"no soy un certificado")
        with pytest.raises(ValueError, match=r"certificado \(\.cer\)"):
            FIEL(str(malo), test_key, test_password)


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

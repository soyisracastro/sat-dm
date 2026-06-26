"""
Manejo de la e-firma (FIEL) del SAT.

Carga el certificado (.cer) y la llave privada (.key), y firma
mensajes XML usando RSA-SHA1 (xmldsig).
"""

import base64
import hashlib
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.x509.oid import ExtensionOID


# RFC mexicano: 3 (moral) o 4 (física) letras + 6 dígitos de fecha + 3 de homoclave.
_RFC_RE = re.compile(r"[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}")


def _a_texto(valor) -> str:
    """Normaliza el valor de un atributo X.509 a `str` imprimible.

    `cryptography` devuelve `bytes` para ciertos OIDs no-texto (en especial
    X500_UNIQUE_IDENTIFIER / 2.5.4.45, que el SAT a veces tipa como BIT STRING,
    y los OtherName del subjectAltName, que vienen como DER). Decodifica y deja
    solo caracteres imprimibles para que las operaciones de string no truenen.
    """
    if isinstance(valor, bytes):
        try:
            valor = valor.decode("utf-8")
        except UnicodeDecodeError:
            valor = valor.decode("latin-1", errors="ignore")
    return "".join(c for c in valor if c.isprintable()).strip()


def _rfc_desde_valores(valores) -> str | None:
    """Extrae el RFC del titular de una lista de cadenas candidatas.

    Maneja el formato del SAT "RFC / CURP" (o, en moral, "RFC_EMPRESA /
    RFC_REPRESENTANTE": el titular es el primer token) y valida contra el patrón
    del RFC para no devolver basura (nombre del CN, prefijo de la CURP, etc.).
    """
    for crudo in valores:
        texto = _a_texto(crudo)
        if not texto:
            continue
        # Formato SAT: el RFC del titular va antes del " / ".
        token = (texto.split(" / ", 1)[0] if " / " in texto else texto).strip().upper()
        m = _RFC_RE.fullmatch(token) or _RFC_RE.search(token)
        if m:
            return m.group(0)
    return None


# OID 2.5.4.45 (x500UniqueIdentifier), donde el SAT pone el RFC, codificado en DER.
_OID_UNIQUE_ID_DER = bytes([0x06, 0x03, 0x55, 0x04, 0x2D])
# OID 2.5.4.3 (commonName), donde el SAT pone el nombre/razón social del titular.
_OID_COMMON_NAME_DER = bytes([0x06, 0x03, 0x55, 0x04, 0x03])
# OID 1.2.840.113549.1.1.1 (rsaEncryption): marca el inicio de la llave pública.
# Acota el escaneo del subject para no leer falsos positivos en la llave/firma.
_OID_RSA_ENCRYPTION_DER = bytes([0x06, 0x09, 0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x01, 0x01])
# Tags ASN.1 de string que puede usar el SAT para ese campo (Printable, UTF8, IA5,
# Teletex/T61, Numeric).
_STR_TAGS = frozenset({0x13, 0x0C, 0x16, 0x14, 0x12})


def _valores_oid_en_der(der: bytes, oid_der: bytes) -> list[bytes]:
    """Valores string que siguen a cada aparición de `oid_der` en el DER crudo.

    Fallback tolerante para certs cuyo subject `cryptography` no puede parsear
    (p. ej. nombres con Ñ tipados como T61String con bytes UTF-8 inválidos): el
    parser estricto truena al leer el subject completo aunque el RFC en sí esté
    limpio. Aquí se busca el OID directo en los bytes y se lee el TLV siguiente.
    Solo longitud en formato corto (<128 bytes), suficiente para RFC y serial.
    """
    out: list[bytes] = []
    i = der.find(oid_der)
    while i != -1:
        j = i + len(oid_der)
        if j + 1 < len(der) and der[j] in _STR_TAGS:
            length = der[j + 1]
            if length < 0x80 and j + 2 + length <= len(der):
                out.append(der[j + 2 : j + 2 + length])
        i = der.find(oid_der, i + 1)
    return out


class FIEL:
    """Encapsula la e-firma: certificado + llave privada."""

    def __init__(self, cer_path: str, key_path: str, password: str):
        """
        Carga el certificado y la llave privada.

        Args:
            cer_path: Ruta al archivo .cer (certificado en DER o PEM)
            key_path: Ruta al archivo .key (llave privada encriptada)
            password: Contraseña de la llave privada
        """
        self._cert = self._load_certificate(cer_path)
        self._private_key = self._load_private_key(key_path, password)
        self._validate_pair()

    # ------------------------------------------------------------------
    # Carga
    # ------------------------------------------------------------------

    def _load_certificate(self, path: str):
        data = Path(path).read_bytes()
        try:
            # Intentar DER primero (formato nativo del SAT)
            cert = x509.load_der_x509_certificate(data)
            self._cert_der = data
        except Exception:
            cert = x509.load_pem_x509_certificate(data)
            self._cert_der = cert.public_bytes(serialization.Encoding.DER)
        return cert

    def _load_private_key(self, path: str, password: str):
        data = Path(path).read_bytes()
        pwd_bytes = password.encode() if isinstance(password, str) else password
        # Las llaves del SAT vienen en DER PKCS#8; algunas en PEM. Probamos ambos.
        errores = []
        for cargar in (serialization.load_der_private_key,
                       serialization.load_pem_private_key):
            try:
                return cargar(data, password=pwd_bytes)
            except Exception as e:  # noqa: BLE001
                errores.append(str(e).lower())
        # Si ambos fallan, distinguir "contraseña incorrecta" de "archivo inválido"
        # (si no, el error real queda enmascarado por el del segundo intento).
        combinado = " ".join(errores)
        if any(k in combinado for k in ("decrypt", "password", "bad", "incorrect")):
            raise ValueError("La contraseña de la clave privada (.key) es incorrecta.")
        raise ValueError("No se pudo leer la clave privada (.key): formato no reconocido.")

    def _validate_pair(self):
        """Verifica que el certificado y la llave coincidan."""
        cert_pub = self._cert.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        key_pub = self._private_key.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        )
        if cert_pub != key_pub:
            raise ValueError(
                "El certificado y la llave privada no corresponden al mismo par."
            )

    # ------------------------------------------------------------------
    # Propiedades útiles
    # ------------------------------------------------------------------

    @property
    def rfc(self) -> str:
        """
        RFC del titular extraído del certificado.

        El SAT pone el RFC en el subject (OID 2.5.4.45 UniqueIdentifier; a veces
        en 2.5.4.5 serialNumber) con formato "RFC / CURP" (persona moral:
        "RFC_EMPRESA / RFC_REPRESENTANTE"). El titular es el primer token.

        Dos cuidados, ambos vistos en certs reales del SAT:
        - `cryptography` puede devolver el valor de 2.5.4.45 como `bytes` →
          `_a_texto` lo normaliza.
        - cuando el nombre del titular trae Ñ/acentos, el SAT lo tipa como
          T61String con bytes UTF-8 inválidos y el parser estricto de
          `cryptography` truena al leer TODO el subject (aunque el RFC esté
          limpio). En ese caso se cae al fallback `_rfc_desde_der`, que lee el
          OID 2.5.4.45 directo del DER sin parsear el subject.
        """
        try:
            rfc = _rfc_desde_valores(self._candidatos_rfc())
            if rfc:
                return rfc
        except Exception:
            # Subject ilegible por cryptography (p. ej. T61String con Ñ).
            pass
        rfc = self._rfc_desde_der()
        if rfc:
            return rfc
        try:
            detalle = f" Subject: {self._cert.subject.rfc4514_string()}"
        except Exception:
            detalle = ""  # subject no parseable; el mensaje base ya orienta
        raise ValueError("No se pudo extraer el RFC del certificado." + detalle)

    def _rfc_desde_der(self) -> str | None:
        """Lee el RFC del titular del DER crudo, evitando el subject estricto.

        El issuer (CA del SAT) también trae un 2.5.4.45 con su propio RFC y va
        ANTES del subject en el DER; por eso se toma la ÚLTIMA aparición, que es
        la del titular.
        """
        der = getattr(self, "_cert_der", None)
        if der is None:
            der = self._cert.public_bytes(serialization.Encoding.DER)
        valores = _valores_oid_en_der(der, _OID_UNIQUE_ID_DER)
        return _rfc_desde_valores(reversed(valores))

    def _candidatos_rfc(self):
        """Genera cadenas candidatas a contener el RFC, en orden de preferencia."""
        # 1) Subject: UniqueIdentifier (2.5.4.45) y serialNumber (2.5.4.5).
        for attr in self._cert.subject:
            if attr.oid.dotted_string in ("2.5.4.45", "2.5.4.5"):
                yield attr.value
        # 2) subjectAltName → OtherName (algunos certs del SAT ponen ahí el RFC).
        try:
            san = self._cert.extensions.get_extension_for_oid(
                ExtensionOID.SUBJECT_ALTERNATIVE_NAME
            ).value
            for on in san.get_values_for_type(x509.OtherName):
                yield on.value  # bytes DER; _a_texto extrae el texto imprimible
        except x509.ExtensionNotFound:
            pass
        # 3) Respaldo: CN y subject completo.
        cn = self._cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
        if cn:
            yield cn[0].value
        yield self._cert.subject.rfc4514_string()

    @property
    def legal_name(self) -> str | None:
        """
        Razón social (PM) o nombre completo (PF) del titular. El SAT lo pone en
        el CN del subject del certificado. None si no se puede extraer.

        Igual que el RFC: si el subject es ilegible para cryptography (nombre con
        Ñ/acentos tipado como T61String), se cae al fallback `_nombre_desde_der`,
        que lee el CN del DER crudo. Justo esos nombres son los que importan
        recuperar (sin él, la empresa se quedaría con el RFC como nombre).
        """
        try:
            cn = self._cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if cn and cn[0].value.strip():
                return cn[0].value.strip()
        except Exception:
            pass
        return self._nombre_desde_der()

    def _nombre_desde_der(self) -> str | None:
        """Lee el nombre del titular (CN) del DER crudo, evitando el subject estricto.

        Acota el escaneo a la parte previa a la llave pública (rsaEncryption) para
        no confundirse con bytes de la llave/firma, y toma el ÚLTIMO commonName
        (el issuer/CA va antes que el subject).
        """
        der = getattr(self, "_cert_der", None)
        if der is None:
            der = self._cert.public_bytes(serialization.Encoding.DER)
        fin = der.find(_OID_RSA_ENCRYPTION_DER)
        region = der[:fin] if fin != -1 else der
        valores = _valores_oid_en_der(region, _OID_COMMON_NAME_DER)
        if not valores:
            return None
        return _a_texto(valores[-1]) or None

    @property
    def not_valid_after(self) -> datetime:
        """Fecha de vencimiento del certificado."""
        return self._cert.not_valid_after_utc

    @property
    def vigente(self) -> bool:
        """True si el certificado no ha expirado."""
        return datetime.now(timezone.utc) < self.not_valid_after

    @property
    def numero_serie(self) -> str:
        """Número de serie del certificado en decimal (como lo espera el SAT)."""
        return str(self._cert.serial_number)

    @property
    def issuer_dn(self) -> str:
        """Nombre del emisor del certificado en formato RFC 4514 (para X509IssuerName en xmldsig)."""
        return self._cert.issuer.rfc4514_string()

    @property
    def certificate_b64(self) -> str:
        """Certificado en Base64 (DER) para incluir en el XML SOAP."""
        der = self._cert.public_bytes(serialization.Encoding.DER)
        return base64.b64encode(der).decode()

    # ------------------------------------------------------------------
    # Firma
    # ------------------------------------------------------------------

    def sign(self, data: bytes) -> bytes:
        """
        Firma `data` con RSA-SHA1 (algoritmo requerido por el SAT).

        Returns:
            Firma en bytes (raw).
        """
        signature = self._private_key.sign(data, padding.PKCS1v15(), hashes.SHA1())
        return signature

    def sign_b64(self, data: bytes) -> str:
        """Firma y devuelve en Base64."""
        return base64.b64encode(self.sign(data)).decode()

    def digest_sha1_b64(self, data: bytes) -> str:
        """SHA-1 digest de `data` en Base64 (para DigestValue en xmldsig)."""
        digest = hashlib.sha1(data).digest()
        return base64.b64encode(digest).decode()

    # ------------------------------------------------------------------
    # Construcción de Security Token para SOAP WS-Security
    # ------------------------------------------------------------------

    def build_security_token_reference(self) -> str:
        """Devuelve el ID del BinarySecurityToken para referencias cruzadas."""
        return f"uuid-{self.numero_serie}-1"

    def now_utc_str(self) -> str:
        """Timestamp en UTC formato ISO requerido por el SAT."""
        now = datetime.now(timezone.utc)
        return now.strftime("%Y-%m-%dT%H:%M:%SZ")

    def expires_utc_str(self, minutes: int = 5) -> str:
        """Timestamp de expiración (ahora + `minutes`)."""
        exp = datetime.now(timezone.utc) + timedelta(minutes=minutes)
        return exp.strftime("%Y-%m-%dT%H:%M:%SZ")

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
            return x509.load_der_x509_certificate(data)
        except Exception:
            return x509.load_pem_x509_certificate(data)

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

        OJO: `cryptography` puede devolver el valor de 2.5.4.45 como `bytes`
        (cuando el cert lo tipa como BIT STRING en vez de texto) — por eso se
        normaliza con `_a_texto`. Como respaldo se revisa el subjectAltName, el
        CN y el subject completo. Ver `_candidatos_rfc`.
        """
        rfc = _rfc_desde_valores(self._candidatos_rfc())
        if rfc:
            return rfc
        raise ValueError(
            "No se pudo extraer el RFC del certificado. "
            f"Subject: {self._cert.subject.rfc4514_string()}"
        )

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
        """
        try:
            cn = self._cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if cn and cn[0].value.strip():
                return cn[0].value.strip()
        except Exception:
            pass
        return None

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

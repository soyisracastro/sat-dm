"""
Manejo de la e-firma (FIEL) del SAT.

Carga el certificado (.cer) y la llave privada (.key), y firma
mensajes XML usando RSA-SHA1 (xmldsig).
"""

import base64
import hashlib
from datetime import datetime, timezone, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


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
        # Las llaves del SAT vienen en formato DER PKCS#8
        try:
            return serialization.load_der_private_key(data, password=pwd_bytes)
        except Exception:
            return serialization.load_pem_private_key(data, password=pwd_bytes)

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
        """RFC extraído del certificado (campo OID 2.5.4.45 o CN)."""
        try:
            # El RFC está en el campo serialNumber o en el OID específico del SAT
            for attr in self._cert.subject:
                if attr.oid.dotted_string in ("2.5.4.45", "2.5.4.5"):
                    # El SAT lo guarda como "CURP / RFC" separado por espacio
                    value = attr.value
                    parts = value.strip().split()
                    # El RFC es el último token
                    return parts[-1]
        except Exception:
            pass
        # Fallback: buscar en CN
        try:
            cn = self._cert.subject.get_attributes_for_oid(x509.NameOID.COMMON_NAME)
            if cn:
                return cn[0].value.split()[-1]
        except Exception:
            pass
        raise ValueError("No se pudo extraer el RFC del certificado.")

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

"""
Generación de solicitudes de e.firma y CSD para el SAT — equivalente a la app
oficial "Certifica" (antes SOLCEDI), en Python puro.

Portado de `satcfdi.certifica` (SAT-CFDI/python-satcfdi, licencia MIT) y adaptado
a la `FIEL` de este proyecto (`core/fiel.py`, basada en `cryptography`) para no
depender de pyOpenSSL. Produce los tres artefactos que genera Certifica:

- ``.req``  Requerimiento de Generación de e.firma: PKCS#10 auto-firmado con la
            llave NUEVA. No requiere una e.firma previa.
- ``.ren``  Requerimiento de Renovación de e.firma: ese PKCS#10 envuelto en un
            PKCS#7/CMS SignedData firmado con la e.firma VIGENTE.
- ``.sdg``  Solicitud de Certificado de Sello Digital: un ZIP de PKCS#10 tipo
            SELLO (uno por sucursal) envuelto en el mismo CMS con la e.firma.

Todo se construye en local; el ENVÍO al SAT (CertiSAT Web) es un paso aparte
(scraping en `portal/`). Este build de Certifica firma todo con SHA-1; se
conserva SHA-1 aquí. Validar contra el portal real antes de anunciarlo.

Diferencia deliberada con Certifica: el nuevo ``.key`` se cifra con AES-256
(``BestAvailableEncryption`` de `cryptography`) en lugar del 3DES de Certifica.
El ``.key`` nunca se envía al SAT (solo lo guarda el usuario) y las herramientas
modernas leen PKCS#8/AES sin problema; solo cambian esos bytes, no la solicitud.
"""

import base64
import hashlib
from datetime import datetime
from pathlib import Path
from secrets import token_bytes

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from .ans1e import Ans1Encoder, Numbers, Classes
from .pkcs7 import create_pkcs7
from ._zip import zip_bytes, ZipData
# Reutilizamos los extractores tolerantes de la FIEL (manejan subjects ilegibles
# por `cryptography`, p. ej. nombres con Ñ tipados como T61String).
from ..core.fiel import _valores_oid_en_der, _a_texto

ENCODING = "windows-1252"

# OIDs del subject que necesitamos leer del certificado vigente, con su prefijo
# DER (para el fallback de escaneo directo cuando el subject no parsea).
_OID_DER = {
    "2.5.4.45": bytes([0x06, 0x03, 0x55, 0x04, 0x2D]),  # x500UniqueIdentifier (RFC)
    "2.5.4.5": bytes([0x06, 0x03, 0x55, 0x04, 0x05]),   # serialNumber (CURP)
    "2.5.4.3": bytes([0x06, 0x03, 0x55, 0x04, 0x03]),   # CN (nombre / razón social PF)
    "2.5.4.10": bytes([0x06, 0x03, 0x55, 0x04, 0x0A]),  # O (razón social PM)
    "1.2.840.113549.1.9.1": bytes(
        [0x06, 0x09, 0x2A, 0x86, 0x48, 0x86, 0xF7, 0x0D, 0x01, 0x09, 0x01]
    ),  # emailAddress
}


# ---------------------------------------------------------------------------
# Lectura del subject del certificado vigente
# ---------------------------------------------------------------------------

def _componentes_subject(fiel) -> dict[str, str]:
    """Devuelve {OID: valor} del subject del `.cer` vigente.

    Intenta primero el subject parseado por `cryptography`; si truena (subject
    ilegible), cae al escaneo del DER crudo, igual que hace `FIEL.rfc`. Toma la
    ÚLTIMA aparición de cada OID en el DER (el issuer/CA va antes que el subject).
    """
    comps: dict[str, str] = {}
    try:
        for attr in fiel._cert.subject:
            dotted = attr.oid.dotted_string
            if dotted in _OID_DER:
                comps.setdefault(dotted, _a_texto(attr.value))
    except Exception:
        pass

    der = getattr(fiel, "_cert_der", None) or fiel._cert.public_bytes(
        serialization.Encoding.DER
    )
    for dotted, oid_der in _OID_DER.items():
        if not comps.get(dotted):
            valores = _valores_oid_en_der(der, oid_der)
            if valores:
                comps[dotted] = _a_texto(valores[-1])
    return comps


def _es_moral(rfc: str) -> bool:
    """RFC de persona moral = 12 caracteres (3 letras); física = 13 (4 letras)."""
    return len(rfc.strip()) == 12


# ---------------------------------------------------------------------------
# PKCS#10 (idéntico a Certifica: hand-rolled, firmado con la llave NUEVA)
# ---------------------------------------------------------------------------

def _certificate_request(private_key, subject: list[tuple], code: bytes) -> bytes:
    """Construye un PKCS#10 CertificationRequest (DER) auto-firmado con
    `private_key` (la llave nueva) usando SHA1withRSA.

    `subject` es una lista ordenada de (oid, valor, nr) donde `nr` es el tag ASN.1
    (None → UTF8String, como en Certifica para nombre/razón social/sucursal).
    """
    public_key_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.PKCS1,
    )

    e = Ans1Encoder()
    with e.seq():
        e(0)  # version
        with e.seq():  # subject
            for oid, valor, nr in subject:
                with e.set():
                    with e.seq():
                        e.oid(oid)
                        e(valor, nr=nr)
        with e.seq():  # subjectPKInfo
            with e.seq():
                e.oid("1.2.840.113549.1.1.1")  # rsaEncryption
                e()
            e(public_key_bytes, nr=Numbers.BitString)
        with e.enter(nr=0, cls=Classes.Context):  # attributes
            with e.seq():
                e.oid("1.2.840.113549.1.9.7")  # challengePassword
                with e.set():
                    e(code, nr=Numbers.PrintableString)
    cert_request_bytes = e.output()

    e = Ans1Encoder()
    with e.seq():
        e.write(cert_request_bytes)
        with e.seq():
            e.oid("1.2.840.113549.1.1.5")  # sha1WithRSAEncryption
            e()
        e(
            private_key.sign(
                data=cert_request_bytes,
                padding=padding.PKCS1v15(),
                algorithm=hashes.SHA1(),
            ),
            nr=Numbers.BitString,
        )
    return e.output()


def _codigo_reto(rfc_ui: str) -> bytes:
    """Reto del CSD: Base64(SHA1(ui + Base64(SHA1(ui+ui)))) sobre el
    x500UniqueIdentifier, tal como Certifica."""
    ui = rfc_ui.encode(ENCODING)

    def digest(value: bytes) -> bytes:
        return base64.b64encode(hashlib.sha1(value).digest())

    return digest(ui + digest(ui + ui))


def _codigo_aleatorio() -> bytes:
    """Reto de generación/renovación: Base64 de 20 bytes aleatorios."""
    return base64.b64encode(token_bytes(20))


# ---------------------------------------------------------------------------
# Nueva llave privada
# ---------------------------------------------------------------------------

def _generar_llave(ruta: Path, password: str):
    """Genera un par RSA-2048 nuevo y escribe el `.key` cifrado (PKCS#8/AES-256)."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ruta.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode()
            ),
        )
    )
    return private_key


def _cms(fiel, data: bytes) -> bytes:
    """Envuelve `data` en el CMS firmado con la e.firma vigente (`fiel`)."""
    cert = fiel._cert
    cert_der = getattr(fiel, "_cert_der", None) or cert.public_bytes(
        serialization.Encoding.DER
    )
    return create_pkcs7(
        data,
        cert_der=cert_der,
        issuer_der=cert.issuer.public_bytes(),
        serial=cert.serial_number,
        private_key=fiel._private_key,
        hash_algorithm=hashes.SHA1(),
    )


def _stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def _dir(salida_dir: str | None) -> Path:
    d = Path(salida_dir) if salida_dir else Path.cwd()
    d.mkdir(parents=True, exist_ok=True)
    return d


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------

def generar_requerimiento_fiel(
    rfc: str,
    curp: str,
    correo: str,
    password: str,
    salida_dir: str | None = None,
) -> dict[str, Path]:
    """Genera una e.firma NUEVA (sin e.firma previa): escribe `.key` + `.req`.

    El `.req` es un PKCS#10 pelón auto-firmado con la llave nueva.
    """
    rfc = rfc.strip().upper()
    d = _dir(salida_dir)
    tmf = _stamp()

    key_path = d / f"Claveprivada_FIEL_{rfc}_{tmf}.key"
    private_key = _generar_llave(key_path, password)

    subject = [
        ("2.5.4.45", rfc.encode(ENCODING), Numbers.PrintableString),
        ("2.5.4.5", curp.strip().upper().encode(ENCODING), Numbers.PrintableString),
        ("1.2.840.113549.1.9.1", correo, Numbers.IA5String),
    ]
    req = _certificate_request(private_key, subject, _codigo_aleatorio())
    req_path = d / f"Requerimiento_FIEL_{rfc}_{tmf}.req"
    req_path.write_bytes(req)
    return {"key": key_path, "req": req_path}


def generar_renovacion_fiel(
    fiel,
    correo: str | None = None,
    password: str | None = None,
    salida_dir: str | None = None,
) -> dict[str, Path]:
    """Renovación de e.firma de persona FÍSICA: escribe `.key` (nuevo) + `.ren`.

    Args:
        fiel: `FIEL` vigente (la que está por vencer), ya cargada.
        correo: correo para el nuevo requerimiento; si falta, se toma del cert.
        password: contraseña del NUEVO `.key`.
    """
    if not password:
        raise ValueError("Falta la contraseña para el nuevo .key")
    comps = _componentes_subject(fiel)
    d = _dir(salida_dir)
    tmf = _stamp()

    key_path = d / f"Claveprivada_FIEL_{fiel.rfc}_{tmf}.key"
    private_key = _generar_llave(key_path, password)

    correo_val = correo or comps.get("1.2.840.113549.1.9.1", "")
    subject = [
        ("2.5.4.45", comps.get("2.5.4.45", "").encode(ENCODING), Numbers.PrintableString),
        ("2.5.4.5", comps.get("2.5.4.5", "").encode(ENCODING), Numbers.PrintableString),
        ("1.2.840.113549.1.9.1", correo_val, Numbers.IA5String),
    ]
    inner = _certificate_request(private_key, subject, _codigo_aleatorio())
    ren = _cms(fiel, inner)
    ren_path = d / f"Renovacion_FIEL_{fiel.rfc}_{tmf}.ren"
    ren_path.write_bytes(ren)
    return {"key": key_path, "ren": ren_path}


def generar_renovacion_fiel_moral(
    fiel,
    rfc_moral: str,
    correo: str,
    password: str,
    salida_dir: str | None = None,
) -> dict[str, Path]:
    """Renovación de e.firma de persona MORAL con representante legal.

    Se firma con la e.firma del representante legal (`fiel`) y `rfc_moral` es el
    RFC de la persona moral a renovar.
    """
    rfc_moral = rfc_moral.strip().upper()
    if not _es_moral(rfc_moral):
        raise ValueError(f"'{rfc_moral}' no es un RFC de persona moral (12 caracteres)")
    comps = _componentes_subject(fiel)
    d = _dir(salida_dir)
    tmf = _stamp()

    key_path = d / f"Claveprivada_FIEL_{rfc_moral}_{tmf}.key"
    private_key = _generar_llave(key_path, password)

    ui = rfc_moral.encode(ENCODING) + b" / " + comps.get("2.5.4.45", "").encode(ENCODING)
    serial = b" / " + comps.get("2.5.4.5", "").encode(ENCODING)
    subject = [
        ("2.5.4.45", ui, Numbers.PrintableString),
        ("2.5.4.5", serial, Numbers.PrintableString),
        ("1.2.840.113549.1.9.1", correo, Numbers.IA5String),
    ]
    inner = _certificate_request(private_key, subject, _codigo_aleatorio())
    ren = _cms(fiel, inner)
    ren_path = d / f"Renovacion_FIEL_{rfc_moral}_{tmf}.ren"
    ren_path.write_bytes(ren)
    return {"key": key_path, "ren": ren_path}


def generar_solicitud_csd(
    fiel,
    sucursal: str,
    password: str,
    salida_dir: str | None = None,
) -> dict[str, Path]:
    """Solicitud de Certificado de Sello Digital (CSD) para una sucursal/unidad.

    Escribe el `.key` (nuevo, del sello) + el `.sdg` (ZIP de PKCS#10 SELLO
    envuelto en el CMS firmado con la e.firma vigente `fiel`).
    """
    comps = _componentes_subject(fiel)
    rfc = fiel.rfc
    d = _dir(salida_dir)
    tmf = _stamp()

    key_path = d / f"CSD_{sucursal.replace(' ', '_')}_{rfc}_{tmf}.key"
    private_key = _generar_llave(key_path, password)

    ui = comps.get("2.5.4.45", "")
    subject = [
        ("2.5.4.45", ui.encode(ENCODING), Numbers.PrintableString),
        ("2.5.4.5", comps.get("2.5.4.5", "").encode(ENCODING), Numbers.PrintableString),
    ]
    if _es_moral(rfc):
        subject.append(("2.5.4.10", comps.get("2.5.4.10", ""), None))  # O (razón social)
    else:
        subject.append(("2.5.4.3", comps.get("2.5.4.3", ""), None))    # CN (nombre)
    subject.append(("2.5.4.11", sucursal, None))  # OU = nombre de la sucursal

    inner = _certificate_request(private_key, subject, _codigo_reto(ui))
    nombre_req = f"CSD_{sucursal.replace(' ', '_')}_{rfc}_{tmf}s.req"
    zipped = zip_bytes([ZipData(nombre_req, inner)])
    sdg = _cms(fiel, zipped)
    sdg_path = d / f"CSD_{rfc}_{tmf}.sdg"
    sdg_path.write_bytes(sdg)
    return {"key": key_path, "sdg": sdg_path}

"""
Tests de `sat_descarga.certifica`: generación de solicitudes de e.firma (.req/.ren)
y CSD (.sdg), equivalente a la app "Certifica" del SAT.

Verificación INDEPENDIENTE de lo generado (no confía en el propio código):
  - El PKCS#10 interno: firma auto-verificada con SHA-1 (la firma es válida aunque
    `is_signature_valid` devuelva False por la política anti-SHA-1 de cryptography),
    OIDs del subject y atributo challengePassword.
  - El CMS externo (.ren/.sdg): el certificado vigente va incrustado y, si hay
    `openssl` en el PATH, `openssl cms -verify` confirma la firma con la e.firma
    vigente y se valida el contenido encapsulado.
  - El nuevo .key abre con su contraseña.

Usa los fixtures de e.firma de prueba de conftest (RFC XAXX010101000).
"""

import io
import shutil
import subprocess
import zipfile
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.serialization import pkcs7

from sat_descarga.core.fiel import FIEL
from sat_descarga import certifica

CHALLENGE_PASSWORD_OID = x509.ObjectIdentifier("1.2.840.113549.1.9.7")
NUEVA_PWD = "NuevaClave#2026"


# ---------------------------------------------------------------------------
# Helpers de verificación independiente
# ---------------------------------------------------------------------------

def _firma_pkcs10_valida(csr: x509.CertificateSigningRequest) -> bool:
    """Verifica a mano la auto-firma del PKCS#10 (SHA-1). `is_signature_valid`
    devuelve False para SHA-1 en cryptography reciente, así que no sirve aquí."""
    try:
        csr.public_key().verify(
            csr.signature, csr.tbs_certrequest_bytes, padding.PKCS1v15(), hashes.SHA1()
        )
        return True
    except Exception:
        return False


def _verificar_pkcs10(der: bytes, oids: dict, sucursal: str | None = None):
    csr = x509.load_der_x509_csr(der)
    assert _firma_pkcs10_valida(csr), "auto-firma del PKCS#10 inválida"
    assert isinstance(csr.signature_hash_algorithm, hashes.SHA1)
    subj = {a.oid.dotted_string: a.value for a in csr.subject}
    for oid, val in oids.items():
        assert subj.get(oid) == val, f"subject {oid}: {subj.get(oid)!r} != {val!r}"
    cp = csr.attributes.get_attribute_for_oid(CHALLENGE_PASSWORD_OID)
    assert cp.value, "falta challengePassword"
    if sucursal is not None:
        assert subj.get("2.5.4.11") == sucursal
    return csr


def _cert_vigente_incrustado(cms_der: bytes, fiel: FIEL) -> bool:
    """El CMS debe traer incrustado el certificado vigente (el que firma)."""
    certs = pkcs7.load_der_pkcs7_certificates(cms_der)
    esperado = fiel._cert.public_bytes(serialization.Encoding.DER)
    return any(c.public_bytes(serialization.Encoding.DER) == esperado for c in certs)


def _openssl_cms_contenido(ruta: Path, fiel: FIEL, tmp: Path) -> bytes:
    """Verifica la firma CMS con openssl y devuelve el contenido encapsulado."""
    pem = tmp / "vigente.pem"
    pem.write_bytes(fiel._cert.public_bytes(serialization.Encoding.PEM))
    out = tmp / "contenido.bin"
    r = subprocess.run(
        ["openssl", "cms", "-verify", "-in", str(ruta), "-inform", "DER",
         "-noverify", "-certfile", str(pem), "-out", str(out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, f"openssl cms -verify falló: {r.stderr}"
    return out.read_bytes()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fiel(test_cer, test_key, test_password) -> FIEL:
    return FIEL(test_cer, test_key, test_password)


# ---------------------------------------------------------------------------
# .req — generación de e.firma nueva (sin e.firma previa)
# ---------------------------------------------------------------------------

def test_generar_requerimiento_fiel(tmp_path):
    res = certifica.generar_requerimiento_fiel(
        "XAXX010101000", "XAXX010101HDFXXX01", "juan@correo.com", NUEVA_PWD, str(tmp_path)
    )
    assert res["req"].suffix == ".req" and res["key"].suffix == ".key"
    _verificar_pkcs10(
        res["req"].read_bytes(),
        {"2.5.4.45": "XAXX010101000", "2.5.4.5": "XAXX010101HDFXXX01",
         "1.2.840.113549.1.9.1": "juan@correo.com"},
    )
    # el nuevo .key abre con su contraseña
    serialization.load_der_private_key(res["key"].read_bytes(), NUEVA_PWD.encode())


# ---------------------------------------------------------------------------
# .ren — renovación con la e.firma vigente
# ---------------------------------------------------------------------------

def test_renovacion_fiel_estructura_y_cert(fiel, tmp_path):
    res = certifica.generar_renovacion_fiel(fiel, "nuevo@correo.com", NUEVA_PWD, str(tmp_path))
    ren = res["ren"].read_bytes()
    assert res["ren"].suffix == ".ren"
    # el certificado vigente va incrustado en el CMS
    assert _cert_vigente_incrustado(ren, fiel)
    # el nuevo .key abre
    serialization.load_der_private_key(res["key"].read_bytes(), NUEVA_PWD.encode())


@pytest.mark.skipif(shutil.which("openssl") is None, reason="requiere openssl")
def test_renovacion_fiel_firma_cms_y_contenido(fiel, tmp_path):
    res = certifica.generar_renovacion_fiel(fiel, "nuevo@correo.com", NUEVA_PWD, str(tmp_path))
    contenido = _openssl_cms_contenido(res["ren"], fiel, tmp_path)
    # el contenido encapsulado es el PKCS#10 nuevo (RFC/CURP copiados del cert vigente)
    _verificar_pkcs10(
        contenido,
        {"2.5.4.45": fiel.rfc, "2.5.4.5": "XAXX010101HDFRRN09",
         "1.2.840.113549.1.9.1": "nuevo@correo.com"},
    )


def test_renovacion_moral_rechaza_rfc_fisica(fiel, tmp_path):
    with pytest.raises(ValueError):
        certifica.generar_renovacion_fiel_moral(
            fiel, "XAXX010101000", "a@b.com", NUEVA_PWD, str(tmp_path)  # 13 chars = física
        )


# ---------------------------------------------------------------------------
# .sdg — solicitud de CSD
# ---------------------------------------------------------------------------

def test_solicitud_csd_estructura(fiel, tmp_path):
    res = certifica.generar_solicitud_csd(fiel, "Matriz Centro", NUEVA_PWD, str(tmp_path))
    assert res["sdg"].suffix == ".sdg"
    assert _cert_vigente_incrustado(res["sdg"].read_bytes(), fiel)
    serialization.load_der_private_key(res["key"].read_bytes(), NUEVA_PWD.encode())


@pytest.mark.skipif(shutil.which("openssl") is None, reason="requiere openssl")
def test_solicitud_csd_firma_cms_zip_y_sello(fiel, tmp_path):
    suc = "Matriz Centro"
    res = certifica.generar_solicitud_csd(fiel, suc, NUEVA_PWD, str(tmp_path))
    contenido = _openssl_cms_contenido(res["sdg"], fiel, tmp_path)
    assert contenido[:2] == b"PK", "el contenido del .sdg debe ser un ZIP"
    with zipfile.ZipFile(io.BytesIO(contenido)) as z:
        nombres = z.namelist()
        assert len(nombres) == 1 and nombres[0].endswith("s.req")
        inner = z.read(nombres[0])
    # PKCS#10 SELLO: CN (física) + OU = sucursal
    _verificar_pkcs10(
        inner,
        {"2.5.4.45": fiel.rfc, "2.5.4.3": "PRUEBA EMPRESA SA DE CV"},
        sucursal=suc,
    )

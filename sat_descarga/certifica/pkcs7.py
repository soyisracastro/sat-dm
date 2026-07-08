"""
Construcción del PKCS#7/CMS SignedData que envuelve la solicitud.

Es la firma EXTERNA que hace Certifica con la e.firma VIGENTE sobre el PKCS#10
(renovación `.ren`) o sobre el ZIP de PKCS#10 (CSD `.sdg`). Lleva atributos
firmados (contentType, signingTime, messageDigest) y la firma RSA va sobre el DER
del SET de atributos, no sobre el contenido. Este build de Certifica usa SHA-1.

Portado de `satcfdi.certifica.pkcs7` (MIT), adaptado para recibir los bytes del
certificado/emisor/serie y la llave privada de `cryptography` directamente, sin
el envoltorio `Signer` de pyOpenSSL.
"""

from datetime import datetime, timezone

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding

from .ans1e import Ans1Encoder, Numbers, Classes, to_utc_time

UTC = timezone.utc


def create_pkcs7(
    data: bytes,
    *,
    cert_der: bytes,
    issuer_der: bytes,
    serial: int,
    private_key,
    hash_algorithm=None,
) -> bytes:
    """Envuelve `data` en un CMS SignedData firmado con `private_key` (la e.firma
    vigente), incrustando su certificado (`cert_der`). Devuelve DER."""
    hash_algorithm = hash_algorithm or hashes.SHA1()

    hash_object = hashes.Hash(hash_algorithm)
    hash_object.update(data)
    digest = hash_object.finalize()

    utctime = to_utc_time(datetime.now(UTC).replace(tzinfo=None))

    # Atributos firmados: contentType (data), signingTime (ahora), messageDigest.
    e = Ans1Encoder()
    with e.seq():
        e.oid("1.2.840.113549.1.9.3")
        with e.set():
            e.oid("1.2.840.113549.1.7.1")
    with e.seq():
        e.oid("1.2.840.113549.1.9.5")
        with e.set():
            e(utctime, nr=Numbers.UTCTime)
    with e.seq():
        e.oid("1.2.840.113549.1.9.4")
        with e.set():
            e(digest, nr=Numbers.OctetString)
    signed_attributes = e.output()

    # La firma RSA va sobre el DER del SET de atributos (tag 0x31), no del SEQUENCE.
    e = Ans1Encoder()
    with e.set():
        e.write(signed_attributes)
    signing_data = e.output()

    signature = private_key.sign(
        data=signing_data,
        padding=padding.PKCS1v15(),
        algorithm=hash_algorithm,
    )

    e = Ans1Encoder()
    with e.seq():
        e.oid("1.2.840.113549.1.7.2")  # id-signedData
        with e.enter(nr=0, cls=Classes.Context):
            with e.seq():
                e(1, nr=Numbers.Integer)  # version
                with e.set():  # digestAlgorithms
                    with e.seq():
                        e.oid("1.3.14.3.2.26")  # SHA-1
                        e(nr=Numbers.Null)
                with e.seq():  # encapContentInfo
                    e.oid("1.2.840.113549.1.7.1")  # id-data
                    with e.enter(nr=0, cls=Classes.Context):
                        e(data, nr=Numbers.OctetString)
                with e.enter(nr=0, cls=Classes.Context):  # certificates
                    e.write(cert_der)
                with e.set():  # signerInfos
                    with e.seq():
                        e(1, nr=Numbers.Integer)  # version
                        with e.seq():  # IssuerAndSerialNumber
                            e.write(issuer_der)
                            e(serial, nr=Numbers.Integer)
                        with e.seq():  # digestAlgorithm
                            e.oid("1.3.14.3.2.26")  # SHA-1
                            e(nr=Numbers.Null)
                        with e.enter(nr=0, cls=Classes.Context):  # signedAttrs
                            e.write(signed_attributes)
                        with e.seq():  # signatureAlgorithm
                            e.oid("1.2.840.113549.1.1.1")  # rsaEncryption
                            e(nr=Numbers.Null)
                        e(signature, nr=Numbers.OctetString)

    return e.output()

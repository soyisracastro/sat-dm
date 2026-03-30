"""
SolicitaDescarga: envía una solicitud de descarga masiva al SAT (API v1.5).

Cambios en v1.5 (mayo 2025):
- Namespace body: http://DescargaMasivaTerceros.sat.gob.mx
- La operación única SolicitaDescarga se dividió en dos:
    · SolicitaDescargaEmitidos  → para CFDIs emitidos por el RFC solicitante
    · SolicitaDescargaRecibidos → para CFDIs recibidos por el RFC solicitante
- Autenticación: token WRAP en HTTP header "Authorization: WRAP access_token=..."
  + firma xmldsig enveloped en el cuerpo (elemento SolicitaDescargaEmitidos firmado)
- La firma va como hijo de <solicitud>, pero se computa sobre el padre
  <SolicitaDescargaEmitidos> (enveloped-signature con URI="").
"""

import hashlib
import base64
from datetime import date
from io import BytesIO
from typing import Optional
from lxml import etree

from .config import ENDPOINTS, SOAP_ACTIONS, TIPO_CFDI, TIPO_EMITIDO
from .fiel import FIEL
from .http_client import make_request


_SOAP_NS = "http://schemas.xmlsoap.org/soap/envelope/"
_DES_NS = "http://DescargaMasivaTerceros.sat.gob.mx"
_XMLDSIG_NS = "http://www.w3.org/2000/09/xmldsig#"


def solicitar_descarga(
    fiel: FIEL,
    token: str,
    rfc_solicitante: str,
    fecha_inicio: date,
    fecha_fin: date,
    tipo_solicitud: str = TIPO_CFDI,
    tipo_comprobante: str = TIPO_EMITIDO,
    rfc_emisor: Optional[str] = None,
    rfc_receptor: Optional[str] = None,
    estado_comprobante: Optional[str] = None,
) -> str:
    """
    Solicita una descarga masiva de CFDIs (API v1.5).

    Args:
        fiel: Instancia de FIEL. Cada solicitud se firma con la e-firma.
        token: Token WRAP obtenido con auth.obtener_token() (URL-encoded).
               Se envía como "Authorization: WRAP access_token='{token}'".
        rfc_solicitante: RFC del contribuyente dueño de la e-firma.
        fecha_inicio: Fecha de inicio del periodo (inclusive).
        fecha_fin: Fecha de fin del periodo (inclusive).
        tipo_solicitud: "CFDI", "Metadata", "PDF", etc.
        tipo_comprobante: "E" (emitidos) o "R" (recibidos).
        rfc_emisor: Filtrar por RFC emisor (solo recibidos, opcional).
        rfc_receptor: Filtrar por RFC receptor (solo emitidos, opcional).

    Returns:
        IdSolicitud (string) para usar en verificación.

    Raises:
        RuntimeError: Si el SAT rechaza la solicitud.
    """
    if tipo_comprobante.upper() == "E":
        return _solicitar_emitidos(
            fiel, token, rfc_solicitante, fecha_inicio, fecha_fin,
            tipo_solicitud, rfc_receptor, estado_comprobante,
        )
    else:
        return _solicitar_recibidos(
            fiel, token, rfc_solicitante, fecha_inicio, fecha_fin,
            tipo_solicitud, rfc_emisor, estado_comprobante,
        )


# ---------------------------------------------------------------------------
# Emitidos
# ---------------------------------------------------------------------------

def _solicitar_emitidos(
    fiel: FIEL,
    token: str,
    rfc_solicitante: str,
    fecha_inicio: date,
    fecha_fin: date,
    tipo_solicitud: str,
    rfc_receptores: Optional[str] = None,
    estado_comprobante: Optional[str] = None,
) -> str:
    """SolicitaDescargaEmitidos — CFDIs emitidos por rfc_solicitante."""
    fi = fecha_inicio.strftime("%Y-%m-%dT00:00:02")
    ff = fecha_fin.strftime("%Y-%m-%dT23:59:57")

    # Atributos de la solicitud (sin firma aún)
    # EstadoComprobante va primero según documentación SAT v1.5
    solicitud_attrs = ""
    if estado_comprobante:
        solicitud_attrs += f' EstadoComprobante="{estado_comprobante}"'
    solicitud_attrs += (
        f' FechaInicial="{fi}"'
        f' FechaFinal="{ff}"'
        f' RfcEmisor="{rfc_solicitante}"'
        f' RfcSolicitante="{rfc_solicitante}"'
        f' TipoSolicitud="{tipo_solicitud}"'
    )

    receptores_xml = ""
    if rfc_receptores:
        receptores_xml = (
            f'<des:RfcReceptores>'
            f'<des:RfcReceptor>{rfc_receptores}</des:RfcReceptor>'
            f'</des:RfcReceptores>'
        )

    envelope_xml = (
        f'<s:Envelope xmlns:s="{_SOAP_NS}" xmlns:des="{_DES_NS}">'
        f'<s:Header/>'
        f'<s:Body>'
        f'<des:SolicitaDescargaEmitidos>'
        f'<des:solicitud{solicitud_attrs}>'
        f'{receptores_xml}'
        f'</des:solicitud>'
        f'</des:SolicitaDescargaEmitidos>'
        f'</s:Body>'
        f'</s:Envelope>'
    )

    body = _sign_envelope(envelope_xml, fiel, "SolicitaDescargaEmitidos")

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": SOAP_ACTIONS["solicita_descarga_emitidos"],
        "Authorization": f'WRAP access_token="{token}"',
    }

    resp_xml = make_request(
        url=ENDPOINTS["solicita_descarga"],
        body=body,
        headers=headers,
        operation="SolicitaDescargaEmitidos",
    )

    return _parse_request_id(resp_xml, "SolicitaDescargaEmitidosResult")


# ---------------------------------------------------------------------------
# Recibidos
# ---------------------------------------------------------------------------

def _solicitar_recibidos(
    fiel: FIEL,
    token: str,
    rfc_solicitante: str,
    fecha_inicio: date,
    fecha_fin: date,
    tipo_solicitud: str,
    rfc_emisor: Optional[str] = None,
    estado_comprobante: Optional[str] = None,
) -> str:
    """SolicitaDescargaRecibidos — CFDIs recibidos por rfc_solicitante."""
    fi = fecha_inicio.strftime("%Y-%m-%dT00:00:02")
    ff = fecha_fin.strftime("%Y-%m-%dT23:59:57")

    # EstadoComprobante va primero según documentación SAT v1.5
    solicitud_attrs = ""
    if estado_comprobante:
        solicitud_attrs += f' EstadoComprobante="{estado_comprobante}"'
    solicitud_attrs += (
        f' FechaInicial="{fi}"'
        f' FechaFinal="{ff}"'
        f' RfcSolicitante="{rfc_solicitante}"'
        f' RfcReceptor="{rfc_solicitante}"'
        f' TipoSolicitud="{tipo_solicitud}"'
    )
    if rfc_emisor:
        solicitud_attrs += f' RfcEmisor="{rfc_emisor}"'

    envelope_xml = (
        f'<s:Envelope xmlns:s="{_SOAP_NS}" xmlns:des="{_DES_NS}">'
        f'<s:Header/>'
        f'<s:Body>'
        f'<des:SolicitaDescargaRecibidos>'
        f'<des:solicitud'
        f'{solicitud_attrs}'
        f'/>'
        f'</des:SolicitaDescargaRecibidos>'
        f'</s:Body>'
        f'</s:Envelope>'
    )

    body = _sign_envelope(envelope_xml, fiel, "SolicitaDescargaRecibidos")

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": SOAP_ACTIONS["solicita_descarga_recibidos"],
        "Authorization": f'WRAP access_token="{token}"',
    }

    resp_xml = make_request(
        url=ENDPOINTS["solicita_descarga"],
        body=body,
        headers=headers,
        operation="SolicitaDescargaRecibidos",
    )

    return _parse_request_id(resp_xml, "SolicitaDescargaRecibidosResult")


# ---------------------------------------------------------------------------
# Firma enveloped (xmldsig) — el elemento firmado es el padre de solicitud
# ---------------------------------------------------------------------------

def _sign_envelope(envelope_xml: str, fiel: FIEL, operation_name: str) -> bytes:
    """
    Parsea el envelope, firma el elemento <des:{operation_name}> con
    xmldsig enveloped, y añade la Signature como hijo de <des:solicitud>.

    Según satcfdi: el elemento firmado es el PADRE de solicitud
    (SolicitaDescargaEmitidos / SolicitaDescargaRecibidos), y la
    Signature se appende como hijo de solicitud.
    """
    root = etree.fromstring(envelope_xml.encode())
    op_elem = root.find(f'.//{{{_DES_NS}}}{operation_name}')
    sol_elem = root.find(f'.//{{{_DES_NS}}}solicitud')

    # 1. C14N inclusiva del elemento operación (SolicitaDescargaEmitidos / Recibidos)
    #    Esto firma el contenido ANTES de agregar la Signature.
    op_c14n = _c14n_inclusive(op_elem)

    # 2. DigestValue
    digest = base64.b64encode(hashlib.sha1(op_c14n).digest()).decode()

    # 3. SignedInfo (inclusive C14N de SignedInfo para firmar)
    signed_info_xml = (
        f'<SignedInfo xmlns="{_XMLDSIG_NS}">'
        f'<CanonicalizationMethod Algorithm="http://www.w3.org/TR/2001/REC-xml-c14n-20010315"/>'
        f'<SignatureMethod Algorithm="http://www.w3.org/2000/09/xmldsig#rsa-sha1"/>'
        f'<Reference URI="">'
        f'<Transforms>'
        f'<Transform Algorithm="http://www.w3.org/2000/09/xmldsig#enveloped-signature"/>'
        f'</Transforms>'
        f'<DigestMethod Algorithm="http://www.w3.org/2000/09/xmldsig#sha1"/>'
        f'<DigestValue>{digest}</DigestValue>'
        f'</Reference>'
        f'</SignedInfo>'
    )

    si_elem = etree.fromstring(signed_info_xml.encode())
    si_c14n = _c14n_inclusive(si_elem)
    signature_value = fiel.sign_b64(si_c14n)

    # 4. Signature completa con X509Data
    signature_xml = (
        f'<Signature xmlns="{_XMLDSIG_NS}">'
        + signed_info_xml
        + f'<SignatureValue>{signature_value}</SignatureValue>'
        f'<KeyInfo>'
        f'<X509Data>'
        f'<X509IssuerSerial>'
        f'<X509IssuerName>{fiel.issuer_dn}</X509IssuerName>'
        f'<X509SerialNumber>{fiel.numero_serie}</X509SerialNumber>'
        f'</X509IssuerSerial>'
        f'<X509Certificate>{fiel.certificate_b64}</X509Certificate>'
        f'</X509Data>'
        f'</KeyInfo>'
        f'</Signature>'
    )

    # 5. Append Signature como hijo de solicitud (no del elemento operación)
    sig_elem = etree.fromstring(signature_xml.encode())
    sol_elem.append(sig_elem)

    return etree.tostring(root, encoding="utf-8", xml_declaration=False)


def _c14n_inclusive(elem) -> bytes:
    """C14N inclusiva (W3C Canonical XML) de un elemento."""
    buf = BytesIO()
    etree.ElementTree(elem).write_c14n(buf, exclusive=False, with_comments=False)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Parsing
# ---------------------------------------------------------------------------

def _parse_request_id(resp_xml: bytes, result_tag: str) -> str:
    """Extrae el IdSolicitud de la respuesta SOAP."""
    root = etree.fromstring(resp_xml)

    result = root.find(f".//{{{_DES_NS}}}{result_tag}")
    if result is None:
        raise RuntimeError(
            f"No se encontró {result_tag} en la respuesta:\n"
            f"{resp_xml.decode(errors='replace')}"
        )

    cod = result.get("CodEstatus", "")
    msg = result.get("Mensaje", "")
    id_solicitud = result.get("IdSolicitud", "")

    if not id_solicitud or cod not in ("5000", ""):
        raise RuntimeError(
            f"SAT rechazó la solicitud. CodEstatus={cod}, Mensaje={msg}"
        )

    return id_solicitud

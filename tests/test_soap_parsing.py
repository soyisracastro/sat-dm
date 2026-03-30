"""Tests para el parsing de respuestas SOAP del SAT (solicitud, verificacion, descarga)."""

import base64
import io
import zipfile

import pytest

from sat_descarga.solicitud import _parse_request_id
from sat_descarga.verificacion import _parse_estado, ESTADO_TERMINADA
from sat_descarga.descarga import _extraer_zip_del_response


_DES_NS = "http://DescargaMasivaTerceros.sat.gob.mx"


# ---------------------------------------------------------------------------
# Solicitud — _parse_request_id
# ---------------------------------------------------------------------------

class TestParseRequestId:

    def test_parse_emitidos_exitoso(self):
        xml = (
            f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<s:Body>'
            f'<SolicitaDescargaEmitidosResponse xmlns="{_DES_NS}">'
            f'<SolicitaDescargaEmitidosResult IdSolicitud="abc-123" '
            f'CodEstatus="5000" Mensaje="Solicitud Aceptada"/>'
            f'</SolicitaDescargaEmitidosResponse>'
            f'</s:Body></s:Envelope>'
        ).encode()

        result = _parse_request_id(xml, "SolicitaDescargaEmitidosResult")
        assert result == "abc-123"

    def test_parse_recibidos_exitoso(self):
        xml = (
            f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<s:Body>'
            f'<SolicitaDescargaRecibidosResponse xmlns="{_DES_NS}">'
            f'<SolicitaDescargaRecibidosResult IdSolicitud="xyz-789" '
            f'CodEstatus="5000" Mensaje="Solicitud Aceptada"/>'
            f'</SolicitaDescargaRecibidosResponse>'
            f'</s:Body></s:Envelope>'
        ).encode()

        result = _parse_request_id(xml, "SolicitaDescargaRecibidosResult")
        assert result == "xyz-789"

    def test_parse_rechazada(self):
        xml = (
            f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<s:Body>'
            f'<SolicitaDescargaEmitidosResponse xmlns="{_DES_NS}">'
            f'<SolicitaDescargaEmitidosResult IdSolicitud="" '
            f'CodEstatus="5002" Mensaje="Se han agotado las solicitudes"/>'
            f'</SolicitaDescargaEmitidosResponse>'
            f'</s:Body></s:Envelope>'
        ).encode()

        with pytest.raises(RuntimeError, match="5002"):
            _parse_request_id(xml, "SolicitaDescargaEmitidosResult")

    def test_parse_elemento_no_encontrado(self):
        xml = b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body/></s:Envelope>'
        with pytest.raises(RuntimeError, match="No se encontr"):
            _parse_request_id(xml, "SolicitaDescargaEmitidosResult")


# ---------------------------------------------------------------------------
# Verificacion — _parse_estado
# ---------------------------------------------------------------------------

class TestParseEstado:

    def _build_response(self, estado="3", cfdis="10", paquetes_xml=""):
        return (
            f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<s:Body>'
            f'<VerificaSolicitudDescargaResponse xmlns="{_DES_NS}">'
            f'<VerificaSolicitudDescargaResult CodEstatus="5000" '
            f'EstadoSolicitud="{estado}" CodigoEstadoSolicitud="5000" '
            f'NumeroCFDIs="{cfdis}" Mensaje="Solicitud Aceptada">'
            f'{paquetes_xml}'
            f'</VerificaSolicitudDescargaResult>'
            f'</VerificaSolicitudDescargaResponse>'
            f'</s:Body></s:Envelope>'
        ).encode()

    def test_estado_terminada_con_paquetes(self):
        paquetes = (
            f'<IdsPaquetes xmlns="{_DES_NS}">PKG-001</IdsPaquetes>'
            f'<IdsPaquetes xmlns="{_DES_NS}">PKG-002</IdsPaquetes>'
        )
        estado = _parse_estado(self._build_response("3", "50", paquetes))
        assert estado.cod_estado == ESTADO_TERMINADA
        assert estado.terminada is True
        assert estado.numero_cfdis == 50
        assert estado.package_ids == ["PKG-001", "PKG-002"]

    def test_estado_procesando(self):
        estado = _parse_estado(self._build_response("2", "0"))
        assert estado.cod_estado == "2"
        assert estado.terminada is False
        assert estado.package_ids == []

    def test_estado_sin_cfdis(self):
        estado = _parse_estado(self._build_response("3", "0"))
        assert estado.terminada is True
        assert estado.numero_cfdis == 0
        assert estado.package_ids == []

    def test_un_solo_paquete(self):
        paquetes = f'<IdsPaquetes xmlns="{_DES_NS}">UNICO-PKG</IdsPaquetes>'
        estado = _parse_estado(self._build_response("3", "5", paquetes))
        assert estado.package_ids == ["UNICO-PKG"]


# ---------------------------------------------------------------------------
# Descarga — _extraer_zip_del_response
# ---------------------------------------------------------------------------

class TestExtraerZip:

    def _create_zip_b64(self, files: dict[str, str]) -> str:
        """Crea un ZIP en memoria con los archivos dados y retorna Base64."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            for name, content in files.items():
                zf.writestr(name, content)
        return base64.b64encode(buf.getvalue()).decode()

    def _build_response(self, zip_b64: str) -> bytes:
        return (
            f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<s:Header>'
            f'<respuesta xmlns="{_DES_NS}" CodEstatus="5000" Mensaje="OK"/>'
            f'</s:Header>'
            f'<s:Body>'
            f'<RespuestaDescargaMasivaTercerosSalida xmlns="{_DES_NS}">'
            f'<Paquete>{zip_b64}</Paquete>'
            f'</RespuestaDescargaMasivaTercerosSalida>'
            f'</s:Body></s:Envelope>'
        ).encode()

    def test_extrae_zip_valido(self):
        zip_b64 = self._create_zip_b64({"factura.xml": "<cfdi/>"})
        resp = self._build_response(zip_b64)
        zip_bytes = _extraer_zip_del_response(resp, "test-pkg")

        # Verificar que es un ZIP válido
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        assert "factura.xml" in zf.namelist()
        assert zf.read("factura.xml") == b"<cfdi/>"

    def test_multiples_archivos(self):
        zip_b64 = self._create_zip_b64({
            "factura1.xml": "<cfdi>1</cfdi>",
            "factura2.xml": "<cfdi>2</cfdi>",
        })
        resp = self._build_response(zip_b64)
        zip_bytes = _extraer_zip_del_response(resp, "test-pkg")
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
        assert len(zf.namelist()) == 2

    def test_paquete_no_encontrado(self):
        resp = (
            f'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            f'<s:Body>'
            f'<RespuestaDescargaMasivaTercerosSalida xmlns="{_DES_NS}">'
            f'<respuestaDescarga CodEstatus="5004" Mensaje="No existe paquete"/>'
            f'</RespuestaDescargaMasivaTercerosSalida>'
            f'</s:Body></s:Envelope>'
        ).encode()
        with pytest.raises(RuntimeError, match="No se encontr"):
            _extraer_zip_del_response(resp, "pkg-no-existe")

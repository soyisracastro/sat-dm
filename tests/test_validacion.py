"""Tests para sat_descarga/validacion.py"""

import pytest
from unittest.mock import patch, MagicMock

from sat_descarga.validacion import (
    _build_soap_envelope,
    _parse_response,
    validar_cfdi,
    validar_masivo,
    EstadoCFDI,
)


class TestBuildSoapEnvelope:
    def test_envelope_contains_uuid(self):
        body = _build_soap_envelope(
            uuid="AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE",
            emisor_rfc="AAA010101AAA",
            receptor_rfc="BBB020202BBB",
            total=1234.56,
        )
        xml = body.decode("utf-8")
        assert "AAAAAAAA-BBBB-CCCC-DDDD-EEEEEEEEEEEE" in xml
        assert "AAA010101AAA" in xml
        assert "BBB020202BBB" in xml
        assert "1234.560000" in xml

    def test_total_formatted_6_decimals(self):
        body = _build_soap_envelope(
            uuid="X", emisor_rfc="X", receptor_rfc="X", total=100
        )
        assert b"100.000000" in body

    def test_soap_structure(self):
        body = _build_soap_envelope(
            uuid="X", emisor_rfc="X", receptor_rfc="X", total=0
        )
        xml = body.decode("utf-8")
        assert "soap:Envelope" in xml
        assert "soap:Body" in xml
        assert "Consulta" in xml
        assert "expresionImpresa" in xml
        assert "tempuri.org" in xml


class TestParseResponse:
    def test_vigente(self):
        xml = (
            b'<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            b'<s:Body>'
            b'<ConsultaResponse xmlns="http://tempuri.org/">'
            b'<ConsultaResult xmlns:a="http://schemas.datacontract.org/2004/07/Sat.Cfdi.Negocio.ConsultaCfdi.Servicio">'
            b'<a:CodigoEstatus>S - Comprobante obtenido satisfactoriamente.</a:CodigoEstatus>'
            b'<a:EsCancelable>Cancelable con aceptacion</a:EsCancelable>'
            b'<a:Estado>Vigente</a:Estado>'
            b'<a:EstatusCancelacion></a:EstatusCancelacion>'
            b'<a:ValidacionEFOS>200</a:ValidacionEFOS>'
            b'</ConsultaResult>'
            b'</ConsultaResponse>'
            b'</s:Body>'
            b'</s:Envelope>'
        )
        result = _parse_response(xml)
        assert result["estado"] == "Vigente"
        assert result["es_cancelable"] == "Cancelable con aceptacion"
        assert result["validacion_efos"] == "200"

    def test_cancelado(self):
        xml = b'<r><a:Estado>Cancelado</a:Estado><a:EsCancelable>No cancelable</a:EsCancelable></r>'
        result = _parse_response(xml)
        assert result["estado"] == "Cancelado"
        assert result["es_cancelable"] == "No cancelable"

    def test_no_encontrado(self):
        xml = b'<r><a:Estado>No existe</a:Estado></r>'
        result = _parse_response(xml)
        assert result["estado"] == "No Encontrado"

    def test_empty_response(self):
        xml = b'<r></r>'
        result = _parse_response(xml)
        assert result["estado"] == "No Encontrado"
        assert result["es_cancelable"] is None


class TestValidarCfdi:
    @patch("sat_descarga.validacion.make_request")
    def test_returns_estado_cfdi(self, mock_request):
        mock_request.return_value = (
            b'<r><a:Estado>Vigente</a:Estado>'
            b'<a:EsCancelable>Cancelable sin aceptacion</a:EsCancelable>'
            b'<a:EstatusCancelacion></a:EstatusCancelacion>'
            b'<a:ValidacionEFOS>200</a:ValidacionEFOS></r>'
        )
        result = validar_cfdi(
            uuid="TEST-UUID",
            emisor_rfc="AAA010101AAA",
            receptor_rfc="BBB020202BBB",
            total=1000.0,
        )
        assert isinstance(result, EstadoCFDI)
        assert result.uuid == "TEST-UUID"
        assert result.estado == "Vigente"
        assert result.es_cancelable == "Cancelable sin aceptacion"
        assert result.error is None

    @patch("sat_descarga.validacion.make_request")
    def test_handles_error(self, mock_request):
        mock_request.side_effect = RuntimeError("Connection failed")
        result = validar_cfdi(
            uuid="TEST-UUID",
            emisor_rfc="X",
            receptor_rfc="X",
            total=0,
        )
        assert result.estado == "Error"
        assert "Connection failed" in result.error


class TestValidarMasivo:
    @patch("sat_descarga.validacion.make_request")
    def test_multiple_cfdis(self, mock_request):
        mock_request.return_value = b'<r><a:Estado>Vigente</a:Estado></r>'

        cfdis = [
            {"uuid": f"UUID-{i}", "emisor_rfc": "A", "receptor_rfc": "B", "total": 100}
            for i in range(5)
        ]
        results = validar_masivo(cfdis, concurrency=2)
        assert len(results) == 5
        assert all(r.estado == "Vigente" for r in results)
        # Verificar que el orden se mantiene
        assert results[0].uuid == "UUID-0"
        assert results[4].uuid == "UUID-4"

    def test_empty_list(self):
        results = validar_masivo([])
        assert results == []

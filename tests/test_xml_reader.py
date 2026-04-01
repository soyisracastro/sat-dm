"""Tests para sat_descarga/xml_reader.py"""

import os
import pytest
import tempfile
from sat_descarga.xml_reader import leer_cfdi, leer_directorio, CfdiHeader


SAMPLE_CFDI_40 = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Serie="A"
    Folio="123"
    Fecha="2025-06-15T10:30:00"
    SubTotal="1000.00"
    Total="1160.00"
    Moneda="MXN"
    TipoDeComprobante="I">
    <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Empresa Emisora SA" RegimenFiscal="601"/>
    <cfdi:Receptor Rfc="BBB020202BBB" Nombre="Cliente Receptor SA" UsoCFDI="G03"/>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital
            UUID="12345678-ABCD-EFGH-IJKL-123456789012"
            FechaTimbrado="2025-06-15T10:31:00"
            RfcProvCertif="SAT970701NN3"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""


SAMPLE_CFDI_33 = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/3"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="3.3"
    Fecha="2024-01-10T08:00:00"
    SubTotal="500.00"
    Total="580.00"
    Moneda="USD"
    TipoDeComprobante="E">
    <cfdi:Emisor Rfc="CCC030303CCC" Nombre="Otra Empresa"/>
    <cfdi:Receptor Rfc="DDD040404DDD" Nombre="Otro Cliente"/>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital
            UUID="ABCDEFGH-1234-5678-9ABC-DEF012345678"
            FechaTimbrado="2024-01-10T08:01:00"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""


NOT_A_CFDI = """<?xml version="1.0"?><html><body>Not a CFDI</body></html>"""


@pytest.fixture
def cfdi_40_file(tmp_path):
    f = tmp_path / "cfdi_40.xml"
    f.write_text(SAMPLE_CFDI_40)
    return str(f)


@pytest.fixture
def cfdi_33_file(tmp_path):
    f = tmp_path / "cfdi_33.xml"
    f.write_text(SAMPLE_CFDI_33)
    return str(f)


@pytest.fixture
def not_cfdi_file(tmp_path):
    f = tmp_path / "not_cfdi.xml"
    f.write_text(NOT_A_CFDI)
    return str(f)


class TestLeerCfdi:
    def test_cfdi_40(self, cfdi_40_file):
        h = leer_cfdi(cfdi_40_file)
        assert isinstance(h, CfdiHeader)
        assert h.uuid == "12345678-ABCD-EFGH-IJKL-123456789012"
        assert h.version == "4.0"
        assert h.tipo_comprobante == "I"
        assert h.emisor_rfc == "AAA010101AAA"
        assert h.emisor_nombre == "Empresa Emisora SA"
        assert h.receptor_rfc == "BBB020202BBB"
        assert h.total == 1160.0
        assert h.moneda == "MXN"
        assert h.serie == "A"
        assert h.folio == "123"
        assert h.fecha_timbrado == "2025-06-15T10:31:00"

    def test_cfdi_33(self, cfdi_33_file):
        h = leer_cfdi(cfdi_33_file)
        assert h.uuid == "ABCDEFGH-1234-5678-9ABC-DEF012345678"
        assert h.version == "3.3"
        assert h.tipo_comprobante == "E"
        assert h.emisor_rfc == "CCC030303CCC"
        assert h.total == 580.0
        assert h.moneda == "USD"

    def test_not_cfdi_raises(self, not_cfdi_file):
        with pytest.raises(ValueError, match="No es un CFDI"):
            leer_cfdi(not_cfdi_file)


class TestLeerDirectorio:
    def test_reads_multiple(self, tmp_path):
        (tmp_path / "a.xml").write_text(SAMPLE_CFDI_40)
        (tmp_path / "b.xml").write_text(SAMPLE_CFDI_33)
        (tmp_path / "c.txt").write_text("not xml")
        (tmp_path / "d.xml").write_text(NOT_A_CFDI)

        headers = leer_directorio(str(tmp_path))
        assert len(headers) == 2
        uuids = {h.uuid for h in headers}
        assert "12345678-ABCD-EFGH-IJKL-123456789012" in uuids
        assert "ABCDEFGH-1234-5678-9ABC-DEF012345678" in uuids

    def test_recursive(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "a.xml").write_text(SAMPLE_CFDI_40)
        (sub / "b.xml").write_text(SAMPLE_CFDI_33)

        headers = leer_directorio(str(tmp_path), recursive=True)
        assert len(headers) == 2

    def test_non_recursive(self, tmp_path):
        sub = tmp_path / "subdir"
        sub.mkdir()
        (tmp_path / "a.xml").write_text(SAMPLE_CFDI_40)
        (sub / "b.xml").write_text(SAMPLE_CFDI_33)

        headers = leer_directorio(str(tmp_path), recursive=False)
        assert len(headers) == 1

    def test_empty_dir(self, tmp_path):
        headers = leer_directorio(str(tmp_path))
        assert headers == []

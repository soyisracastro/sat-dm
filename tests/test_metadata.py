"""Tests para sat_descarga/metadata.py"""

import pytest
from sat_descarga.metadata import parse_metadata_csv, MetadataCFDI


class TestParseMetadataCsv:
    def test_comma_delimited(self):
        csv_text = (
            "Uuid,RfcEmisor,NombreEmisor,RfcReceptor,NombreReceptor,"
            "RfcPac,FechaEmision,FechaCertificacionSat,Monto,"
            "EfectoComprobante,Estatus,FechaCancelacion\n"
            "ABC-123,AAA010101AAA,Empresa A,BBB020202BBB,Empresa B,"
            "PAC010101PAC,2025-01-15,2025-01-15,1500.00,"
            "Ingreso,Vigente,\n"
        )
        records = parse_metadata_csv(csv_text)
        assert len(records) == 1
        assert records[0].uuid == "ABC-123"
        assert records[0].rfc_emisor == "AAA010101AAA"
        assert records[0].nombre_emisor == "Empresa A"
        assert records[0].monto == "1500.00"
        assert records[0].estatus == "Vigente"
        assert records[0].fecha_cancelacion == ""

    def test_tilde_delimited(self):
        csv_text = (
            "Uuid~RfcEmisor~NombreEmisor~RfcReceptor~NombreReceptor~"
            "RfcPac~FechaEmision~FechaCertificacionSat~Monto~"
            "EfectoComprobante~Estatus~FechaCancelacion\n"
            "XYZ-789~CCC030303CCC~Empresa C~DDD040404DDD~Empresa D~"
            "PAC020202PAC~2025-03-01~2025-03-01~2500.50~"
            "Egreso~Cancelado~2025-04-01\n"
        )
        records = parse_metadata_csv(csv_text)
        assert len(records) == 1
        assert records[0].uuid == "XYZ-789"
        assert records[0].estatus == "Cancelado"
        assert records[0].fecha_cancelacion == "2025-04-01"

    def test_empty_csv(self):
        records = parse_metadata_csv("")
        assert records == []

    def test_header_only(self):
        csv_text = "Uuid,RfcEmisor,NombreEmisor\n"
        records = parse_metadata_csv(csv_text)
        assert records == []

    def test_multiple_records(self):
        lines = [
            "Uuid,RfcEmisor,NombreEmisor,RfcReceptor,NombreReceptor,"
            "RfcPac,FechaEmision,FechaCertificacionSat,Monto,"
            "EfectoComprobante,Estatus,FechaCancelacion"
        ]
        for i in range(10):
            lines.append(
                f"UUID-{i},RFC{i:03d},Nombre{i},RFCR{i:03d},NombreR{i},"
                f"PAC,2025-01-{i+1:02d},2025-01-{i+1:02d},{(i+1)*100:.2f},"
                f"Ingreso,Vigente,"
            )
        csv_text = "\n".join(lines)
        records = parse_metadata_csv(csv_text)
        assert len(records) == 10
        assert records[0].uuid == "UUID-0"
        assert records[9].uuid == "UUID-9"

    def test_blank_rows_ignored(self):
        csv_text = (
            "Uuid,RfcEmisor,Monto,Estatus\n"
            "A,B,100,Vigente\n"
            "\n"
            ",,,,\n"
            "C,D,200,Cancelado\n"
        )
        records = parse_metadata_csv(csv_text)
        assert len(records) == 2

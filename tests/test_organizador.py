"""Tests para sat_descarga/organizador.py"""

import pytest
from sat_descarga.organizador import (
    organizar,
    renombrar,
    eliminar_duplicados,
    agrupar_por_version_tipo,
)


SAMPLE_CFDI = """<?xml version="1.0" encoding="utf-8"?>
<cfdi:Comprobante
    xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
    Version="4.0"
    Fecha="2025-06-15T10:30:00"
    SubTotal="1000.00"
    Total="1160.00"
    Moneda="MXN"
    TipoDeComprobante="I">
    <cfdi:Emisor Rfc="AAA010101AAA" Nombre="Empresa A"/>
    <cfdi:Receptor Rfc="BBB020202BBB" Nombre="Cliente B"/>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital UUID="{uuid}" FechaTimbrado="2025-06-15T10:31:00"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""


def _create_cfdi(tmp_path, filename, uuid="12345678-AAAA-BBBB-CCCC-DDDDDDDDDDDD"):
    path = tmp_path / filename
    path.write_text(SAMPLE_CFDI.format(uuid=uuid))
    return path


class TestOrganizar:
    def test_organiza_por_rfc_anio_mes(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "factura1.xml")

        result = organizar(str(src), str(dst), "rfc_emisor/anio/mes")

        assert result.archivos_procesados == 1
        assert result.archivos_movidos == 1
        assert (dst / "AAA010101AAA" / "2025" / "06" / "factura1.xml").exists()

    def test_organiza_por_anio_mes(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "test.xml")

        result = organizar(str(src), str(dst), "anio/mes")
        assert (dst / "2025" / "06" / "test.xml").exists()

    def test_copiar_en_lugar_de_mover(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "test.xml")

        organizar(str(src), str(dst), "anio/mes", copiar=True)

        # Original sigue existiendo
        assert (src / "test.xml").exists()
        assert (dst / "2025" / "06" / "test.xml").exists()

    def test_estructura_invalida(self, tmp_path):
        with pytest.raises(ValueError, match="no válida"):
            organizar(str(tmp_path), str(tmp_path), "invalida/estructura")

    def test_omite_no_xml(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        (src / "readme.txt").write_text("not xml")

        result = organizar(str(src), str(dst), "anio/mes")
        assert result.archivos_procesados == 0


class TestRenombrar:
    def test_renombra_por_emisor_fecha_total(self, tmp_path):
        _create_cfdi(tmp_path, "original.xml")
        result = renombrar(str(tmp_path), "emisor_fecha_total")

        assert result.archivos_movidos == 1
        # Nuevo nombre: AAA010101AAA_2025-06-15_1160.00_12345678.xml
        files = list(tmp_path.glob("*.xml"))
        assert len(files) == 1
        assert "AAA010101AAA" in files[0].name
        assert "2025-06-15" in files[0].name

    def test_renombra_por_uuid(self, tmp_path):
        _create_cfdi(tmp_path, "test.xml", uuid="UNIQUE-UUID-1234-5678-ABCDEFABCDEF")
        renombrar(str(tmp_path), "uuid")

        files = list(tmp_path.glob("*.xml"))
        assert files[0].name == "UNIQUE-UUID-1234-5678-ABCDEFABCDEF.xml"

    def test_patron_invalido(self, tmp_path):
        with pytest.raises(ValueError, match="no válido"):
            renombrar(str(tmp_path), "patron_inventado")


class TestEliminarDuplicados:
    def test_elimina_duplicados(self, tmp_path):
        uuid = "SAME-UUID-1111-2222-333344445555"
        _create_cfdi(tmp_path, "first.xml", uuid=uuid)
        _create_cfdi(tmp_path, "second.xml", uuid=uuid)

        result = eliminar_duplicados(str(tmp_path))
        assert result.archivos_analizados == 2
        assert result.duplicados_encontrados == 1
        assert result.duplicados_eliminados == 1

        # Solo queda 1 archivo
        xml_files = list(tmp_path.glob("*.xml"))
        assert len(xml_files) == 1

    def test_dry_run(self, tmp_path):
        uuid = "SAME-UUID-1111-2222-333344445555"
        _create_cfdi(tmp_path, "first.xml", uuid=uuid)
        _create_cfdi(tmp_path, "second.xml", uuid=uuid)

        result = eliminar_duplicados(str(tmp_path), dry_run=True)
        assert result.duplicados_encontrados == 1
        assert result.duplicados_eliminados == 0

        # Ambos siguen existiendo
        xml_files = list(tmp_path.glob("*.xml"))
        assert len(xml_files) == 2

    def test_sin_duplicados(self, tmp_path):
        _create_cfdi(tmp_path, "a.xml", uuid="UUID-AAAA-1111-2222-333333333333")
        _create_cfdi(tmp_path, "b.xml", uuid="UUID-BBBB-1111-2222-333333333333")

        result = eliminar_duplicados(str(tmp_path))
        assert result.duplicados_encontrados == 0
        assert len(list(tmp_path.glob("*.xml"))) == 2


class TestAgruparPorVersionTipo:
    def test_agrupa(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "test.xml")

        result = agrupar_por_version_tipo(str(src), str(dst))
        assert result.archivos_movidos == 1
        assert (dst / "v4.0" / "Ingreso" / "test.xml").exists()

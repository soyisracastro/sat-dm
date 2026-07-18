"""Tests para sat_descarga/organizador.py"""

import pytest
from sat_descarga.utils.organizador import (
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
    <cfdi:Emisor Rfc="{emisor}" Nombre="Empresa emisora"/>
    <cfdi:Receptor Rfc="{receptor}" Nombre="Empresa receptora"/>
    <cfdi:Complemento>
        <tfd:TimbreFiscalDigital UUID="{uuid}" FechaTimbrado="2025-06-15T10:31:00"/>
    </cfdi:Complemento>
</cfdi:Comprobante>"""


def _create_cfdi(
    tmp_path,
    filename,
    uuid="12345678-AAAA-BBBB-CCCC-DDDDDDDDDDDD",
    emisor="AAA010101AAA",
    receptor="BBB020202BBB",
):
    path = tmp_path / filename
    path.write_text(SAMPLE_CFDI.format(uuid=uuid, emisor=emisor, receptor=receptor))
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


class TestEstructuraCustom:
    """Estructuras compuestas por tokens (feature 'Personalizada')."""

    def test_custom_completa_emitidos(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "factura.xml")

        # El RFC de la empresa es el emisor → Emitidos
        result = organizar(
            str(src), str(dst), "rfc/anio/mes/flujo/tipo", rfc="AAA010101AAA"
        )

        assert result.archivos_movidos == 1
        assert (
            dst / "AAA010101AAA" / "2025" / "06" / "Emitidos" / "Ingreso" / "factura.xml"
        ).exists()

    def test_flujo_recibidos(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "factura.xml")

        organizar(str(src), str(dst), "anio/mes/flujo", rfc="bbb020202bbb")

        # Comparación case-insensitive: el RFC de la empresa es el receptor
        assert (dst / "2025" / "06" / "Recibidos" / "factura.xml").exists()

    def test_ningun_xml_de_la_empresa_no_organiza(self, tmp_path):
        # La empresa no es emisor ni receptor de NINGÚN XML: no se organiza
        # nada y se pide activar la empresa correcta (nunca carpeta "Otros").
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "factura.xml")

        with pytest.raises(ValueError, match="empresa activa"):
            organizar(str(src), str(dst), "flujo", rfc="ZZZ999999ZZZ")

        # El origen queda intacto y no se creó nada en el destino
        assert (src / "factura.xml").exists()
        assert not (dst / "Otros").exists()

    def test_carpeta_mixta_omite_otros_rfc(self, tmp_path):
        # Facturas de la empresa + facturas de otro RFC: las suyas se
        # organizan, las ajenas se quedan en su lugar y se reportan.
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "mia.xml", uuid="UUID-0001-AAAA-BBBB-CCCCCCCCCCCC")
        _create_cfdi(
            src, "ajena.xml",
            uuid="UUID-0002-AAAA-BBBB-CCCCCCCCCCCC",
            emisor="XXX111111XX1", receptor="YYY222222YY2",
        )

        result = organizar(str(src), str(dst), "anio/mes/flujo", rfc="AAA010101AAA")

        assert result.archivos_movidos == 1
        assert result.de_otro_rfc == 1
        assert result.archivos_omitidos == 1
        assert (dst / "2025" / "06" / "Emitidos" / "mia.xml").exists()
        assert (src / "ajena.xml").exists()  # no se tocó
        assert not (dst / "2025" / "06" / "Otros").exists()

    def test_autofactura_cuenta_como_emitida(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "auto.xml", emisor="AAA010101AAA", receptor="AAA010101AAA")

        organizar(str(src), str(dst), "flujo", rfc="AAA010101AAA")

        assert (dst / "Emitidos" / "auto.xml").exists()

    def test_rfc_o_flujo_sin_rfc_falla(self, tmp_path):
        with pytest.raises(ValueError, match="RFC de la empresa"):
            organizar(str(tmp_path), str(tmp_path), "anio/flujo")
        with pytest.raises(ValueError, match="RFC de la empresa"):
            organizar(str(tmp_path), str(tmp_path), "rfc/anio")

    def test_plano_no_combina(self, tmp_path):
        with pytest.raises(ValueError, match="no válida"):
            organizar(str(tmp_path), str(tmp_path), "plano/anio")

    def test_estructura_vacia(self, tmp_path):
        with pytest.raises(ValueError, match="no válida"):
            organizar(str(tmp_path), str(tmp_path), "")
        with pytest.raises(ValueError, match="no válida"):
            organizar(str(tmp_path), str(tmp_path), "anio//mes")

    def test_texto_literal(self, tmp_path):
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        _create_cfdi(src, "factura.xml")

        organizar(str(src), str(dst), "txt:Facturas/anio/txt:CFDI")

        assert (dst / "Facturas" / "2025" / "CFDI" / "factura.xml").exists()

    def test_texto_literal_vacio_falla(self, tmp_path):
        with pytest.raises(ValueError, match="no válida"):
            organizar(str(tmp_path), str(tmp_path), "anio/txt:")


class TestDestinoDentroDelOrigen:
    """El walk no debe releer la salida de corridas previas."""

    def test_segunda_corrida_no_relee_lo_organizado(self, tmp_path):
        src = tmp_path / "xmls"
        dst = src / "Ordenado"  # destino DENTRO del origen (caso común en la UI)
        src.mkdir()
        _create_cfdi(src, "factura.xml")

        r1 = organizar(str(src), str(dst), "anio/mes", copiar=True)
        assert r1.archivos_procesados == 1
        assert (dst / "2025" / "06" / "factura.xml").exists()

        # Segunda corrida: la copia dentro de Ordenado/ NO se vuelve a procesar
        r2 = organizar(str(src), str(dst), "anio/mes", copiar=True)
        assert r2.archivos_procesados == 1  # solo el original
        assert r2.archivos_movidos == 0     # el destino ya existía → omitido
        assert r2.archivos_omitidos == 1

    def test_flujo_no_rebota_entre_corridas(self, tmp_path):
        # Escenario del bug reportado: organizar con flujo dejaba salida que la
        # siguiente corrida (otra empresa) releía y volvía a mover/copiar.
        src = tmp_path / "xmls"
        dst = src / "Ordenado"
        src.mkdir()
        _create_cfdi(
            src, "a.xml", uuid="UUID-A-1",
            emisor="AAA010101AAA", receptor="CCC333333CC3",
        )
        _create_cfdi(
            src, "b.xml", uuid="UUID-B-1",
            emisor="XXX111111XX1", receptor="BBB020202BBB",
        )

        r1 = organizar(str(src), str(dst), "anio/mes/flujo", rfc="AAA010101AAA", copiar=True)
        assert r1.archivos_movidos == 1
        assert r1.de_otro_rfc == 1

        # Corrida para la otra empresa: procesa solo los 2 originales (no la
        # salida de la corrida 1) y organiza el que le pertenece.
        r2 = organizar(str(src), str(dst), "anio/mes/flujo", rfc="BBB020202BBB", copiar=True)
        assert r2.archivos_procesados == 2
        assert r2.archivos_movidos == 1
        assert r2.de_otro_rfc == 1
        assert (dst / "2025" / "06" / "Emitidos" / "a.xml").exists()
        assert (dst / "2025" / "06" / "Recibidos" / "b.xml").exists()


class TestSanearSegmento:
    def test_sanea_chars_invalidos(self):
        from sat_descarga.utils.organizador import _sanear_segmento

        assert _sanear_segmento('A<B>:C"D|E?F*G') == "A_B__C_D_E_F_G"
        assert _sanear_segmento("normal") == "normal"
        # Windows no permite puntos/espacios al final
        assert _sanear_segmento("carpeta. ") == "carpeta"

    def test_vacio_es_sin_dato(self):
        from sat_descarga.utils.organizador import _sanear_segmento

        assert _sanear_segmento("") == "SIN_DATO"
        assert _sanear_segmento(None) == "SIN_DATO"
        assert _sanear_segmento("   ") == "SIN_DATO"


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

    def test_renombra_por_partes(self, tmp_path):
        _create_cfdi(tmp_path, "original.xml", uuid="A1B2C3D4-AAAA-BBBB-CCCC-DDDDDDDDDDDD")

        result = renombrar(
            tmp_path.as_posix(),
            partes=["fecha", "rfc_emisor", "folio_fiscal"],
            separador="-",
        )

        assert result.archivos_movidos == 1
        files = list(tmp_path.glob("*.xml"))
        assert files[0].name == "2025-06-15-AAA010101AAA-A1B2C3D4.xml"

    def test_renombra_partes_con_texto_y_separador(self, tmp_path):
        _create_cfdi(tmp_path, "x.xml")

        renombrar(tmp_path.as_posix(), partes=["txt:CFDI", "total"], separador="_")

        files = list(tmp_path.glob("*.xml"))
        assert files[0].name == "CFDI_1160.00.xml"

    def test_partes_invalidas(self, tmp_path):
        with pytest.raises(ValueError, match="no válidas"):
            renombrar(str(tmp_path), partes=["fecha", "inventada"])
        with pytest.raises(ValueError, match="no válidas"):
            renombrar(str(tmp_path), partes=[])


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

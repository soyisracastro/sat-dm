"""Tests del parser de la Constancia de Situación Fiscal (capa pura).

Las fixtures emulan la salida cruda de pdfplumber (celdas con saltos de línea
y None) — NO se usan PDFs reales porque contienen datos personales.
"""

import pytest

from sat_descarga.utils.csf_parser import parsear_contenido_csf
from sat_descarga.utils.regimenes_fiscales import clave_de_regimen


def _cedula(rfc: str, *lineas_nombre: str) -> list:
    """Tabla del bloque QR de la página 1 (celda multilínea)."""
    contenido = "\n".join([
        rfc,
        "Registro Federal de Contribuyentes",
        *lineas_nombre,
        "Nombre, denominación o razón",
        "social",
        "idCIF: 14080809903",
        "VALIDA TU INFORMACIÓN",
        "FISCAL",
    ])
    return [["CÉDULA DE IDENTIFICACIÓN FISCAL"], [contenido]]


def _tabla_regimenes(*filas) -> list:
    return [["Regímenes:", None, None],
            ["Régimen", "Fecha Inicio", "Fecha Fin"],
            *filas]


def _tabla_actividades(*filas) -> list:
    return [["Actividades Económicas:", None, None, None, None],
            ["Orden", "Actividad Económica", "Porcentaje", "Fecha Inicio", "Fecha Fin"],
            *filas]


TABLAS_PM = [
    _cedula("SAJ0205248A9", "SUPERSERVICIO AJUCHITLAN"),
    [["Datos de Identificación del Contribuyente:", None],
     ["RFC:", "SAJ0205248A9"],
     ["Denominación/Razón Social:", "SUPERSERVICIO AJUCHITLAN"],
     ["Régimen Capital:", "SOCIEDAD ANONIMA DE CAPITAL VARIABLE"]],
    _tabla_actividades(
        ["2", "Comercio al por menor de gasolina y diésel", "99", "24/05/2002", ""],
        ["2", "Comercio al por menor de aceites y grasas lubricantes de uso industrial, aditivos y\nsimilares para vehículos de motor", "1", "31/07/2025", ""],
    ),
    _tabla_regimenes(
        ["Régimen General de Ley Personas Morales", "31/03/2002", ""],
    ),
]

TABLAS_PF = [
    _cedula("MUVO970228GVA", "OMAR ANDRES MURGUIA", "VILLAFUERTE"),
    [["Datos de Identificación del Contribuyente:", None],
     ["RFC:", "MUVO970228GVA"],
     ["CURP:", "MUVO970228HCMRLM07"],
     ["Nombre (s):", "OMAR ANDRES"],
     ["Primer Apellido:", "MURGUIA"],
     ["Segundo Apellido:", "VILLAFUERTE"]],
    _tabla_actividades(
        ["1", "Instalaciones eléctricas en construcciones", "100", "15/08/2025", ""],
    ),
    _tabla_regimenes(
        ["Régimen Simplificado de Confianza", "15/08/2025", ""],
    ),
]


class TestPersonaMoral:

    def test_nombre_y_tipo(self):
        datos = parsear_contenido_csf("", TABLAS_PM)
        assert datos.nombre == "SUPERSERVICIO AJUCHITLAN"
        assert datos.tipo_persona == "PM"
        assert datos.rfc == "SAJ0205248A9"

    def test_regimen_mapeado_al_catalogo(self):
        datos = parsear_contenido_csf("", TABLAS_PM)
        assert [(r.clave, r.descripcion) for r in datos.regimenes] == [
            ("601", "Régimen General de Ley Personas Morales"),
        ]

    def test_actividades_ordenadas_con_principal(self):
        datos = parsear_contenido_csf("", TABLAS_PM)
        assert len(datos.actividades) == 2
        primera, segunda = datos.actividades
        assert primera.porcentaje == 99 and primera.principal is True
        assert segunda.porcentaje == 1 and segunda.principal is False
        # La celda multilínea se normaliza a una sola línea con espacios.
        assert segunda.descripcion == (
            "Comercio al por menor de aceites y grasas lubricantes de uso "
            "industrial, aditivos y similares para vehículos de motor"
        )

    def test_nombre_fallback_sin_cedula(self):
        # Sin el bloque QR, el nombre sale de Denominación/Razón Social.
        datos = parsear_contenido_csf("", TABLAS_PM[1:])
        assert datos.nombre == "SUPERSERVICIO AJUCHITLAN"
        assert datos.tipo_persona == "PM"


class TestPersonaFisica:

    def test_nombre_concatenado_desde_cedula(self):
        datos = parsear_contenido_csf("", TABLAS_PF)
        assert datos.nombre == "OMAR ANDRES MURGUIA VILLAFUERTE"
        assert datos.tipo_persona == "PF"
        assert datos.rfc == "MUVO970228GVA"

    def test_resico_y_actividad_unica(self):
        datos = parsear_contenido_csf("", TABLAS_PF)
        assert [r.clave for r in datos.regimenes] == ["626"]
        assert len(datos.actividades) == 1
        assert datos.actividades[0].porcentaje == 100
        assert datos.actividades[0].principal is True

    def test_nombre_fallback_desde_filas_identificacion(self):
        datos = parsear_contenido_csf("", TABLAS_PF[1:])
        assert datos.nombre == "OMAR ANDRES MURGUIA VILLAFUERTE"

    def test_sin_segundo_apellido(self):
        tablas = [[["RFC:", "XAXX010101ABC"],
                   ["CURP:", "XAXX010101HDFRRL01"],
                   ["Nombre (s):", "MARIA"],
                   ["Primer Apellido:", "LOPEZ"],
                   ["Segundo Apellido:", ""]],
                  _tabla_regimenes(["Régimen Simplificado de Confianza", "01/01/2022", ""])]
        datos = parsear_contenido_csf("", tablas)
        assert datos.nombre == "MARIA LOPEZ"
        assert datos.tipo_persona == "PF"

    def test_etiquetas_sin_espacios(self):
        # Con la tolerancia default pdfplumber pega las etiquetas ("Nombre(s):");
        # el matching debe seguir funcionando.
        tablas = [[["RFC:", "XAXX010101ABC"],
                   ["Nombre(s):", "MARIA"],
                   ["PrimerApellido:", "LOPEZ"],
                   ["SegundoApellido:", "GOMEZ"]],
                  _tabla_regimenes(["Régimen Simplificado de Confianza", "01/01/2022", ""])]
        datos = parsear_contenido_csf("", tablas)
        assert datos.nombre == "MARIA LOPEZ GOMEZ"


class TestReglasDeSeccion:

    def test_regimen_concluido_se_excluye(self):
        tablas = [_cedula("CAUI890921DAA", "ISRAEL CASTRO URIETA"),
                  _tabla_regimenes(
                      ["Régimen de Incorporación Fiscal", "01/01/2015", "31/12/2021"],
                      ["Régimen Simplificado de Confianza", "01/01/2022", ""],
                  )]
        datos = parsear_contenido_csf("", tablas)
        assert [r.clave for r in datos.regimenes] == ["626"]

    def test_actividad_concluida_se_excluye(self):
        tablas = [_cedula("CAUI890921DAA", "ISRAEL CASTRO URIETA"),
                  _tabla_actividades(
                      ["1", "Comercio anterior", "50", "01/01/2010", "31/12/2020"],
                      ["1", "Servicios de contabilidad y auditoría", "100", "01/01/2021", ""],
                  )]
        datos = parsear_contenido_csf("", tablas)
        assert [a.descripcion for a in datos.actividades] == [
            "Servicios de contabilidad y auditoría",
        ]

    def test_porcentaje_no_numerico_ordena_al_final(self):
        tablas = [_cedula("CAUI890921DAA", "ISRAEL CASTRO URIETA"),
                  _tabla_actividades(
                      ["1", "Sin porcentaje", "N/A", "01/01/2021", ""],
                      ["2", "Con porcentaje", "40", "01/01/2021", ""],
                  )]
        datos = parsear_contenido_csf("", tablas)
        assert datos.actividades[0].descripcion == "Con porcentaje"
        assert datos.actividades[0].principal is True
        assert datos.actividades[1].porcentaje is None

    def test_tablas_multipagina_se_concatenan(self):
        # La tabla continúa en la página siguiente repitiendo su encabezado.
        tablas = [_cedula("CAUI890921DAA", "ISRAEL CASTRO URIETA"),
                  _tabla_actividades(["1", "Asalariado", "75", "01/07/2021", ""]),
                  _tabla_actividades(["1", "Servicios de contabilidad y auditoría", "25", "01/08/2009", ""])]
        datos = parsear_contenido_csf("", tablas)
        assert [a.porcentaje for a in datos.actividades] == [75, 25]
        assert [a.principal for a in datos.actividades] == [True, False]

    def test_empate_de_porcentaje_conserva_orden_sat(self):
        tablas = [_cedula("CAUI890921DAA", "ISRAEL CASTRO URIETA"),
                  _tabla_actividades(
                      ["1", "Primera del SAT", "50", "01/01/2021", ""],
                      ["2", "Segunda del SAT", "50", "01/01/2021", ""],
                  )]
        datos = parsear_contenido_csf("", tablas)
        assert [a.descripcion for a in datos.actividades] == [
            "Primera del SAT", "Segunda del SAT",
        ]

    def test_regimen_desconocido_queda_sin_clave(self):
        tablas = [_cedula("SAJ0205248A9", "SUPERSERVICIO AJUCHITLAN"),
                  _tabla_regimenes(["Régimen Hipotético del Futuro", "01/01/2030", ""])]
        datos = parsear_contenido_csf("", tablas)
        assert len(datos.regimenes) == 1
        assert datos.regimenes[0].clave == ""
        assert datos.regimenes[0].descripcion == "Régimen Hipotético del Futuro"


class TestCasosBorde:

    def test_pdf_que_no_es_csf(self):
        with pytest.raises(ValueError):
            parsear_contenido_csf("factura cualquiera", [[["Total:", "$100.00"]]])

    def test_tipo_por_longitud_de_rfc(self):
        # Sin filas de identificación PF/PM, el tipo sale del largo del RFC.
        datos = parsear_contenido_csf(
            "RFC: SAJ0205248A9",
            [_cedula("SAJ0205248A9", "SUPERSERVICIO AJUCHITLAN")],
        )
        assert datos.tipo_persona == "PM"
        datos = parsear_contenido_csf(
            "RFC: MUVO970228GVA",
            [_cedula("MUVO970228GVA", "OMAR ANDRES MURGUIA", "VILLAFUERTE")],
        )
        assert datos.tipo_persona == "PF"


class TestClaveDeRegimen:

    @pytest.mark.parametrize("descripcion,clave", [
        # Tal cual la CSF los imprime (corpus real 2026).
        ("Régimen General de Ley Personas Morales", "601"),
        ("Régimen Simplificado de Confianza", "626"),
        ("Régimen de Sueldos y Salarios e Ingresos Asimilados a Salarios", "605"),
        ("Régimen de Ingresos por Dividendos (socios y accionistas)", "611"),
        ("Régimen de las Personas Físicas con Actividades Empresariales y Profesionales", "612"),
        ("Régimen de Incorporación Fiscal", "621"),
        ("Régimen de Arrendamiento", "606"),
        ("Régimen de los Ingresos por Obtención de Premios", "615"),
        # Tolerancia a acentos/mayúsculas perdidos.
        ("REGIMEN SIMPLIFICADO DE CONFIANZA", "626"),
        ("regimen general de ley personas morales", "601"),
        # Sin el prefijo "Régimen …" (como viene en el catálogo).
        ("General de Ley Personas Morales", "601"),
        ("Sueldos y Salarios e Ingresos Asimilados a Salarios", "605"),
    ])
    def test_matching_tolerante(self, descripcion, clave):
        assert clave_de_regimen(descripcion) == clave

    def test_desconocido_devuelve_none(self):
        assert clave_de_regimen("Régimen Hipotético del Futuro") is None
        assert clave_de_regimen("") is None

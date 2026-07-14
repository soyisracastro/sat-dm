"""Tests del parser de la Opinión de Cumplimiento 32-D (capa pura).

Fixtures de texto sintético que emulan la salida de pdfplumber — NO se usan PDFs
reales (traen datos personales y no se commitean).
"""

import pytest

from sat_descarga.utils.opinion_parser import parsear_contenido_opinion


def _cadena(rfc: str, folio: str, letra: str) -> str:
    return f"Cadena Original\n||{rfc}|{folio}|30-05-2026|{letra}||00001088888800000031||"


OPINION_POSITIVA = f"""Opinión del cumplimiento de obligaciones fiscales
Nombre, denominación o razón social Sentido
FERNANDO GUZMAN PINEDA POSITIVO
RFC Folio
GUPF620405TD8 26ND5007756
Se le informa que ... se encuentra al corriente en los puntos que revisa la opinión ...
Información importante
MarcaSAT ...
{_cadena("GUPF620405TD8", "26ND5007756", "P")}
"""

OPINION_NEGATIVA = f"""Opinión del cumplimiento de obligaciones fiscales
Nombre, denominación o razón social Sentido
ISRAEL CASTRO URIETA NEGATIVO
RFC Folio
CAUI890921DAA 26ND5008217
Se le informa que ... se detectan inconsistencias u omisiones ..., las cuales se detallan a continuación:
Créditos fiscales
Se ubican los siguientes créditos fiscales firmes o no garantizados a su cargo:
234910013510
Cumplimiento de obligaciones
Se detectan omisiones en la presentación de las siguientes obligaciones que tiene registradas:
Pago provisional mensual de ISR por servicios profesionales. Régimen de Actividades Empresariales y Profesionales
Ejercicio 2022
Febrero | Marzo | Abril | Mayo | Junio | Julio
Información importante
Si no estás de acuerdo ...
{_cadena("CAUI890921DAA", "26ND5008217", "N")}
"""


class TestSentido:

    def test_positiva(self):
        d = parsear_contenido_opinion(OPINION_POSITIVA)
        assert d.sentido == "positiva"
        assert d.rfc == "GUPF620405TD8"
        assert d.folio == "26ND5007756"
        assert d.motivos == []

    def test_negativa(self):
        d = parsear_contenido_opinion(OPINION_NEGATIVA)
        assert d.sentido == "negativa"
        assert d.rfc == "CAUI890921DAA"

    def test_letra_desconocida_es_otro(self):
        texto = "Opinión del cumplimiento de obligaciones fiscales\n" + _cadena(
            "XAXX010101ABC", "26ND0000001", "S"
        )
        assert parsear_contenido_opinion(texto).sentido == "otro"

    def test_fallback_por_texto_sin_cadena_legible(self):
        # Formato viejo cuya cadena no parsea: cae al texto "en sentido NEGATIVO".
        texto = ("Opinión del cumplimiento de obligaciones fiscales\n"
                 "Por lo que se emite esta opinión ... en sentido NEGATIVO.")
        assert parsear_contenido_opinion(texto).sentido == "negativa"


class TestMotivos:

    def test_secciones_titulo_descripcion_detalles(self):
        d = parsear_contenido_opinion(OPINION_NEGATIVA)
        assert [m.titulo for m in d.motivos] == [
            "Créditos fiscales", "Cumplimiento de obligaciones",
        ]
        creditos, obligaciones = d.motivos
        assert creditos.descripcion.startswith("Se ubican los siguientes créditos")
        assert creditos.detalles == ["234910013510"]
        assert obligaciones.descripcion.startswith("Se detectan omisiones")
        assert obligaciones.detalles == [
            "Pago provisional mensual de ISR por servicios profesionales. "
            "Régimen de Actividades Empresariales y Profesionales",
            "Ejercicio 2022",
            "Febrero | Marzo | Abril | Mayo | Junio | Julio",
        ]

    def test_positiva_no_tiene_motivos(self):
        assert parsear_contenido_opinion(OPINION_POSITIVA).motivos == []

    def test_seccion_desconocida_agnostica(self):
        # Una razón NO documentada (buzón, localización, etc.) igual se refleja:
        # el encabezado se detecta porque le sigue la frase "Se ...".
        texto = f"""Opinión del cumplimiento de obligaciones fiscales
Se le informa que ..., las cuales se detallan a continuación:
Buzón Tributario
Se detecta que el buzón tributario no tiene medios de contacto habilitados.
Información importante
{_cadena("XAXX010101ABC", "26ND0000002", "N")}
"""
        d = parsear_contenido_opinion(texto)
        assert d.sentido == "negativa"
        assert len(d.motivos) == 1
        assert d.motivos[0].titulo == "Buzón Tributario"
        assert d.motivos[0].descripcion.startswith("Se detecta que el buzón")

    def test_encabezado_conocido_sin_frase_introductoria(self):
        # Sección conocida cuyo cuerpo va directo al detalle (sin "Se ...").
        texto = f"""Opinión del cumplimiento de obligaciones fiscales
..., las cuales se detallan a continuación:
Créditos fiscales
234910013510
Información importante
{_cadena("XAXX010101ABC", "26ND0000003", "N")}
"""
        d = parsear_contenido_opinion(texto)
        assert [m.titulo for m in d.motivos] == ["Créditos fiscales"]
        assert d.motivos[0].detalles == ["234910013510"]


class TestCasosBorde:

    def test_pdf_que_no_es_opinion(self):
        with pytest.raises(ValueError):
            parsear_contenido_opinion("Factura cualquiera\nTotal: $100.00")

    def test_titulo_sin_cadena_sigue_siendo_valido(self):
        # Con el título pero sin cadena ni sentido → válido, sentido vacío.
        d = parsear_contenido_opinion(
            "Opinión del cumplimiento de obligaciones fiscales\nContenido raro"
        )
        assert d.sentido == ""
        assert d.motivos == []

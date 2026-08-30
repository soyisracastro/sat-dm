"""Tests del envío de contabilidad electrónica (lógica pura, sin browser).

El flujo con Playwright no se prueba e2e (convención del repo): se prueban los
helpers puros — inspección de ZIPs del Anexo 24, parseo del grid de acuses,
los regexes que clasifican mensajes del portal y el predicado de estado
terminal — más la superficie del CLI en test_cli_contabilidad.py.
"""

import zipfile

import pytest

from sat_descarga.portal.contabilidad_electronica import (
    RE_ERROR_TRANSITORIO,
    RE_FECHA_ACUSE,
    RE_FOLIO,
    RE_NOMBRE_ZIP,
    _limpiar_html,
    es_estado_terminal,
    inspeccionar_zip,
    inventario,
    parsear_grid_acuses,
)

# ---------------------------------------------------------------------------
# armado de ZIPs de prueba
# ---------------------------------------------------------------------------

XML_BALANZA = (
    '<?xml version="1.0"?>\n'
    '<BCE:Balanza Version="1.3" RFC="{rfc}" Mes="{mes}" Anio="{anio}" '
    'TipoEnvio="N" xmlns:BCE="http://www.sat.gob.mx/esquemas/ContabilidadE/'
    '1_3/BalanzaComprobacion">'
    '<BCE:Ctas NumCta="100-01" SaldoIni="1.0" Debe="0.0" Haber="0.0" '
    'SaldoFin="1.0"/></BCE:Balanza>'
)
XML_CATALOGO = (
    '<?xml version="1.0"?>\n'
    '<catalogocuentas:Catalogo Version="1.3" RFC="{rfc}" Mes="{mes}" '
    'Anio="{anio}" xmlns:catalogocuentas="http://www.sat.gob.mx/esquemas/'
    'ContabilidadE/1_3/CatalogoCuentas">'
    '<catalogocuentas:Ctas CodAgrup="100" NumCta="100-01" Desc="Caja" '
    'Nivel="1" Natur="D"/></catalogocuentas:Catalogo>'
)


def _zip(tmp_path, nombre, contenido_xml=None, *, interno=None, extras=()):
    """Crea `nombre`.zip con un XML adentro (nombre interno = el del ZIP)."""
    path = tmp_path / nombre
    with zipfile.ZipFile(path, "w") as zf:
        if contenido_xml is not None:
            zf.writestr(interno or (path.stem + ".xml"), contenido_xml)
        for nombre_extra, cuerpo in extras:
            zf.writestr(nombre_extra, cuerpo)
    return path


def _balanza(tmp_path, rfc="SSA980330HU1", anio="2026", mes="01", **kw):
    nombre = f"{rfc}{anio}{mes}BN.zip"
    xml = XML_BALANZA.format(rfc=rfc, anio=anio, mes=mes)
    return _zip(tmp_path, nombre, xml, **kw)


# ---------------------------------------------------------------------------
# inspeccionar_zip
# ---------------------------------------------------------------------------

def test_zip_valido(tmp_path):
    info = inspeccionar_zip(_balanza(tmp_path))
    assert info["problemas"] == []
    assert info["rfc"] == "SSA980330HU1"
    assert info["anio"] == "2026"
    assert info["mes"] == "01"
    assert info["tipo"] == "BN"
    assert info["raiz"] == "Balanza"
    assert info["version"] == "1.3"


def test_nombre_fuera_de_nomenclatura(tmp_path):
    info = inspeccionar_zip(_zip(tmp_path, "2025.zip", XML_BALANZA.format(
        rfc="X", anio="2025", mes="01")))
    assert any("nomenclatura" in p for p in info["problemas"])


def test_xml_no_cuadra_con_el_nombre(tmp_path):
    # el nombre dice 2026-01 pero el XML trae otro RFC, año y mes
    xml = XML_BALANZA.format(rfc="SAJ0205248A9", anio="2025", mes="03")
    info = inspeccionar_zip(_zip(tmp_path, "SSA980330HU1202601BN.zip", xml))
    textos = " ".join(info["problemas"])
    assert "RFC" in textos and "Anio" in textos and "Mes" in textos


def test_catalogo_disfrazado_de_balanza(tmp_path):
    # raíz <Catalogo> dentro de un *BN.zip → el SAT lo rechazaría después
    xml = XML_CATALOGO.format(rfc="SSA980330HU1", anio="2026", mes="01")
    info = inspeccionar_zip(_zip(tmp_path, "SSA980330HU1202601BN.zip", xml))
    assert any("<Catalogo>" in p and "BN" in p for p in info["problemas"])


def test_zip_con_dos_archivos(tmp_path):
    info = inspeccionar_zip(_balanza(
        tmp_path, extras=(("basura.txt", "x"),)))
    assert any("2 archivos" in p for p in info["problemas"])


def test_nombre_interno_distinto(tmp_path):
    info = inspeccionar_zip(_balanza(tmp_path, interno="otro_nombre.xml"))
    assert any("otro_nombre.xml" in p for p in info["problemas"])


def test_zip_corrupto(tmp_path):
    path = tmp_path / "SSA980330HU1202601BN.zip"
    path.write_bytes(b"esto no es un zip")
    info = inspeccionar_zip(path)
    assert any("no se pudo leer" in p for p in info["problemas"])


def test_mes_fuera_de_rango(tmp_path):
    info = inspeccionar_zip(_balanza(tmp_path, mes="14"))
    assert any("fuera de rango" in p for p in info["problemas"])


def test_mes_13_cierre_es_valido(tmp_path):
    info = inspeccionar_zip(_balanza(tmp_path, mes="13"))
    assert info["problemas"] == []


# ---------------------------------------------------------------------------
# inventario: orden
# ---------------------------------------------------------------------------

def test_catalogo_antes_que_balanza_del_mismo_periodo(tmp_path):
    bn = _balanza(tmp_path)
    ct = _zip(tmp_path, "SSA980330HU1202601CT.zip",
              XML_CATALOGO.format(rfc="SSA980330HU1", anio="2026", mes="01"))
    filas = inventario([bn, ct])
    # el catálogo se envía la primera vez junto con la primera balanza y debe
    # ir ANTES; alfabéticamente BN < CT, así que el orden es deliberado
    assert [f["tipo"] for f in filas] == ["CT", "BN"]


def test_inventario_ordena_por_rfc_anio_mes(tmp_path):
    zips = [
        _balanza(tmp_path, rfc="SSA980330HU1", anio="2026", mes="02"),
        _balanza(tmp_path, rfc="SAJ0205248A9", anio="2026", mes="01"),
        _balanza(tmp_path, rfc="SSA980330HU1", anio="2025", mes="12"),
    ]
    filas = inventario(zips)
    assert [(f["rfc"], f["anio"], f["mes"]) for f in filas] == [
        ("SAJ0205248A9", "2026", "01"),
        ("SSA980330HU1", "2025", "12"),
        ("SSA980330HU1", "2026", "02"),
    ]


# ---------------------------------------------------------------------------
# parsear_grid_acuses — HTML tomado del portal real (sesión 2026-08-29)
# ---------------------------------------------------------------------------

GRID_REAL = """
<tr class="encabezado"><th class="acNoRegisto">No.</th>
<th class="acPeriodo">Periodo</th></tr>
<tr><td class="acNoRegisto">1</td><td class="acPeriodo">2025-01</td>
<td class="acMotivo">Env&#237;o Mensual</td>
<td class="acTipoArch">Cat&#225;logos de Cuentas</td>
<td class="acTipoEnvio"></td>
<td class="acNombreArchivo">SSA980330HU1202501CT.zip</td>
<td class="acFolio">0001250100000000194202</td>
<td class="acFecha">29/08/2026 14:41:25</td>
<td class="acEstatus">Aceptado</td>
<td class="acVer"><img onclick="VerAcuseRecepcion('0001250100000000194202',true,true)"></td></tr>
<tr><td class="acNoRegisto">2</td><td class="acPeriodo">2025-01</td>
<td class="acMotivo">Env&#237;o Mensual</td>
<td class="acTipoArch">Balanzas de Comprobaci&#243;n</td>
<td class="acTipoEnvio">Normal</td>
<td class="acNombreArchivo">SSA980330HU1202501BN.zip</td>
<td class="acFolio">0002250100000000306756</td>
<td class="acFecha">29/08/2026 16:43:47</td>
<td class="acEstatus">Aceptado</td>
<td class="acVer"><img onclick="VerAcuseRecepcion('0002250100000000306756',true,true)"></td></tr>
"""


def test_parsea_grid_real():
    filas = parsear_grid_acuses(GRID_REAL)
    assert len(filas) == 2  # el encabezado se descarta solo
    ct, bn = filas
    assert ct["tipo_archivo"] == "Catálogos de Cuentas"   # &#225; → á
    assert bn["tipo_archivo"] == "Balanzas de Comprobación"
    assert bn["folio"] == "0002250100000000306756"
    assert bn["estatus"] == "Aceptado"
    assert bn["tipo_envio"] == "Normal"
    assert ct["tipo_envio"] == ""


def test_grid_vacio_y_fila_sin_folio():
    assert parsear_grid_acuses("") == []
    assert parsear_grid_acuses("<tr><td class='acPeriodo'>2025-01</td></tr>") == []


# ---------------------------------------------------------------------------
# regexes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("nombre,ok", [
    ("SSA980330HU1202601BN", True),     # persona moral (3 letras + homoclave)
    ("SAJ0205248A9202513CT", True),
    ("CACS6008103K4202601BN", True),    # persona física (4 letras)
    ("A&B991231XX1202601BN", True),     # & es válido en RFC de PM (p. ej. A&B)
    ("ÑON991231XX1202601BN", True),     # Ñ también
    ("SSA980330HU1202601", False),      # sin tipo
    ("balanza_enero", False),
])
def test_re_nombre_zip(nombre, ok):
    assert bool(RE_NOMBRE_ZIP.match(nombre)) is ok


@pytest.mark.parametrize("mensaje,transitorio", [
    # los tres mensajes reales vistos contra el portal
    ("Se presentó un error durante la carga del archivo X.zip.\n"
     "Could not find file 'C:\\Resources\\directory\\...xmlTemp\\X.xml'.", True),
    ("Tiempo de espera agotado", True),
    ("Por favor intente de nuevo más tarde", True),
    # errores de fondo: insistir no sirve
    ("El certificado no corresponde al contribuyente firmado.", False),
    ("El RFC del archivo no coincide con la sesión.", False),
])
def test_re_error_transitorio(mensaje, transitorio):
    assert bool(RE_ERROR_TRANSITORIO.search(mensaje)) is transitorio


def test_re_folio_y_fecha():
    texto = ("Archivo SSA980330HU1202501BN.zip recibido con éxito el día "
             "29/08/2026 a las 16:43:47 hrs. Folio No. 0002250100000000306756")
    assert RE_FOLIO.search(texto).group(1) == "0002250100000000306756"
    m = RE_FECHA_ACUSE.search(texto)
    assert (m.group(1), m.group(2)) == ("29/08/2026", "16:43:47")


def test_limpiar_html_desescapa():
    assert _limpiar_html("  Balanzas de\n Comprobaci&#243;n ") == \
        "Balanzas de Comprobación"


# ---------------------------------------------------------------------------
# es_estado_terminal — los 8 casos medidos contra el portal (2026-08-29)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("texto,terminal", [
    ("", False),
    ("Enviando archivo. Por favor espere...", False),
    ("0% completado.", False),
    ("47 % completado.", False),
    ("Procesando", False),
    ("Archivo SSA980330HU1202501BN.zip recibido con éxito el día 29/08/2026 "
     "a las 16:43:47 hrs. Folio No. 0002250100000000306756", True),
    ("Se presentó un error durante la carga del archivo X.zip. "
     "Could not find file 'C:\\Resources\\...xmlTemp\\X.xml'.", True),
    ("El archivo fue rechazado.", True),
])
def test_es_estado_terminal(texto, terminal):
    assert es_estado_terminal(texto) is terminal

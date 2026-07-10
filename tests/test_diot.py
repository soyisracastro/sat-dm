"""Tests del núcleo DIOT: layout, agregación, store, validaciones y export TXT.

El layout de 54 campos y las reglas vienen del instructivo oficial del SAT
(Enero 2025) — ver docs/diot-2025.md.
"""

import shutil
from pathlib import Path

import pytest

from sat_descarga.cli import config_store
from sat_descarga.diot import (
    CAMPOS_DIOT,
    DiotInvalida,
    exportar_txt,
    fila_vacia,
    formatear_linea,
    nombre_archivo,
    prellenar_desde_procesador,
    prellenar_y_guardar,
    validar_filas,
)
from sat_descarga.diot import store as diot_store
from sat_descarga.procesador import ProcesadorDB, parse_cfdi
from sat_descarga.procesador import db as db_mod

MI_RFC = "BBB020202BBB"
PROV_A = "AAA010101AAA"
PROV_B = "CCC030303CC9"

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Fixtures: XMLs sintéticos con desglose de IVA variado
# ---------------------------------------------------------------------------


def _xml(
    uuid: str,
    tipo: str = "I",
    fecha: str = "2026-05-15T10:00:00",
    emisor_rfc: str = PROV_A,
    emisor_nombre: str = "PROVEEDOR ALFA SA DE CV",
    receptor_rfc: str = MI_RFC,
    traslados: str = '<cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>',
    retenciones: str = "",
    total: str = "1160.00",
) -> bytes:
    bloque_ret = f"<cfdi:Retenciones>{retenciones}</cfdi:Retenciones>" if retenciones else ""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Version="4.0" Serie="A" Folio="1" Fecha="{fecha}"
    SubTotal="1000.00" Moneda="MXN" Total="{total}"
    TipoDeComprobante="{tipo}" Exportacion="01" MetodoPago="PUE" FormaPago="03"
    LugarExpedicion="64000">
  <cfdi:Emisor Rfc="{emisor_rfc}" Nombre="{emisor_nombre}" RegimenFiscal="601"/>
  <cfdi:Receptor Rfc="{receptor_rfc}" Nombre="RECEPTOR" DomicilioFiscalReceptor="64000"
                 RegimenFiscalReceptor="612" UsoCFDI="G03"/>
  <cfdi:Conceptos>
    <cfdi:Concepto ClaveProdServ="01010101" Cantidad="1" ClaveUnidad="ACT"
                   Descripcion="X" ValorUnitario="1000.00" Importe="1000.00" ObjetoImp="02"/>
  </cfdi:Conceptos>
  <cfdi:Impuestos>
    {bloque_ret}
    <cfdi:Traslados>{traslados}</cfdi:Traslados>
  </cfdi:Impuestos>
  <cfdi:Complemento>
    <tfd:TimbreFiscalDigital xmlns:tfd="http://www.sat.gob.mx/TimbreFiscalDigital"
        Version="1.1" UUID="{uuid}" FechaTimbrado="{fecha}"
        RfcProvCertif="SAT970701NN3" SelloCFD="..." SelloSAT="..." NoCertificadoSAT="0"/>
  </cfdi:Complemento>
</cfdi:Comprobante>""".encode("utf-8")


TRASLADO_16 = '<cfdi:Traslado Base="1000.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="160.00"/>'
TRASLADO_8 = '<cfdi:Traslado Base="500.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.080000" Importe="40.00"/>'
TRASLADO_0 = '<cfdi:Traslado Base="300.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.000000" Importe="0.00"/>'
TRASLADO_EXENTO = '<cfdi:Traslado Base="200.00" Impuesto="002" TipoFactor="Exento"/>'
TRASLADO_IEPS = '<cfdi:Traslado Base="100.00" Impuesto="003" TipoFactor="Tasa" TasaOCuota="0.080000" Importe="8.00"/>'
RETENCION_IVA = '<cfdi:Retencion Impuesto="002" Importe="106.67"/>'


@pytest.fixture()
def db(tmp_path):
    """DB temporal; siembra el singleton para que abrir_db() la devuelva."""
    db_mod.resetear_singleton_para_tests()
    inst = ProcesadorDB(tmp_path / "test.db")
    yield inst
    inst.close()
    db_mod.resetear_singleton_para_tests()


@pytest.fixture(autouse=True)
def aislar_config(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")


# ---------------------------------------------------------------------------
# Parser: desglose de IVA por tasa
# ---------------------------------------------------------------------------


def test_parser_desglosa_bases_por_tasa():
    cfdi = parse_cfdi(
        _xml("U1-DESGLOSE", traslados=TRASLADO_16 + TRASLADO_8 + TRASLADO_0 + TRASLADO_EXENTO + TRASLADO_IEPS)
    )
    assert cfdi.base_iva_16 == 1000.0
    assert cfdi.iva_trasladado == 160.0
    assert cfdi.base_iva_8 == 500.0
    assert cfdi.iva_trasladado_8 == 40.0
    assert cfdi.base_iva_0 == 300.0
    assert cfdi.base_exento == 200.0
    assert cfdi.ieps_trasladado == 8.0  # el IEPS no contamina el desglose de IVA


def test_parser_deriva_base_sin_atributo_base():
    # CFDI 3.3: el Traslado global no trae `Base` — se deriva importe/tasa.
    cfdi = parse_cfdi(
        _xml(
            "U2-SINBASE",
            traslados='<cfdi:Traslado Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.16" Importe="160.00"/>',
        )
    )
    assert cfdi.base_iva_16 == pytest.approx(1000.0)
    assert cfdi.iva_trasladado == 160.0


def test_parser_tasas_formato_corto():
    cfdi = parse_cfdi(
        _xml(
            "U3-CORTO",
            traslados='<cfdi:Traslado Base="500.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.08" Importe="40.00"/>',
        )
    )
    assert cfdi.base_iva_8 == 500.0
    assert cfdi.iva_trasladado_8 == 40.0


# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------


def test_layout_54_campos():
    assert len(CAMPOS_DIOT) == 54


def test_formatear_linea_53_pipes_y_orden():
    fila = fila_vacia()
    fila.update(rfc="aaa010101aaa", valor_16=1000, dev_16=10, acred_excl_16=160)
    linea = formatear_linea(fila)
    campos = linea.split("|")
    assert len(campos) == 54
    assert campos[0] == "04"           # tipo tercero
    assert campos[2] == "AAA010101AAA" # RFC en mayúsculas
    assert campos[11] == "1000"        # valor_16 (campo 12)
    assert campos[12] == "10"          # dev_16 (campo 13)
    assert campos[21] == "160"         # acred_excl_16 (campo 22)
    assert campos[53] == "01"          # manifiesto


def test_formatear_linea_extranjero_y_limpieza():
    fila = fila_vacia()
    fila.update(
        tipo_tercero="05", tipo_operacion="03", rfc="",
        id_fiscal="TAX|123", nombre_extranjero="ACME Inc", pais="usa",
        lugar_jurisdiccion="no debería salir",  # solo aplica con ZZZ
    )
    campos = formatear_linea(fila).split("|")
    assert campos[3] == "TAX 123"  # el pipe embebido no rompe el formato
    assert campos[5] == "USA"
    assert campos[6] == ""  # lugar_jurisdiccion vacío si país != ZZZ


def test_formatear_linea_nacional_fuerza_campos_extranjero_vacios():
    fila = fila_vacia()
    fila.update(rfc=PROV_A, pais="USA", nombre_extranjero="basura")
    campos = formatear_linea(fila).split("|")
    assert campos[4] == "" and campos[5] == ""


# ---------------------------------------------------------------------------
# Agregación desde el procesador
# ---------------------------------------------------------------------------


def _cargar(db, xmls: list[bytes]) -> None:
    db.agregar([parse_cfdi(x) for x in xmls], mi_rfc=MI_RFC)


def test_prellenar_respeta_incluir_diot(db):
    """Los comprobantes con el interruptor DIOT apagado en Comprobantes no
    entran al prellenado y se reportan en `cfdis_excluidos`."""
    _cargar(db, [
        _xml("I1", traslados=TRASLADO_16),
        _xml("I2", traslados=TRASLADO_16),
    ])
    db.actualizar_flags_cfdi("I2", MI_RFC, {"incluir_diot": 0})

    resultado = prellenar_desde_procesador(MI_RFC, "2026-05", db=db)
    assert resultado["resumen"]["cfdis_considerados"] == 1
    assert resultado["resumen"]["cfdis_excluidos"] == 1
    (fila,) = resultado["filas"]
    assert fila["valor_16"] == 1000  # solo I1; sin el skip serían 2000
    assert fila["num_cfdis"] == 1


def test_prellenar_agrupa_por_proveedor_y_mapea_tasas(db):
    _cargar(db, [
        _xml("I1", traslados=TRASLADO_16 + TRASLADO_8 + TRASLADO_0 + TRASLADO_EXENTO,
             retenciones=RETENCION_IVA),
        _xml("I2", traslados=TRASLADO_16),
        _xml("I3", emisor_rfc=PROV_B, emisor_nombre="PROVEEDOR BETA", traslados=TRASLADO_16),
    ])
    resultado = prellenar_desde_procesador(MI_RFC, "2026-05", db=db)
    filas = resultado["filas"]
    assert resultado["resumen"] == {
        "cfdis_considerados": 3, "cfdis_excluidos": 0,
        "cfdis_sin_desglose": 0, "proveedores": 2,
    }
    alfa = next(f for f in filas if f["rfc"] == PROV_A)
    assert alfa["valor_16"] == 2000       # dos facturas de 1000
    assert alfa["acred_excl_16"] == 320
    assert alfa["valor_rf_norte"] == 500  # asunción v1: 8% → RF norte
    assert alfa["acred_excl_rf_norte"] == 40
    assert alfa["tasa_0"] == 300
    assert alfa["exentos"] == 200
    assert alfa["iva_retenido"] == 107    # 106.67 redondeado
    assert alfa["tipo_tercero"] == "04"
    assert alfa["tipo_operacion"] == "85"
    assert alfa["manifiesto"] == "01"
    assert alfa["nombre"] == "PROVEEDOR ALFA SA DE CV"
    assert alfa["num_cfdis"] == 2


def test_prellenar_capa_acreditable_al_iva_pagado_del_sat(db):
    # Caso real (carga masiva rechazada 2026-07): las bases suman 2458.62 → 2459
    # y el IVA suma 393.62 → 394, pero la aplicación del SAT deriva el "IVA
    # pagado" de los enteros declarados: round(2459 × 0.16) = 393. Sin cap, el
    # acreditable queda 1 peso arriba y el SAT rechaza el archivo.
    _cargar(db, [
        _xml("C1", traslados='<cfdi:Traslado Base="1229.31" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="196.81"/>'),
        _xml("C2", traslados='<cfdi:Traslado Base="1229.31" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="196.81"/>'),
    ])
    (fila,) = prellenar_desde_procesador(MI_RFC, "2026-05", db=db)["filas"]
    assert fila["valor_16"] == 2459          # 2458.62 redondeado
    assert fila["acred_excl_16"] == 393      # 393.62 → 394, capado a round(2459×0.16)


def test_prellenar_egresos_van_a_devoluciones_no_a_negativos(db):
    _cargar(db, [
        _xml("I1"),
        _xml("E1", tipo="E", traslados='<cfdi:Traslado Base="400.00" Impuesto="002" TipoFactor="Tasa" TasaOCuota="0.160000" Importe="64.00"/>'),
    ])
    (fila,) = prellenar_desde_procesador(MI_RFC, "2026-05", db=db)["filas"]
    assert fila["valor_16"] == 1000
    assert fila["dev_16"] == 400          # la nota de crédito NO resta el valor
    assert fila["acred_excl_16"] == 96    # pero el IVA acreditable sí es neto: 160-64


def test_prellenar_filtra_periodo_emitidos_y_autofacturas(db):
    _cargar(db, [
        _xml("I1"),                                              # cuenta
        _xml("F1", fecha="2026-06-01T00:00:00"),                 # otro mes
        _xml("EM1", emisor_rfc=MI_RFC, receptor_rfc=PROV_A),     # emitido (no recibido)
        _xml("AUTO1", emisor_rfc=MI_RFC, receptor_rfc=MI_RFC),   # autofactura
    ])
    resultado = prellenar_desde_procesador(MI_RFC, "2026-05", db=db)
    assert resultado["resumen"]["cfdis_considerados"] == 1
    assert [f["rfc"] for f in resultado["filas"]] == [PROV_A]


def test_prellenar_tercero_global_y_extranjero(db):
    _cargar(db, [
        _xml("G1", emisor_rfc="XAXX010101000", emisor_nombre="GLOBAL"),
        _xml("X1", emisor_rfc="XEXX010101000", emisor_nombre="EXTRANJERO SA"),
    ])
    filas = prellenar_desde_procesador(MI_RFC, "2026-05", db=db)["filas"]
    global_ = next(f for f in filas if f["tipo_tercero"] == "15")
    extranjero = next(f for f in filas if f["tipo_tercero"] == "05")
    assert global_["rfc"] == "XAXX010101000"
    assert global_["tipo_operacion"] == "87"
    assert extranjero["tipo_operacion"] == "03"


def test_prellenar_fila_legacy_estima_base(db):
    _cargar(db, [_xml("L1")])
    # Simula una fila cargada antes de la migración 008 (desglose en NULL).
    with db.cursor() as cur:
        cur.execute(
            "UPDATE cfdis SET base_iva_16 = NULL, base_iva_8 = NULL, "
            "iva_trasladado_8 = NULL, base_iva_0 = NULL, base_exento = NULL"
        )
        cur.connection.commit()
    resultado = prellenar_desde_procesador(MI_RFC, "2026-05", db=db)
    (fila,) = resultado["filas"]
    assert resultado["resumen"]["cfdis_sin_desglose"] == 1
    assert fila["estimado"] is True
    assert fila["valor_16"] == 1000  # 160 / 0.16


def test_prellenar_y_guardar_conserva_filas_manuales(db):
    _cargar(db, [_xml("I1")])
    manual = fila_vacia()
    manual.update(rfc=PROV_B, valor_16=500, origen="manual", nombre="CAPTURADO A MANO")
    diot_store.set_periodo(MI_RFC, "2026-05", [manual], origen="manual")

    estado = prellenar_y_guardar(MI_RFC, "2026-05", db=db)
    rfcs = [f["rfc"] for f in estado["filas"]]
    assert PROV_A in rfcs and PROV_B in rfcs
    manual_persistida = next(f for f in estado["filas"] if f["rfc"] == PROV_B)
    assert manual_persistida["origen"] == "manual"
    # Y quedó persistido:
    assert len(diot_store.get_periodo(MI_RFC, "2026-05")["filas"]) == 2


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


def test_store_aisla_por_rfc_y_periodo():
    fila = fila_vacia()
    fila.update(rfc=PROV_A, valor_16=100)
    diot_store.set_periodo(MI_RFC, "2026-01", [fila])
    assert diot_store.get_periodo(MI_RFC, "2026-02") is None
    assert diot_store.get_periodo("CCC030303CC9", "2026-01") is None
    assert diot_store.get_periodo(MI_RFC, "2026-01")["filas"][0]["valor_16"] == 100


def test_store_rechaza_rfc_y_periodo_invalidos():
    with pytest.raises(ValueError):
        diot_store.set_periodo("../etc/passwd", "2026-01", [])
    with pytest.raises(ValueError):
        diot_store.set_periodo(MI_RFC, "2026-13", [])


def test_store_delete_periodo():
    diot_store.set_periodo(MI_RFC, "2026-01", [])
    assert diot_store.delete_periodo(MI_RFC, "2026-01") is True
    assert diot_store.delete_periodo(MI_RFC, "2026-01") is False


# ---------------------------------------------------------------------------
# Validaciones
# ---------------------------------------------------------------------------


def _fila_ok(**kwargs) -> dict:
    fila = fila_vacia()
    fila.update(rfc=PROV_A, valor_16=1000, acred_excl_16=160)
    fila.update(kwargs)
    return fila


def test_validar_fila_correcta_sin_errores():
    res = validar_filas([_fila_ok()])
    assert res["errores"] == [] and res["advertencias"] == []


@pytest.mark.parametrize("cambios, campo", [
    ({"tipo_tercero": "99"}, "tipo_tercero"),
    ({"tipo_operacion": "87"}, "tipo_operacion"),   # 87 solo aplica a global
    ({"rfc": ""}, "rfc"),                           # nacional sin RFC
    ({"rfc": "MALO"}, "rfc"),
    ({"manifiesto": ""}, "manifiesto"),
    ({"valor_16": -5}, "valor_16"),                 # negativo
    ({"dev_16": 2000}, "dev_16"),                   # devoluciones > valor
    ({"acred_excl_16": 161}, "acred_excl_16"),      # acreditable > round(1000×0.16)
    ({"acred_prop_16": 1}, "acred_excl_16"),        # excl+prop (160+1) > 160
    ({"acred_excl_rf_norte": 5}, "acred_excl_rf_norte"),  # sin valor RF norte
])
def test_validar_errores(cambios, campo):
    res = validar_filas([_fila_ok(**cambios)])
    assert any(e["campo"] == campo for e in res["errores"]), res["errores"]


def test_validar_extranjero_requiere_datos():
    fila = _fila_ok(tipo_tercero="05", tipo_operacion="03", rfc="",
                    id_fiscal="", nombre_extranjero="", pais="")
    campos = {e["campo"] for e in validar_filas([fila])["errores"]}
    assert {"id_fiscal", "nombre_extranjero", "pais"} <= campos


def test_validar_zzz_requiere_lugar():
    fila = _fila_ok(tipo_tercero="05", tipo_operacion="03", rfc="",
                    id_fiscal="X", nombre_extranjero="ACME", pais="ZZZ")
    assert any(e["campo"] == "lugar_jurisdiccion" for e in validar_filas([fila])["errores"])
    fila["lugar_jurisdiccion"] = "Atlántida"
    assert validar_filas([fila])["errores"] == []


def test_validar_advierte_sin_montos_y_duplicados():
    res = validar_filas([_fila_ok(valor_16=0, acred_excl_16=0), _fila_ok(), _fila_ok()])
    mensajes = " ".join(a["mensaje"] for a in res["advertencias"])
    assert "ningún monto" in mensajes
    assert "ya aparece" in mensajes


# ---------------------------------------------------------------------------
# Export TXT (golden file)
# ---------------------------------------------------------------------------


def _filas_golden() -> list[dict]:
    nacional = fila_vacia()
    nacional.update(
        tipo_tercero="04", tipo_operacion="85", rfc="AAA010101AAA",
        valor_16=2000, dev_16=400, acred_excl_16=256,
        valor_rf_norte=500, acred_excl_rf_norte=40,
        tasa_0=300, exentos=200, iva_retenido=107, manifiesto="01",
    )
    extranjero = fila_vacia()
    extranjero.update(
        tipo_tercero="05", tipo_operacion="03", rfc="",
        id_fiscal="US-TAX-1", nombre_extranjero="ACME Inc", pais="USA",
        valor_16=1000, acred_excl_16=160, manifiesto="01",
    )
    global_ = fila_vacia()
    global_.update(
        tipo_tercero="15", tipo_operacion="87", rfc="XAXX010101000",
        valor_16=800, acred_excl_16=128, manifiesto="02",
    )
    return [nacional, extranjero, global_]


def test_exportar_txt_golden():
    data = exportar_txt(_filas_golden())
    esperado = (FIXTURES / "diot_esperado.txt").read_bytes()
    assert data == esperado


def test_exportar_txt_formato():
    data = exportar_txt(_filas_golden())
    assert data.startswith(b"\xef\xbb\xbf")          # BOM UTF-8
    cuerpo = data[3:].decode("utf-8")
    lineas = cuerpo.split("\r\n")
    assert lineas[-1] == ""                          # CRLF final
    for linea in lineas[:-1]:
        assert linea.count("|") == 53
        assert "\n" not in linea


def test_exportar_txt_bloquea_con_errores():
    fila = _fila_ok(rfc="")
    with pytest.raises(DiotInvalida) as exc:
        exportar_txt([fila])
    assert "RFC" in str(exc.value)


def test_exportar_txt_vacio_falla():
    with pytest.raises(DiotInvalida):
        exportar_txt([])


def test_nombre_archivo():
    assert nombre_archivo(MI_RFC, "2026-05") == f"{MI_RFC}_diot_2026-05.txt"
    assert nombre_archivo("no-rfc", "2026-05") == "diot_2026-05.txt"
    assert nombre_archivo(None, "2026-05") == "diot_2026-05.txt"


# ---------------------------------------------------------------------------
# Migración 008 sobre una DB existente
# ---------------------------------------------------------------------------


def test_migracion_008_agrega_columnas_null(tmp_path):
    db_mod.resetear_singleton_para_tests()
    path = tmp_path / "mig.db"
    # DB nueva ya trae el schema completo; verificamos que las columnas existen
    # y que una fila con desglose NULL activa el fallback de la agregación.
    inst = ProcesadorDB(path)
    try:
        with inst.cursor() as cur:
            cur.execute("PRAGMA table_info(cfdis)")
            columnas = {r[1] for r in cur.fetchall()}
        assert {"base_iva_16", "base_iva_8", "iva_trasladado_8", "base_iva_0", "base_exento"} <= columnas
    finally:
        inst.close()
        db_mod.resetear_singleton_para_tests()


def test_migracion_007_a_008_preserva_datos_y_estima(tmp_path):
    """Upgrade real de un usuario que ya tenía la app: una DB en v007 poblada
    sube a v008 sin perder datos; las filas viejas quedan sin desglose (la DIOT
    las estima desde el IVA) y las nuevas traen el desglose exacto.

    El v007 se simula ocultando TODAS las migraciones posteriores a la 007
    mientras se puebla la DB "a la vieja" (INSERT sin las columnas nuevas); el
    `finally` las restaura SIEMPRE — de no hacerlo rompería el resto de la suite.
    """
    ocultas = [
        (mig, tmp_path / f"{mig.name}.bak")
        for mig in sorted(db_mod.MIGRATIONS_DIR.glob("*.sql"))
        if int(mig.name[:3]) > 7
    ]
    db_path = tmp_path / "procesador.db"

    db_mod.resetear_singleton_para_tests()
    try:
        # 1) DB "vieja" en v007: nada posterior en el directorio de migraciones.
        for mig, fuera in ocultas:
            shutil.move(str(mig), str(fuera))
        vieja = db_mod.ProcesadorDB(db_path)
        try:
            with vieja.cursor() as c:
                c.execute("SELECT value FROM _meta WHERE key='schema_version'")
                assert c.fetchone()[0] == "7"
                # INSERT como lo haría la app ANTERIOR: sin las columnas de la 008.
                c.execute(
                    "INSERT INTO cfdis (uuid, mi_rfc, tipo, fecha, emisor_rfc, "
                    "emisor_nombre, receptor_rfc, iva_trasladado) VALUES "
                    "('LEGACY-1', ?, 'I', '2026-05-10T10:00:00', 'LEGA010101AA1', "
                    "'PROVEEDOR LEGADO', ?, 160.0)",
                    (MI_RFC, MI_RFC),
                )
                c.connection.commit()
        finally:
            vieja.close()
    finally:
        # Restaurar las migraciones pase lo que pase (crítico para la suite).
        for mig, fuera in ocultas:
            if fuera.exists():
                shutil.move(str(fuera), str(mig))
        db_mod.resetear_singleton_para_tests()

    # 2) La app nueva reabre la misma DB → aplica 008+ ANTES de cualquier INSERT.
    nueva = db_mod.ProcesadorDB(db_path)
    try:
        with nueva.cursor() as c:
            c.execute("SELECT value FROM _meta WHERE key='schema_version'")
            assert c.fetchone()[0] == str(db_mod.schema_version_actual())
            c.execute("SELECT base_iva_16 FROM cfdis WHERE uuid='LEGACY-1'")
            assert c.fetchone()[0] is None  # fila legacy: sin desglose, no se pierde

        # 3) Con la app nueva se carga un CFDI con desglose completo (16% + 8%).
        nueva.agregar(
            [parse_cfdi(_xml("NUEVA-1", traslados=TRASLADO_16 + TRASLADO_8))],
            mi_rfc=MI_RFC,
        )
        res = prellenar_desde_procesador(MI_RFC, "2026-05", db=nueva)
        assert res["resumen"]["cfdis_sin_desglose"] == 1  # solo la vieja
        por_rfc = {f["rfc"]: f for f in res["filas"]}
        # Legacy: base 16% estimada desde el IVA (160 / 0.16).
        assert por_rfc["LEGA010101AA1"]["estimado"] is True
        assert por_rfc["LEGA010101AA1"]["valor_16"] == 1000
        # Nueva: desglose exacto, sin estimar.
        assert por_rfc[PROV_A]["estimado"] is False
        assert por_rfc[PROV_A]["valor_rf_norte"] == 500  # base 8% exacta
    finally:
        nueva.close()
        db_mod.resetear_singleton_para_tests()

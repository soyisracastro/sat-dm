"""Liquidación — indemnización por tipo de terminación, exenciones e ISR Art. 95."""

from datetime import date

import pytest

from sat_descarga.calculadoras import LiquidacionInput, calcular_liquidacion


def _input(**kwargs):
    base = dict(
        salario=15000,
        tipo_salario="mensual",
        fecha_ingreso=date(2020, 3, 1),
        fecha_baja=date(2026, 7, 15),
        tipo_terminacion="DESPIDO_INJUSTIFICADO",
    )
    base.update(kwargs)
    return LiquidacionInput(**base)


def test_despido_injustificado():
    """3 meses sí, 20 días NO (sin demanda de reinstalación), prima sí."""
    res = calcular_liquidacion(_input())
    assert res["aplica_tres_meses"] is True
    assert res["aplica_veinte_dias"] is False
    assert res["aplica_prima_antiguedad"] is True
    ind = res["indemnizacion"]
    assert ind["tres_meses_constitucional"]["monto"] == pytest.approx(
        res["salario_diario_integrado"] * 90
    )
    assert ind["veinte_dias_por_anio"]["monto"] == 0
    assert ind["prima_antiguedad"]["monto"] > 0


def test_rescision_art51_incluye_veinte_dias():
    res = calcular_liquidacion(_input(tipo_terminacion="RESCISION_ART51"))
    ant = res["antiguedad"]["anios_completos"]
    ind = res["indemnizacion"]
    assert res["aplica_veinte_dias"] is True
    assert ind["veinte_dias_por_anio"]["monto"] == pytest.approx(
        res["salario_diario_integrado"] * 20 * ant
    )


def test_renuncia_sin_15_anios_no_indemnizacion():
    res = calcular_liquidacion(_input(tipo_terminacion="RENUNCIA_VOLUNTARIA"))
    assert res["indemnizacion"] is None
    assert res["aplica_indemnizacion"] is False
    # el total es solo el finiquito
    assert res["total_bruto"] == pytest.approx(res["finiquito"]["subtotal"])


def test_renuncia_con_15_anios_solo_prima():
    res = calcular_liquidacion(
        _input(
            tipo_terminacion="RENUNCIA_VOLUNTARIA",
            fecha_ingreso=date(2010, 1, 15),
            salario=500,
            tipo_salario="diario",
        )
    )
    ind = res["indemnizacion"]
    assert ind is not None
    assert ind["tres_meses_constitucional"]["monto"] == 0
    assert ind["veinte_dias_por_anio"]["monto"] == 0
    prima = ind["prima_antiguedad"]
    assert prima["aplica"] is True
    # salario 500 bajo el tope de 2×SMG general (630.08) → aplica completo
    assert prima["salario_aplicable"] == 500
    assert prima["monto"] == pytest.approx(500 * 12 * res["antiguedad"]["anios_completos"])


def test_tope_prima_antiguedad_general_vs_frontera():
    general = calcular_liquidacion(_input(salario=1000, tipo_salario="diario"))
    frontera = calcular_liquidacion(
        _input(salario=1000, tipo_salario="diario", es_zona_fronteriza=True)
    )
    assert general["indemnizacion"]["prima_antiguedad"]["salario_tope"] == pytest.approx(630.08)
    assert frontera["indemnizacion"]["prima_antiguedad"]["salario_tope"] == pytest.approx(881.74)
    assert general["indemnizacion"]["prima_antiguedad"]["salario_aplicable"] == pytest.approx(630.08)


def test_exencion_90_uma_cubre_indemnizacion():
    """Indemnización menor a 90 UMA × años → gravado 0 e ISR de indemnización 0."""
    res = calcular_liquidacion(
        _input(
            tipo_terminacion="RENUNCIA_VOLUNTARIA",
            fecha_ingreso=date(2010, 1, 15),
            salario=500,
            tipo_salario="diario",
        )
    )
    ind = res["indemnizacion"]
    assert ind["gravado"] == 0
    assert ind["exento"] == pytest.approx(ind["subtotal"])
    assert res["fiscal"]["indemnizacion"]["isr"] == 0


def test_tasa_efectiva_cuando_supera_ultimo_sueldo():
    res = calcular_liquidacion(_input())
    fiscal = res["fiscal"]["indemnizacion"]
    assert res["indemnizacion"]["subtotal"] >= res["salario_mensual"]
    assert fiscal["usa_tasa_efectiva"] is True
    assert fiscal["isr"] == pytest.approx(
        fiscal["base_gravable"] * fiscal["tasa_efectiva"] / 100
    )


def test_tarifa_directa_cuando_indemnizacion_menor_al_sueldo():
    """Indemnización < último sueldo → tarifa directa (sin SPE)."""
    res = calcular_liquidacion(
        _input(
            fecha_ingreso=date(2026, 1, 2),
            fecha_baja=date(2026, 7, 15),
            salario=90000,
            tipo_salario="mensual",
        )
    )
    fiscal = res["fiscal"]["indemnizacion"]
    if res["indemnizacion"] is not None and fiscal["base_gravable"] > 0:
        assert fiscal["usa_tasa_efectiva"] is (res["indemnizacion"]["subtotal"] >= 90000)


def test_antiguedad_seis_meses_exactos_no_redondea():
    """Paridad web: 6 meses exactos (0 días) NO suma año en liquidación."""
    res = calcular_liquidacion(
        _input(fecha_ingreso=date(2020, 1, 15), fecha_baja=date(2026, 7, 15))
    )
    assert res["antiguedad"]["meses"] == 6
    assert res["antiguedad"]["dias"] == 0
    assert res["antiguedad"]["anios_completos"] == 6


def test_totales_cuadran():
    res = calcular_liquidacion(_input(tipo_terminacion="TERMINACION_COLECTIVA"))
    assert res["total_bruto"] == pytest.approx(
        res["finiquito"]["subtotal"] + res["indemnizacion"]["subtotal"]
    )
    assert res["total_neto"] == pytest.approx(res["total_bruto"] - res["total_isr"])
    assert res["total_isr"] == pytest.approx(
        res["fiscal"]["finiquito"]["isr"] + res["fiscal"]["indemnizacion"]["isr"]
    )


def test_entrada_invalida():
    with pytest.raises(ValueError):
        calcular_liquidacion(_input(salario=0))
    with pytest.raises(ValueError):
        calcular_liquidacion(
            _input(fecha_ingreso=date(2026, 7, 15), fecha_baja=date(2026, 7, 15))
        )

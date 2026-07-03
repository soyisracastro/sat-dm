"""SBC — factor de integración, tope 25 UMA y tabla de vacaciones."""

import pytest

from sat_descarga.calculadoras import SBCInput, calcular_sbc, dias_vacaciones


def test_factor_minimo_legal():
    """Primer año: 15 aguinaldo + 12 vacaciones × 25% → factor 1.0493."""
    res = calcular_sbc(SBCInput(salario=300, tipo_salario="diario", antiguedad_anios=1))
    assert res["factor_integracion"] == pytest.approx(1.0493, abs=0.0001)
    assert res["sbc_diario"] == pytest.approx(300 * res["factor_integracion"])
    assert not res["excede_tope"]


def test_salario_mensual_usa_factor_30():
    """Paridad con la web: mensual→diario divide entre 30 (no 30.4)."""
    res = calcular_sbc(SBCInput(salario=9000, tipo_salario="mensual", antiguedad_anios=1))
    assert res["salario_diario_base"] == 300
    assert res["sbc_mensual"] == pytest.approx(res["sbc_diario"] * 30)


def test_tope_25_uma():
    res = calcular_sbc(SBCInput(salario=3000, tipo_salario="diario", antiguedad_anios=5))
    assert res["excede_tope"]
    assert res["sbc_diario"] == pytest.approx(2932.75)  # 25 × 117.31


def test_tabla_vacaciones_lft_2023():
    assert dias_vacaciones(0) == 0
    assert dias_vacaciones(1) == 12
    assert dias_vacaciones(2) == 14
    assert dias_vacaciones(5) == 20
    assert dias_vacaciones(6) == 22
    assert dias_vacaciones(10) == 22
    assert dias_vacaciones(11) == 24
    assert dias_vacaciones(31) == 32
    assert dias_vacaciones(35) == 32
    # >35: fórmula de la web (32 + (floor((a-30)/5) - 1) × 2)
    assert dias_vacaciones(36) == 32
    assert dias_vacaciones(40) == 34


def test_antiguedad_mayor_mas_vacaciones_mas_factor():
    f1 = calcular_sbc(SBCInput(salario=500, tipo_salario="diario", antiguedad_anios=1))
    f10 = calcular_sbc(SBCInput(salario=500, tipo_salario="diario", antiguedad_anios=10))
    assert f10["factor_integracion"] > f1["factor_integracion"]


def test_desglose_suma():
    res = calcular_sbc(SBCInput(salario=400, tipo_salario="diario", antiguedad_anios=3))
    d = res["desglose"]
    assert d["total_integrado"] == pytest.approx(
        d["salario_base"]["integracion_diaria"]
        + d["aguinaldo"]["integracion_diaria"]
        + d["prima_vacacional"]["integracion_diaria"]
    )
    assert d["prima_vacacional"]["dias_vacaciones"] == 16

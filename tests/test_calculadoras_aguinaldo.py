"""Aguinaldo — golden cases portados de los tests TS de la web."""

from datetime import date

import pytest

from sat_descarga.calculadoras import AguinaldoInput, calcular_aguinaldo


def test_ejemplo1_anio_completo_parcialmente_gravado():
    """$8,000 mensuales, 15 días, año completo → bruto 3,947.37, exento 3,519.30."""
    res = calcular_aguinaldo(
        AguinaldoInput(
            salario=8000,
            tipo_salario="mensual",
            fecha_ingreso=date(2025, 1, 1),
            dias_aguinaldo=15,
            fecha_calculo=date(2026, 12, 20),
            metodo_isr="ley",
        )
    )
    assert res["dias_trabajados"] == 365
    assert res["aguinaldo_bruto"] == pytest.approx(3947.37, abs=0.01)
    assert res["parte_exenta"] == 3519.30
    assert res["parte_gravada"] == pytest.approx(res["aguinaldo_bruto"] - 3519.30, abs=0.01)


def test_ejemplo2_proporcional_totalmente_exento():
    """Ingreso 01-jun, cálculo 20-dic → 203 días; bruto < 30 UMA → ISR 0."""
    res = calcular_aguinaldo(
        AguinaldoInput(
            salario=12000,
            tipo_salario="mensual",
            fecha_ingreso=date(2026, 6, 1),
            dias_aguinaldo=15,
            fecha_calculo=date(2026, 12, 20),
            metodo_isr="ley",
        )
    )
    assert res["dias_trabajados"] == 203
    assert res["aguinaldo_bruto"] < 3519.30
    assert res["isr_retenido"] == 0
    assert res["aguinaldo_neto"] == res["aguinaldo_bruto"]


def test_ejemplo3_aguinaldo_alto_isr_significativo():
    """$50,000 con 30 días → bruto 49,342.11; ISR > 10k; tasa 25-32%."""
    res = calcular_aguinaldo(
        AguinaldoInput(
            salario=50000,
            tipo_salario="mensual",
            fecha_ingreso=date(2020, 1, 1),
            dias_aguinaldo=30,
            fecha_calculo=date(2026, 12, 20),
            ingreso_ordinario_mensual=50000,
            metodo_isr="ley",
        )
    )
    assert res["aguinaldo_bruto"] == pytest.approx(49342.11, abs=0.01)
    assert res["parte_exenta"] == 3519.30
    assert res["parte_gravada"] > 45000
    assert res["isr_retenido"] > 10000
    assert 25 < res["tasa_efectiva_isr"] < 32


def test_ejemplo4_comparacion_metodos():
    """El método reglamento (Art. 174) retiene menos o igual que la ley."""
    res = calcular_aguinaldo(
        AguinaldoInput(
            salario=15000,
            tipo_salario="mensual",
            fecha_ingreso=date(2025, 1, 1),
            dias_aguinaldo=15,
            fecha_calculo=date(2026, 12, 20),
            ingreso_ordinario_mensual=15000,
        )
    )
    comp = res["comparacion_metodos"]
    assert comp is not None
    assert comp["metodo_reglamento"]["isr_calculado"] <= comp["metodo_ley"]["isr_calculado"]
    assert comp["metodo_recomendado"] in ("ley", "reglamento")


def test_dias_trabajados_anio_parcial():
    """Ingreso 15-ene, cálculo 20-ene → 6 días (15..20 inclusive)."""
    res = calcular_aguinaldo(
        AguinaldoInput(
            salario=10000,
            tipo_salario="mensual",
            fecha_ingreso=date(2026, 1, 15),
            dias_aguinaldo=15,
            fecha_calculo=date(2026, 1, 20),
        )
    )
    assert res["dias_trabajados"] == 6


def test_metodo_reglamento_aplicado():
    res_ley = calcular_aguinaldo(
        AguinaldoInput(
            salario=25000,
            tipo_salario="mensual",
            fecha_ingreso=date(2020, 1, 1),
            dias_aguinaldo=30,
            fecha_calculo=date(2026, 12, 20),
            metodo_isr="ley",
        )
    )
    res_reg = calcular_aguinaldo(
        AguinaldoInput(
            salario=25000,
            tipo_salario="mensual",
            fecha_ingreso=date(2020, 1, 1),
            dias_aguinaldo=30,
            fecha_calculo=date(2026, 12, 20),
            metodo_isr="reglamento",
        )
    )
    comp = res_ley["comparacion_metodos"]
    assert res_ley["isr_retenido"] == comp["metodo_ley"]["isr_calculado"]
    assert res_reg["isr_retenido"] == comp["metodo_reglamento"]["isr_calculado"]


def test_desglose_estructura():
    res = calcular_aguinaldo(
        AguinaldoInput(
            salario=400,
            tipo_salario="diario",
            fecha_ingreso=date(2024, 3, 1),
            fecha_calculo=date(2026, 12, 20),
        )
    )
    assert len(res["desglose"]["pasos"]) == 6
    assert res["desglose"]["parametros"]["ejercicio"] == 2026
    assert res["salario_diario"] == 400

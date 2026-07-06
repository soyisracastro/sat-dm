"""Finiquito — conceptos proporcionales, exenciones e ISR."""

from datetime import date

import pytest

from sat_descarga.calculadoras import FiniquitoInput, calcular_finiquito


def test_caso_base():
    """$12,000 mensuales, ingreso 01-mar-2022, baja 15-jul-2026."""
    res = calcular_finiquito(
        FiniquitoInput(
            salario=12000,
            tipo_salario="mensual",
            fecha_ingreso=date(2022, 3, 1),
            fecha_baja=date(2026, 7, 15),
        )
    )
    assert res["salario_diario"] == 400  # /30, paridad web
    ant = res["antiguedad"]
    assert (ant["anios"], ant["meses"], ant["dias"]) == (4, 4, 14)
    assert ant["anios_completos"] == 4  # meses < 6 no redondea
    # días trabajados del año: 1-ene → 15-jul inclusive = 196
    assert res["aguinaldo_proporcional"]["dias_trabajados_anio"] == 196
    # salario devengado: 15 días del mes
    assert res["salario_devengado"]["monto"] == pytest.approx(15 * 400)
    # aguinaldo proporcional: (196/365)×15×400 — bajo la exención de 30 UMA
    assert res["aguinaldo_proporcional"]["monto"] == pytest.approx(3221.92, abs=0.01)
    assert res["aguinaldo_proporcional"]["gravado"] == 0
    # vacaciones: 4 años → 18 días anuales
    assert res["vacaciones_proporcionales"]["dias_vacaciones_anuales"] == 18
    assert res["vacaciones_proporcionales"]["monto"] == pytest.approx(3866.30, abs=0.01)
    # prima vacacional 25% — bajo la exención de 15 UMA
    assert res["prima_vacacional"]["monto"] == pytest.approx(966.58, abs=0.01)
    assert res["prima_vacacional"]["gravado"] == 0
    # totales cuadran
    assert res["subtotal_bruto"] == pytest.approx(
        res["salario_devengado"]["monto"]
        + res["aguinaldo_proporcional"]["monto"]
        + res["vacaciones_proporcionales"]["monto"]
        + res["prima_vacacional"]["monto"]
    )
    assert res["total_neto"] == pytest.approx(res["subtotal_bruto"] - res["total_isr"])
    assert res["total_isr"] > 0


def test_antiguedad_redondea_con_6_meses():
    res = calcular_finiquito(
        FiniquitoInput(
            salario=400,
            tipo_salario="diario",
            fecha_ingreso=date(2024, 1, 10),
            fecha_baja=date(2026, 7, 15),  # 2 años, 6 meses
        )
    )
    assert res["antiguedad"]["anios_completos"] == 3  # >= 6 meses cuenta como año


def test_antiguedad_minima_un_anio():
    res = calcular_finiquito(
        FiniquitoInput(
            salario=400,
            tipo_salario="diario",
            fecha_ingreso=date(2026, 3, 1),
            fecha_baja=date(2026, 5, 15),
        )
    )
    assert res["antiguedad"]["anios_completos"] == 1  # mínimo para tabla de vacaciones
    assert res["vacaciones_proporcionales"]["dias_vacaciones_anuales"] == 12


def test_exenciones_superadas_gravan():
    """Salario alto: aguinaldo y prima exceden 30/15 UMA y se grava el excedente."""
    res = calcular_finiquito(
        FiniquitoInput(
            salario=3000,
            tipo_salario="diario",
            fecha_ingreso=date(2015, 1, 1),
            fecha_baja=date(2026, 12, 30),
        )
    )
    aguinaldo = res["aguinaldo_proporcional"]
    prima = res["prima_vacacional"]
    assert aguinaldo["exento"] == pytest.approx(3519.30, abs=0.01)  # 30 UMA
    assert aguinaldo["gravado"] == pytest.approx(aguinaldo["monto"] - 3519.30, abs=0.01)
    assert prima["exento"] == pytest.approx(1759.65, abs=0.01)  # 15 UMA
    assert prima["gravado"] == pytest.approx(prima["monto"] - 1759.65, abs=0.01)


def test_baja_29_febrero_bisiesto():
    res = calcular_finiquito(
        FiniquitoInput(
            salario=500,
            tipo_salario="diario",
            fecha_ingreso=date(2023, 2, 28),
            fecha_baja=date(2024, 2, 29),
            anio=2024,
        )
    )
    ant = res["antiguedad"]
    assert (ant["anios"], ant["meses"], ant["dias"]) == (1, 0, 1)
    # 1-ene-2024 → 29-feb-2024 inclusive = 60 días
    assert res["aguinaldo_proporcional"]["dias_trabajados_anio"] == 60


def test_entrada_invalida_regresa_vacio():
    res = calcular_finiquito(
        FiniquitoInput(
            salario=0,
            tipo_salario="diario",
            fecha_ingreso=date(2024, 1, 1),
            fecha_baja=date(2026, 1, 1),
        )
    )
    assert res["subtotal_bruto"] == 0
    res2 = calcular_finiquito(
        FiniquitoInput(
            salario=400,
            tipo_salario="diario",
            fecha_ingreso=date(2026, 5, 1),
            fecha_baja=date(2026, 5, 1),  # baja == ingreso
        )
    )
    assert res2["total_neto"] == 0

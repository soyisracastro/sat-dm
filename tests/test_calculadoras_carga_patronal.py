"""Carga patronal — cuotas IMSS, Infonavit, ISN y costo total."""

import pytest

from sat_descarga.calculadoras import CargaPatronalInput, calcular_carga_patronal
from sat_descarga.calculadoras.carga_patronal import calcular_cuotas_imss, determinar_tasa_cyv


def test_caso_base_cdmx():
    """$12,000 mensuales, 1 año, clase I, CDMX (ISN 4%)."""
    res = calcular_carga_patronal(
        CargaPatronalInput(
            salario=12000,
            tipo_salario="mensual",
            antiguedad_anios=1,
            clase_riesgo="I",
            codigo_estado="CDMX",
        )
    )
    assert res["salario_diario"] == 400
    assert res["sbc"] == pytest.approx(419.73, abs=0.01)  # 400 × 1.0493
    assert res["impuesto_estatal"] == pytest.approx(480.0)  # 4% CDMX
    assert res["aguinaldo_prorrateo"] == pytest.approx(500.0)  # 15×400/12
    assert res["vacaciones_prorrateo"] == pytest.approx(100.0)  # 12×0.25×400/12
    assert res["infonavit"] == pytest.approx(10.49, abs=0.01)  # sbc×5%×0.5
    assert res["isr_empleado"] == pytest.approx(946.62, abs=0.01)  # sin SPE (>11,492.66)
    assert res["salario_neto"] == pytest.approx(12000 - 946.62, abs=0.01)
    assert res["costo_total_mensual"] == pytest.approx(
        res["salario_mensual"] + res["carga_patronal_mensual"], abs=0.01
    )
    assert res["costo_total_anual"] == pytest.approx(res["costo_total_mensual"] * 12, abs=0.05)


def test_cuotas_imss_con_tope_3_uma():
    """SBC arriba de 3 UMA: la parte fija aplica solo hasta 3 UMA + 1.10% del excedente."""
    sbc = 419.726  # > 3 UMA (351.93)
    cuotas = calcular_cuotas_imss(sbc, prima_riesgo_trabajo=0.54355)
    base = 117.31 * 3
    esperado = base * (0.204 + 0.007) + (sbc - base) * 0.011
    assert cuotas["enfermedad_maternidad"] == pytest.approx(esperado, abs=0.01)


def test_cuotas_imss_sbc_bajo_3_uma():
    sbc = 300.0  # < 3 UMA
    cuotas = calcular_cuotas_imss(sbc, prima_riesgo_trabajo=0.54355)
    assert cuotas["enfermedad_maternidad"] == pytest.approx(300 * 0.211, abs=0.01)


@pytest.mark.parametrize(
    "umas,tasa",
    [
        (1.0, 0.0315),
        (1.01, 0.0368),
        (2.0, 0.0485),
        (3.0, 0.0603),
        (4.0, 0.0661),
        (4.01, 0.0751),
        (10.0, 0.0751),
    ],
)
def test_rangos_cyv(umas, tasa):
    assert determinar_tasa_cyv(117.31 * umas) == tasa


def test_isn_por_estado_y_manual():
    jalisco = calcular_carga_patronal(
        CargaPatronalInput(
            salario=10000, tipo_salario="mensual", antiguedad_anios=1, codigo_estado="JAL"
        )
    )
    assert jalisco["tasa_estatal_aplicada"] == 0.03
    manual = calcular_carga_patronal(
        CargaPatronalInput(
            salario=10000,
            tipo_salario="mensual",
            antiguedad_anios=1,
            codigo_estado="JAL",
            tasa_impuesto_estatal=0.025,
        )
    )
    assert manual["tasa_estatal_aplicada"] == 0.025
    assert manual["impuesto_estatal"] == pytest.approx(250.0)


def test_prima_riesgo_por_clase():
    clase_v = calcular_carga_patronal(
        CargaPatronalInput(
            salario=10000, tipo_salario="mensual", antiguedad_anios=1, clase_riesgo="V"
        )
    )
    assert clase_v["prima_riesgo_aplicada"] == pytest.approx(7.58875)
    assert clase_v["cuotas_imss"]["riesgos_trabajo"] > 0


def test_prestaciones_adicionales():
    res = calcular_carga_patronal(
        CargaPatronalInput(
            salario=10000,
            tipo_salario="mensual",
            antiguedad_anios=1,
            prestaciones_adicionales=[
                {"nombre": "Vales de despensa", "monto": 1000, "tipo": "mensual"},
                {"nombre": "Fondo de ahorro", "monto": 12000, "tipo": "anual"},
            ],
        )
    )
    assert res["prestaciones_adicionales"] == pytest.approx(2000.0)


def test_sin_prorrateos():
    res = calcular_carga_patronal(
        CargaPatronalInput(
            salario=10000,
            tipo_salario="mensual",
            antiguedad_anios=1,
            incluir_aguinaldo_mensual=False,
            incluir_vacaciones_mensual=False,
        )
    )
    assert res["aguinaldo_prorrateo"] == 0
    assert res["vacaciones_prorrateo"] == 0


def test_salario_invalido():
    with pytest.raises(ValueError):
        calcular_carga_patronal(
            CargaPatronalInput(salario=0, tipo_salario="mensual", antiguedad_anios=1)
        )


def test_anio_sin_imss():
    with pytest.raises(ValueError, match="IMSS"):
        calcular_carga_patronal(
            CargaPatronalInput(salario=10000, tipo_salario="mensual", antiguedad_anios=1, anio=2025)
        )

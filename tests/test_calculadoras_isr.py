"""ISR Art. 96 LISR + subsidio para el empleo (módulo compartido)."""

import pytest

from sat_descarga.calculadoras.isr import (
    calcular_isr_periodo,
    calcular_spe,
    isr_diferencial,
    isr_tarifa_directa,
    tarifa_por_periodicidad,
    tasa_efectiva_art174,
    validar_salario_minimo,
)


def test_isr_mensual_15000():
    """Tramo 5 de 2026 (14,644.65-17,533.64): CF 1,339.14 + 17.92%; sin SPE."""
    res = calcular_isr_periodo(15000, 2026)
    assert res["isr_bruto"] == pytest.approx(1402.8187, abs=0.001)
    assert res["subsidio_aplicado"] == 0  # 15,000 > 11,492.66
    assert res["isr_final"] == pytest.approx(1402.8187, abs=0.001)
    assert res["ingreso_neto"] == pytest.approx(15000 - 1402.8187, abs=0.001)


def test_isr_mensual_8000_spe_absorbe():
    """Con $8,000 el SPE ($535.65) supera al ISR bruto → ISR final 0."""
    res = calcular_isr_periodo(8000, 2026)
    assert res["isr_bruto"] == pytest.approx(511.415, abs=0.001)
    assert res["subsidio_aplicado"] == pytest.approx(535.6468, abs=0.001)
    assert res["isr_final"] == 0
    assert res["ingreso_neto"] == 8000


def test_spe_limite_exacto():
    assert calcular_spe(11492.66, 2026) == pytest.approx(535.6468, abs=0.001)
    assert calcular_spe(11492.67, 2026) == 0


def test_spe_enero_2026_usa_uma_2025():
    """Transitorio Segundo DOF 31-12-2025: enero = 15.59% × UMA mensual 2025."""
    enero = calcular_spe(8000, 2026, mes=1)
    assert enero == pytest.approx(113.14 * 30.4 * 0.1559, abs=0.001)
    assert enero == pytest.approx(536.21, abs=0.005)


def test_spe_asimilado_no_aplica():
    res = calcular_isr_periodo(8000, 2026, es_asimilado=True)
    assert res["subsidio_aplicado"] == 0
    assert res["isr_final"] == pytest.approx(511.415, abs=0.001)


def test_spe_tabla_2024():
    assert calcular_spe(5000, 2024) == 324.87
    assert calcular_spe(1000, 2024) == 407.02
    assert calcular_spe(8000, 2024) == 0  # arriba del último rango (7,382.33)


def test_fronteras_de_tramo_2026():
    r1 = calcular_isr_periodo(844.59, 2026, es_asimilado=True)
    r2 = calcular_isr_periodo(844.60, 2026, es_asimilado=True)
    assert r1["desglose"]["rango_tarifa"]["cuota_fija"] == 0.0
    assert r2["desglose"]["rango_tarifa"]["cuota_fija"] == 16.22


@pytest.mark.parametrize(
    "periodicidad,factor",
    [
        ("diario", 1 / 30.4),
        ("semanal", 7 / 30.4),
        ("decenal", 10 / 30.4),
        ("quincenal", 15 / 30.4),
        ("mensual", 1.0),
    ],
)
def test_tarifa_escalada_por_periodicidad(periodicidad, factor):
    tarifa = tarifa_por_periodicidad(2026, periodicidad)
    assert tarifa[1].limite_inferior == pytest.approx(844.60 * factor)
    assert tarifa[1].cuota_fija == pytest.approx(16.22 * factor)
    assert tarifa[1].porcentaje_excedente == 0.0640  # el porcentaje no cambia


def test_isr_quincenal_equivale_a_mensual_escalado():
    """Mismo salario expresado quincenal ≈ ISR mensual × factor (sin SPE)."""
    mensual = calcular_isr_periodo(20000, 2026, "mensual", es_asimilado=True)
    quincenal = calcular_isr_periodo(20000 * 15 / 30.4, 2026, "quincenal", es_asimilado=True)
    assert quincenal["isr_final"] == pytest.approx(mensual["isr_final"] * 15 / 30.4, rel=1e-9)


def test_ingreso_cero_o_negativo():
    assert calcular_isr_periodo(0, 2026)["isr_final"] == 0
    assert calcular_isr_periodo(-100, 2026)["isr_final"] == 0


def test_anio_sin_tarifa():
    with pytest.raises(ValueError, match="2021"):
        calcular_isr_periodo(10000, 2021)


def test_isr_tarifa_directa_vlookup():
    """Semántica VLOOKUP (plantilla PTU): mayor límite inferior ≤ base."""
    assert isr_tarifa_directa(0, 2026) == 0
    assert isr_tarifa_directa(15000, 2026) == pytest.approx(1402.8187, abs=0.001)
    # base en el "hueco" entre tramos cae al tramo anterior (VLOOKUP aproximado)
    assert isr_tarifa_directa(844.595, 2026) == pytest.approx(
        (844.595 - 0.01) * 0.0192, abs=1e-6
    )


def test_isr_diferencial():
    res = isr_diferencial(5000, 15000, 2026)
    esperado = (
        calcular_isr_periodo(20000, 2026)["isr_final"]
        - calcular_isr_periodo(15000, 2026)["isr_final"]
    )
    assert res["isr"] == pytest.approx(esperado)
    assert res["tasa"] == pytest.approx(res["isr"] / 5000 * 100)


def test_tasa_efectiva_art174():
    res = tasa_efectiva_art174(43240.35, 15000, 2026)
    assert res["mensualizado"] == pytest.approx(43240.35 / 365 * 30.4)
    assert res["isr"] == pytest.approx(43240.35 * res["tasa"] / 100)
    assert 0 < res["tasa"] < 35


def test_validar_salario_minimo_general():
    """$100 diarios < SMG general 2026 ($315.04) → rechazado con mensaje claro."""
    with pytest.raises(ValueError, match="salario mínimo general"):
        validar_salario_minimo(100, 2026, "diario")
    # En o por encima del mínimo pasa sin error
    validar_salario_minimo(315.04, 2026, "diario")
    validar_salario_minimo(400, 2026, "diario")


def test_validar_salario_minimo_frontera():
    """$400 diarios: válido en zona general, inválido en ZLFN ($440.87)."""
    validar_salario_minimo(400, 2026, "diario", es_zona_fronteriza=False)
    with pytest.raises(ValueError, match="Frontera Norte"):
        validar_salario_minimo(400, 2026, "diario", es_zona_fronteriza=True)
    validar_salario_minimo(440.87, 2026, "diario", es_zona_fronteriza=True)


def test_validar_salario_minimo_por_periodicidad():
    """El umbral escala por días del período (mensual = SMG × 30.4)."""
    umbral_mensual = 315.04 * 30.4  # $9,577.22
    with pytest.raises(ValueError):
        validar_salario_minimo(umbral_mensual - 0.01, 2026, "mensual")
    validar_salario_minimo(umbral_mensual, 2026, "mensual")
    with pytest.raises(ValueError):
        validar_salario_minimo(315.04 * 15 - 0.01, 2026, "quincenal")

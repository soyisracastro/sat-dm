"""PTU — lógica de la plantilla Excel de TodoConta (golden case de la guía)."""

from datetime import date

import pytest

from sat_descarga.calculadoras import EmpresaPTU, TrabajadorPTU, calcular_ptu


def _empresa(**kwargs):
    base = dict(
        utilidad_fiscal=600000.0,
        ejercicio=2025,
        nombre="Servicios Profesionales del Norte SA de CV",
        rfc="SPN240115ABC",
        ptu_no_cobrada=0.0,
        tipo_persona="Moral",
        criterio_exencion="UMA",
    )
    base.update(kwargs)
    return EmpresaPTU(**base)


def _trabajador_unico(**kwargs):
    base = dict(
        nombre="Trabajador de Prueba",
        salario_diario=15000 / 30.4,  # ≈ 493.42 (la guía usa el equivalente de $15,000)
        dias_trabajados=365,
        percepcion_anual=180000.0,
        ptu_anio_1=40000.0,
        ptu_anio_2=40000.0,
        ptu_anio_3=40000.0,
        ingreso_mensual_ordinario=15000.0,
        isr_mensual_ordinario=1068.54,
    )
    base.update(kwargs)
    return TrabajadorPTU(**base)


def test_golden_case_guia_plantilla():
    """Caso de validación de la guía: utilidad 600k, 1 trabajador de $15,000."""
    res = calcular_ptu(_empresa(), [_trabajador_unico()])

    # Año de pago = ejercicio + 1 → 2026 (UMA/SMG/tarifa de 2026)
    assert res["config"]["anio_pago"] == 2026
    assert res["config"]["uma_diaria"] == 117.31
    assert res["config"]["fecha_limite_pago"] == "2026-05-30"  # Moral

    emp = res["empresa"]
    assert emp["ptu_generada"] == pytest.approx(60000.0)
    assert emp["ptu_a_repartir"] == pytest.approx(60000.0)
    assert emp["bolsa_dias"] == pytest.approx(30000.0)

    t = res["trabajadores"][0]
    assert t["ptu_bruta"] == pytest.approx(60000.0)
    assert t["tope_tres_meses"] == pytest.approx(45000.0)  # salario diario × 91.2
    assert t["promedio_tres_anios"] == pytest.approx(40000.0)
    assert t["monto_maximo"] == pytest.approx(45000.0)
    assert t["ptu_real"] == pytest.approx(45000.0)
    assert t["ptu_exenta"] == pytest.approx(1759.65)  # 15 × UMA 2026
    assert t["ptu_gravada"] == pytest.approx(43240.35)
    # La guía valida que el método recomendado sea Art. 174
    assert t["comparacion"]["metodo_recomendado"] == "art174"
    assert t["art174"]["isr_ptu"] < t["art96"]["isr_ptu"]
    assert t["comparacion"]["ptu_neta_final"] == pytest.approx(
        45000.0 - t["comparacion"]["isr_recomendado"]
    )


def test_art96_usa_isr_ordinario_capturado():
    res = calcular_ptu(_empresa(), [_trabajador_unico()])
    t = res["trabajadores"][0]
    # base Art. 96 = ingreso mensual + gravada; ISR PTU = ISR(base) − ISR capturado
    assert t["art96"]["base_gravable"] == pytest.approx(15000 + 43240.35)
    assert t["art96"]["isr_ordinario"] == 1068.54
    assert t["art96"]["isr_ptu"] == pytest.approx(t["art96"]["isr_total"] - 1068.54, abs=0.01)


def test_criterio_smg_prodecon():
    res = calcular_ptu(_empresa(criterio_exencion="SMG"), [_trabajador_unico()])
    t = res["trabajadores"][0]
    assert res["config"]["exencion_por_trabajador"] == pytest.approx(15 * 315.04)  # SMG 2026
    assert t["ptu_exenta"] == pytest.approx(4725.60)
    assert t["ptu_gravada"] == pytest.approx(45000.0 - 4725.60)


def test_reparto_50_50_multiples_trabajadores():
    trabajadores = [
        _trabajador_unico(nombre="A", dias_trabajados=365, percepcion_anual=100000),
        _trabajador_unico(nombre="B", dias_trabajados=182.5, percepcion_anual=100000),
    ]
    res = calcular_ptu(_empresa(), trabajadores)
    a, b = res["trabajadores"]
    assert a["factor_dias"] == pytest.approx(365 / 547.5, abs=1e-6)
    assert b["factor_dias"] == pytest.approx(182.5 / 547.5, abs=1e-6)
    assert a["factor_salarios"] == pytest.approx(0.5)
    assert a["ptu_dias"] + b["ptu_dias"] == pytest.approx(30000.0, abs=0.01)
    assert a["ptu_salarios"] + b["ptu_salarios"] == pytest.approx(30000.0, abs=0.01)


def test_tope_confianza_120_por_ciento():
    """Ejemplo de la plantilla: Roberto (confianza, $850) topa al 120% del más
    alto de planta (Ana, $320 → tope $384; percepción topada 384×365)."""
    trabajadores = [
        _trabajador_unico(nombre="Ana", salario_diario=320, percepcion_anual=116800),
        _trabajador_unico(
            nombre="Roberto",
            salario_diario=850,
            percepcion_anual=310250,
            es_confianza=True,
        ),
    ]
    res = calcular_ptu(_empresa(), trabajadores)
    roberto = res["trabajadores"][1]
    assert roberto["salario_tope_confianza"] == pytest.approx(384.0)
    suma_percepciones = 116800 + 310250
    esperado = min(310250, 384 * 365) / suma_percepciones
    assert roberto["factor_salarios"] == pytest.approx(esperado, abs=1e-6)


def test_ptu_no_cobrada_se_suma():
    res = calcular_ptu(_empresa(ptu_no_cobrada=12500.0), [_trabajador_unico()])
    assert res["empresa"]["ptu_a_repartir"] == pytest.approx(72500.0)


def test_advertencia_fecha_pago_tardia():
    res = calcular_ptu(
        _empresa(fecha_pago=date(2026, 6, 15)), [_trabajador_unico()]
    )
    assert any("fecha límite" in a for a in res["advertencias"])
    ok = calcular_ptu(_empresa(fecha_pago=date(2026, 5, 15)), [_trabajador_unico()])
    assert ok["advertencias"] == []


def test_fecha_limite_persona_fisica():
    res = calcular_ptu(_empresa(tipo_persona="Física"), [_trabajador_unico()])
    assert res["config"]["fecha_limite_pago"] == "2026-06-29"


def test_advertencia_menos_de_60_dias():
    res = calcular_ptu(
        _empresa(),
        [_trabajador_unico(), _trabajador_unico(nombre="Eventual", dias_trabajados=45)],
    )
    assert res["trabajadores"][0]["advertencias"] == []
    assert any("60" in a for a in res["trabajadores"][1]["advertencias"])


def test_prenomina_claves_cfdi():
    res = calcular_ptu(_empresa(), [_trabajador_unico()])
    pre = res["trabajadores"][0]["prenomina"]
    assert pre["clave_percepcion"] == "003"
    assert pre["clave_deduccion"] == "002"
    assert pre["tipo_nomina"] == "Extraordinaria"
    assert pre["ptu_gravada"] + pre["ptu_exenta"] == pytest.approx(45000.0, abs=0.01)
    assert pre["neto_a_pagar"] == pytest.approx(45000.0 - pre["isr_retenido"], abs=0.01)


def test_totales():
    res = calcular_ptu(
        _empresa(),
        [
            _trabajador_unico(nombre="A"),
            _trabajador_unico(nombre="B", salario_diario=300, percepcion_anual=109500),
        ],
    )
    tot = res["totales"]
    assert tot["ptu_real"] == pytest.approx(
        sum(t["ptu_real"] for t in res["trabajadores"]), abs=0.01
    )
    assert tot["ptu_neta_a_pagar"] == pytest.approx(
        sum(t["comparacion"]["ptu_neta_final"] for t in res["trabajadores"]), abs=0.01
    )


def test_ejercicio_no_soportado():
    with pytest.raises(ValueError, match="soportados"):
        calcular_ptu(_empresa(ejercicio=2019), [_trabajador_unico()])


def test_validaciones_basicas():
    with pytest.raises(ValueError):
        calcular_ptu(_empresa(utilidad_fiscal=0), [_trabajador_unico()])
    with pytest.raises(ValueError):
        calcular_ptu(_empresa(), [])

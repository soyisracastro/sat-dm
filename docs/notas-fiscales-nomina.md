# Notas fiscales de nómina (para calculadoras y futura auditoría de nómina)

Hallazgos verificados contra fuentes primarias durante el hito de calculadoras
(2026-07, PRs #110-#113). Este documento existe para que una futura **función de
auditoría de nómina** (revisar CFDIs de nómina emitidos: retenciones y subsidio
correctos por período) no tenga que redescubrir estas reglas. La fuente de
verdad programática es `sat_descarga/calculadoras/indicadores.py`.

## 1. Subsidio para el empleo (SPE): enero es un mes especial

### Mecánica vigente (2025+)

El decreto DOF 01-05-2024 cambió el SPE de la tabla de montos fijos (2013) a un
**monto fijo mensual = porcentaje × valor mensual de la UMA**, con tope de
ingreso. Cada diciembre un decreto actualiza porcentaje y tope para el año
siguiente.

| Año | % general | Tope ingreso mensual | Decreto |
|---|---|---|---|
| 2025 | 13.80% | $10,171.00 | DOF 31-12-2024 (nota 5746529) |
| 2026 | 15.02% | $11,492.66 | DOF 31-12-2025 (nota 5777649) |

### La peculiaridad de enero

La UMA nueva entra en vigor **el 1 de febrero** (Art. 5 de la Ley para
Determinar el Valor de la UMA). En enero sigue vigente la UMA del año anterior,
así que aplicar el % general en enero daría un subsidio menor que el resto del
año. Para emparejarlo, el **Transitorio Segundo** de cada decreto fija un
porcentaje mayor para enero, aplicado sobre la UMA vigente en enero (la del año
anterior):

| Período | Fórmula | Monto |
|---|---|---|
| Enero 2026 | 15.59% × UMA mensual 2025 ($3,439.46) | **$536.21** |
| Feb-dic 2026 | 15.02% × UMA mensual 2026 ($3,566.22) | **$535.65** |
| Enero 2025 | 14.39% × UMA mensual 2024 ($3,300.53) | **$474.95** |
| Feb-dic 2025 | 13.80% × UMA mensual 2025 ($3,439.46) | **$474.64** |

Notas para la auditoría:

- **Error común** (lo tiene la calculadora web de todoconta-apps): aplicar el
  % de enero sobre la UMA del año nuevo. Para enero 2026 da $556.08 en vez de
  $536.21 — subsidio de más ⇒ retención de menos. Un CFDI de nómina de enero
  con `subsidio_causado` ≈ 556 delata este error.
- El considerando del decreto 2026 cita $536.22 como monto objetivo: se calculó
  con una UMA proyectada antes de que INEGI publicara la definitiva. Con la UMA
  real, feb-dic quedó en $535.65 (enero termina $0.56 arriba).
- Períodos menores a un mes: el monto mensual se divide entre 30.4 y se
  multiplica por los días del período. Pagos de 2+ meses en una exhibición:
  monto mensual × número de meses.
- El SPE **no aplica a asimilados a salarios** ni a ingresos por encima del
  tope; el tope **excluye** primas de antigüedad, retiro e indemnizaciones.
- Hasta 2024 el esquema era la tabla de montos fijos (límite $7,382.33). El
  decreto de mayo 2024 aplicó desde mayo; una auditoría estricta de 2024
  tendría que partir el año (las calculadoras usan la tabla todo 2024 como
  simplificación, igual que la web).

## 2. Salario mínimo y retención de ISR

- **Pagar por debajo del salario mínimo es ilegal** (Art. 90 LFT). Un "salario"
  menor al SMG del período no es base válida para calcular retención — la
  calculadora de ISR lo bloquea con mensaje.
- **Quien percibe exactamente el salario mínimo no es sujeto de retención**
  (Art. 96, último párrafo, LISR). En una auditoría: CFDI de nómina de un
  trabajador con SMG y con ISR retenido > 0 es un hallazgo.
- El umbral depende de la zona: **general** vs **Zona Libre de la Frontera
  Norte** (ZLFN, mínimo mayor). 2026: $315.04 vs $440.87 diarios. Histórico
  completo en `UMA_SMG_HISTORICO` (indicadores.py).
- Equivalencias por período con el mes de 30.4 días del Anexo 8 (2026 general:
  $9,577.22 mensuales; ZLFN: $13,402.45).

## 3. Otras semillas para la auditoría de nómina

- **Tarifas ISR**: se actualizan solo cuando la inflación acumulada supera 10%
  (Art. 152 LISR). Vigencias: tabla con primer tramo a $746.04 = 2022-2025;
  tabla 2026 (factor 1.1321, Anexo 8 RMF 2026, DOF 28-12-2025). Auditar un
  período con la tarifa equivocada produce diferencias sistemáticas pequeñas.
- **Exenciones ligadas a UMA** (Art. 93 LISR): aguinaldo 30 UMA, prima
  vacacional y PTU 15 UMA (PTU con criterio SAT=UMA vs PRODECON=SMG, en
  disputa), pagos por separación 90 UMA por año de servicio. Siempre con la
  UMA **del año del pago**.
- **Pagos extraordinarios** (aguinaldo, PTU): la retención puede calcularse por
  Art. 96 LISR (directo) o Art. 174 RLISR (tasa efectiva mensualizada);
  cualquiera de las dos es válida — la auditoría debe probar ambas antes de
  marcar una retención como incorrecta.

## 4. Dónde vive esto en el código

- `sat_descarga/calculadoras/indicadores.py` — valores por año con cita de
  fuente (UMA/SMG, tarifas, SPE con `porcentaje_enero`/`uma_diaria_enero`).
- `sat_descarga/calculadoras/isr.py` — `calcular_spe(..., mes=1|2..12)`,
  `validar_salario_minimo(...)`.
- La UI de la calculadora de ISR **no expone el mes** (usa feb-dic): el caso
  enero es relevante para auditar nóminas históricas, no para el cálculo "al
  momento". Cuando exista la auditoría, pasar `mes=1` para recibos de enero.

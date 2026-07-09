# Mapeo CFDI → Póliza (reglas contables)

> Define cómo se convierte un CFDI parseado (`CfdiData`) en los asientos de una póliza. Es la capa
> **común** a las dos vías de escritura: el resultado (una `Poliza` con sus `MovimientoPoliza`) se
> serializa a TXT (`01-importacion-txt-polizas.md`) o se envía por SDK (`02-sdk-com.md`) sin cambiar
> el armado.
>
> **Aviso**: el mapeo contable es **decisión del contador**. Este documento propone un esqueleto
> razonable y parametrizable; las cuentas concretas y algunas reglas (p. ej. IVA en PPD) las define
> el usuario por empresa. Se marca claramente qué es **regla fija** y qué es **configuración**.

## 1. Entrada: campos de `CfdiData`

De `sat_descarga/procesador/cfdi_parser.py` (dataclass `CfdiData`, línea 122; ya persistido en
`cfdis.raw_json`). Campos que consume el mapeo:

- **Clasificación**: `tipo_comprobante` (`I`/`E`/`T`/`N`/`P`), `emisor_rfc`, `receptor_rfc`,
  `mi_rfc` (contexto: ¿la empresa es emisora o receptora?), `metodo_pago` (`PUE`/`PPD`),
  `forma_pago`.
- **Montos**: `sub_total`, `descuento`, `total`, `moneda`, `tipo_cambio`.
- **Impuestos**: `iva_trasladado` (16%), `iva_trasladado_8` + `base_iva_8` (8%), `ieps_trasladado`,
  `iva_retenido`, `isr_retenido`, `base_iva_16`, `base_iva_0`, `base_exento`.
- **Identidad**: `uuid`, `serie`, `folio`, `fecha_emision`, `emisor_nombre`, `receptor_nombre`.
- **Complementos**: `datos_pago` (tipo P), `datos_nomina` (tipo N).

## 2. Determinación de "emisor vs receptor"

**Regla fija**: comparar `mi_rfc` (la empresa que contabiliza) con `emisor_rfc`/`receptor_rfc`:

- `mi_rfc == emisor_rfc` → **CFDI emitido** → normalmente **póliza de Ingreso** (tipo 1), IVA
  **trasladado** (por pagar).
- `mi_rfc == receptor_rfc` → **CFDI recibido** → normalmente **póliza de Egreso** (tipo 2),
  IVA **acreditable**, posibles retenciones.

El `tipo_comprobante` afina: `E` (egreso/nota de crédito) invierte el sentido respecto de `I`.

## 3. Catálogo de cuentas por defecto (configuración por empresa)

Estructura propuesta (`ConfigCuentasContpaq`), con **códigos** de cuenta (los que existen en
`Cuentas.Codigo`, ver `03-lectura-sql-server.md` §4.1). Valores de ejemplo — el usuario los ajusta:

| Clave de config | Uso | Ejemplo |
|---|---|---|
| `clientes` | Cuenta de clientes (ingreso PPD) | `1050-...` |
| `proveedores` | Cuenta de proveedores (egreso PPD) | `2010-...` |
| `bancos` / por forma de pago | Banco/caja (ingreso/egreso PUE) | `1020-...` |
| `ventas` | Ingresos por ventas | `4010-...` |
| `gastos_default` | Gasto genérico (egreso) | `6010-...` |
| `iva_trasladado_cobrado` | IVA trasladado efectivamente cobrado | `2080-...` |
| `iva_trasladado_pendiente` | IVA trasladado pendiente de cobro (PPD) | `2085-...` |
| `iva_acreditable_pagado` | IVA acreditable pagado | `1180-...` |
| `iva_acreditable_pendiente` | IVA acreditable pendiente de pago (PPD) | `1185-...` |
| `iva_retenido` / `isr_retenido` | Retenciones | `2120-...` / `2130-...` |
| `ieps` | IEPS | según caso |
| `redondeo` | Cuenta de ajuste por redondeo | `7900-...` |

Opcional: **reglas por RFC de proveedor/cliente** (mapear un tercero a una cuenta de gasto
específica) y por `clave_prod_serv` del concepto.

## 4. Matriz de asientos por escenario

Notación: **C** = cargo, **A** = abono. Todos los escenarios deben **cuadrar** (ΣC = ΣA).

### 4.1 Ingreso emitido, PUE (cobrado al contado) — póliza tipo 1
| Mov | Cuenta | Importe |
|---|---|---|
| C | `bancos` | `total` |
| A | `ventas` | `sub_total - descuento` |
| A | `iva_trasladado_cobrado` | `iva_trasladado` (+ `iva_trasladado_8`) |

### 4.2 Ingreso emitido, PPD (a crédito) — póliza tipo 1
| Mov | Cuenta | Importe |
|---|---|---|
| C | `clientes` | `total` |
| A | `ventas` | `sub_total - descuento` |
| A | `iva_trasladado_pendiente` | `iva_trasladado` |

El **cobro posterior** llega como CFDI de **Pago (P)** → ver §4.5.

### 4.3 Egreso recibido, PUE (gasto pagado) — póliza tipo 2
| Mov | Cuenta | Importe |
|---|---|---|
| C | `gastos_default` (o por RFC/concepto) | `sub_total - descuento` |
| C | `iva_acreditable_pagado` | `iva_trasladado` |
| A | `iva_retenido` | `iva_retenido` (si aplica) |
| A | `isr_retenido` | `isr_retenido` (si aplica) |
| A | `bancos` | `total - iva_retenido - isr_retenido` |

Retenciones típicas de honorarios/arrendamiento: ISR 10% y IVA 2/3 (`iva_retenido`, `isr_retenido`
ya vienen calculados en `CfdiData`).

### 4.4 Egreso recibido, PPD (a crédito) — póliza tipo 2
Igual que 4.3 pero el abono va a `proveedores` (no a `bancos`) y el IVA a
`iva_acreditable_pendiente`. El **pago** posterior es CFDI de Pago (P).

### 4.5 Pago (tipo P) — reclasificación de IVA — póliza tipo 1 (cobro) o 2 (pago)
El complemento de pagos **realiza** el IVA que estaba pendiente:
- **Cobro** (pago recibido): C `bancos` / A `clientes` por el monto pagado; y reclasificación
  C `iva_trasladado_pendiente` / A `iva_trasladado_cobrado` por el IVA proporcional.
- **Pago** (pago emitido): A `bancos` / C `proveedores`; y C `iva_acreditable_pagado` /
  A `iva_acreditable_pendiente`.

Usa `datos_pago` (monto, documentos relacionados) para prorratear cuando un pago cubre varias
facturas.

### 4.6 Nota de crédito (tipo E emitida) — póliza tipo 1 (o 3)
Invierte 4.1/4.2: C `ventas` (devolución), C `iva_trasladado_*`, A `clientes`/`bancos`.

### 4.7 Nómina (tipo N) — póliza tipo 2 (egreso)
Desde `datos_nomina` (percepciones, deducciones, otros pagos):
| Mov | Cuenta | Importe |
|---|---|---|
| C | `sueldos_gastos` (percepciones gravadas + exentas) | total percepciones |
| A | `isr_retenido_nomina` | ISR retenido |
| A | `imss_deducciones` | cuotas obrero / otras deducciones |
| A | `bancos` / `nomina_por_pagar` | neto pagado |

El nivel de desglose (por percepción/deducción individual) es configurable; v1 puede agrupar.

## 5. Reglas transversales

- **Cuadre y redondeo** (regla fija): si por redondeo ΣC ≠ ΣA, ajustar con un movimiento a la
  cuenta `redondeo` (tolerancia configurable, p. ej. ±$0.02). Nunca exportar descuadrado.
- **Moneda extranjera**: si `moneda != "MXN"`, poblar `ImporteME` con el monto en ME y `Importe`
  con el valorizado a `tipo_cambio` (el campo `TipoCambio` existe en los registros TXT y en el SDK).
- **Referencia** (`Referencia`, máx. 10 en `MovimientosPoliza`): `serie + folio` truncado.
- **Concepto de póliza**: p. ej. `"{tipo} {emisor|receptor} {serie}-{folio}"`; concepto de
  movimiento puede incluir el nombre del tercero + UUID corto.
- **UUID**: siempre asociar (registro `AD` en TXT / `TSdkAsocCFDI` en SDK) para trazabilidad y
  para que la conciliación (`03`) reconozca la póliza.
- **Fecha**: `fecha_emision` → `yyyyMMdd`. Validar que caiga en un periodo abierto (`Ejercicios`).
- **Clase**: exportar como `Sin afectar`/`CLASE_SINAFECTAR` en modo "revisar antes"; `Normal`/
  `CLASE_AFECTAR` cuando el contador confía en el mapeo.

## 6. Qué es fijo vs configurable

| Fijo (regla contable/estructural) | Configurable (decisión del contador) |
|---|---|
| Sentido cargo/abono por tipo de CFDI | Qué **cuentas** concretas se usan |
| Cuadre obligatorio ΣC = ΣA | Tolerancia y cuenta de redondeo |
| Reclasificación de IVA en pagos PPD→P | Cuentas de IVA cobrado/pendiente/acreditable |
| Asociar UUID a la póliza | Nivel de desglose (nómina, por concepto) |
| ME: Importe valorizado + ImporteME | Reglas por RFC/`clave_prod_serv` |

## 7. Propuesta en sat-dm *(no implementado)*

- `sat_descarga/contpaq/mapeo.py`: `mapear_cfdi(cfdi: CfdiData, cfg: ConfigCuentasContpaq) -> Poliza`,
  con una función por escenario (`_ingreso_pue`, `_egreso_ppd`, `_pago`, `_nomina`, …) y un
  dispatcher por `(tipo_comprobante, es_emitido, metodo_pago)`.
- `ConfigCuentasContpaq`: dataclass persistida por empresa (junto al estado de la DIOT en
  `~/.sat-descarga/`), poblada con ayuda del catálogo leído por SQL (doc 03).
- **Verificación**: fixtures de CFDI reales (ingreso PUE/PPD, egreso con retención, pago, nómina)
  con la póliza esperada; test de cuadre en todos.

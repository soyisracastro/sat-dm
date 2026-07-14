# CONTPAQi Contabilidad — Importación de pólizas por archivo de texto (vía A)

> **Fuente**: esquema oficial `CT_EST_Poliza_NG.xls` instalado por CONTPAQi Contabilidad
> en `C:\Compac\Empresas\Esquemas\Contpaq\`, hoja `Estructura` ("ContPAQ NG /
> Estructura del archivo / Pólizas"), leído de la instalación **14.4.2**. Los tipos y
> longitudes de campo, así como la definición de póliza/movimiento, se cruzaron contra el
> **Diccionario de la Base de Datos de CONTPAQi Contabilidad** (`BDDCONTPAQi.pdf`, tablas
> `Polizas`, `MovimientosPoliza`, `AsocCFDIs`, `Cuentas`).
>
> Esta es la vía de escritura **que NO requiere licencia del SDK**: genera un archivo de
> texto que el usuario importa desde CONTPAQi con *Importación → Importar otros sistemas*
> usando la estructura `CT_EST_Poliza_NG`. Es el análogo de lo que ya hacemos con la DIOT
> (ver `docs/diot-2025.md` + `sat_descarga/diot/`), y es la **primera fase de escritura**
> comprometida en `docs/presentacion-pitch.md` (líneas 204-210): *"Pre-armar pólizas … en el
> formato que CONTPAQi importa (el camino más seguro y el primero que haríamos)"*.

## 1. Modelo del formato

CONTPAQi importa datos de "otros sistemas" mediante **estructuras**: archivos `.xls`
(`CT_EST_*`) que describen, byte a byte, cómo leer un archivo de texto plano. Cada estructura
declara uno o más **registros**; cada registro es **una línea** del archivo que empieza por un
**marcador** de 1-2 caracteres y concatena campos de **ancho fijo**.

La hoja `Estructura` tiene 5 columnas que gobiernan la serialización:

| Columna | Significado |
|---|---|
| **Tipo** | `E` = definición de registro (inicia un registro nuevo); `A` = campo con valor; `R` = campo de **referencia** (se captura un **código** y CONTPAQi resuelve el Id interno); `C` = campo clave/relación jerárquica; `AE` = campo alfanumérico especial (p. ej. RFC); `S` = **separador** (un carácter de relleno, longitud 1) |
| **Nombre** | nombre interno del registro (`poliza.1`, `movtopoliza.1`, …) o del campo (`Fecha`, `IdCuenta`, …) |
| **Longitud** | ancho fijo en caracteres que ocupa el elemento |
| **Formato** | para `E`: el **marcador** del registro (`P`, `M`, `D`, `V`, `AD`, …); para campos: máscara (`yyyyMMdd`) o dominio booleano (`1,0` = se emite `1`/`0`) |
| **Alineación** | `derecha` cuando el campo se alinea a la derecha; por defecto a la izquierda |

**Reglas de serialización** (derivadas de la estructura; **verificar contra una importación real**
antes de dar por cerrada la Fase 2 — ver §6):

- El archivo es **texto plano**, **una línea por registro**, orden de registros = orden lógico
  (una `P` seguida de sus `M`, luego registros opcionales de esa póliza, luego la siguiente `P`).
- Cada línea se arma **concatenando en orden** cada elemento de la estructura, ocupando
  exactamente su `Longitud`. Los elementos `S` (longitud 1) son separadores literales entre
  campos; **no todos los campos llevan `S`** (p. ej. `Concepto`→`SistOrig` en la póliza van
  pegados), por eso el layout es **posicional estricto**: hay que respetar la tabla al carácter.
- **Codificación `Windows-1252` (ANSI)**, saltos `CRLF`. CONTPAQi es una app x86 nativa mexicana:
  los acentos van en Latin-1, no UTF-8. (Contraste con la DIOT, que sí es UTF-8; ver
  `sat_descarga/diot/exportar.py`.)
- **Campos de referencia (`R`)**: se escribe el **código de negocio**, no el Id numérico. Para
  `IdCuenta` → el **código de la cuenta contable** tal como existe en el catálogo (`Cuentas.Codigo`,
  Varchar 30), **sin guiones ni puntos** si el catálogo se definió sin máscara. Para `IdDiario`,
  `IdSegNeg` → el código del diario especial / segmento de negocio (vacío si no se usan).
- **Montos**: numéricos con **punto** decimal, sin separador de miles, ancho 20.
- **Booleanos** (`Impresa`, `Ajuste`, `TipoMovto`): formato `1,0` → se emite `1` o `0`.
- **Cuadre obligatorio**: por póliza, Σ cargos = Σ abonos (CONTPAQi rechaza pólizas descuadradas).

## 2. Registro `P` — encabezado de póliza (`poliza.1`)

Campos en orden exacto de `CT_EST_Poliza_NG.xls`. "Pos." = posición inicial 1-indexada
asumiendo que cada elemento consume su `Longitud` en secuencia (incluidos los separadores `S`).

| Pos. | Campo | Tipo | Long. | Formato / valores | Obl. | Semántica (tabla `Polizas`) |
|---|---|---|---|---|---|---|
| 1 | *(marcador)* | E | 2 | `P` | Sí | Identifica el registro de encabezado |
| 4 | `Fecha` | A | 8 | `yyyyMMdd` | Sí | Fecha de la póliza |
| 13 | `TipoPol` | A | 4 | `1`=Ingresos, `2`=Egresos, `3`=Diario, `4`=Orden, `5`=Estadística, `6+`=usuario | Sí | Tipo de póliza |
| 18 | `Folio` | A | 9 | entero | Sí | Folio/número de la póliza |
| 28 | `Clase` | A | 1 | `1`=Normal (se afecta), `2`=Sin afectar | Sí | Clase de póliza |
| 30 | `IdDiario` | R | 10 | código del diario especial | No | Vacío si no se usan diarios |
| 41 | `Concepto` | A | 100 | texto | Sí | Concepto de la póliza |
| 141 | `SistOrig` | A | 3 | `11` = CONTPAQi Contabilidad | Reco. | Sistema origen a estampar |
| 145 | `Impresa` | A | 1 | `1,0` | No | `0` |
| 147 | `Ajuste` | A | 1 | `1,0` | No | `0` = póliza normal |
| 149 | `Guid` | A | 36 | GUID | No | Vacío → CONTPAQi lo genera |

## 3. Registro `M` — movimiento / asiento (`movtopoliza.1`)

Una línea `M` por cada cargo o abono. Van inmediatamente después de su `P`.

| Pos. | Campo | Tipo | Long. | Formato / valores | Obl. | Semántica (tabla `MovimientosPoliza`) |
|---|---|---|---|---|---|---|
| 1 | *(marcador)* | E | 2 | `M` | Sí | Identifica un movimiento |
| 4 | `IdCuenta` | R | 30 | **código** de cuenta contable, sin guiones | Sí | La cuenta que afecta (`Cuentas.Codigo`) |
| 35 | `Referencia` | A | 10 | texto | No | Referencia del movimiento (Varchar 10) |
| 46 | `TipoMovto` | A | 1 | `0`=Cargo, `1`=Abono | Sí | Cargo/abono |
| 48 | `Importe` | A | 20 | decimal con punto, > 0 | Sí | Importe del movimiento |
| 69 | `IdDiario` | R | 10 | código diario | No | |
| 80 | `ImporteME` | A | 20 | decimal | No | Importe en moneda extranjera (`0` en MXN) |
| 101 | `Concepto` | A | 100 | texto | No | Concepto del movimiento |
| 202 | `IdSegNeg` | R | 4 | código segmento | No | Segmento de negocio |

> **Cargo = 0, Abono = 1.** El diccionario define el campo booleano de la BD como
> `False = Cargo / True = Abono`; en el archivo (formato `1,0`) eso se emite como `0`/`1`.

## 4. Registros opcionales de la estructura `CT_EST_Poliza_NG`

La estructura define muchos más registros que enriquecen la póliza. Los relevantes para
TodoConta, en orden de utilidad:

| Marcador | Registro | Para qué sirve | Campos clave |
|---|---|---|---|
| **`AD`** | `asocdocto.1` | **Asocia un CFDI (UUID) a la póliza** a nivel documento → alimenta el ADD y la tabla `AsocCFDIs`. **Esta es la asociación UUID↔póliza por archivo, sin SDK.** | `UUID` (36) |
| **`AM`** | `asocmovto.1` | Asocia un UUID a nivel **movimiento** | `UUID` (36) |
| **`V`** | `devolucion.1` | Registro de **causación/control de IVA y DIOT**: proveedor, base, IVA, retenciones, UUID, RFC. Necesario si quieres que la póliza alimente la DIOT y el control de IVA de CONTPAQi | `IdProveedor`, `ImpTotal`, `PorIVA`, `ImpBase`, `ImpIVA`, `Serie`, `Folio`, `Referencia`, `IVARetenido`, `ISRRetenido`, `UUID`, `RFC`, `IEPS`, `IVAPagNoAcred` |
| **`C`** / **`D`** | `causacion.1` / `.2` | Desglose de IVA por tasa a nivel póliza (Tot/Base/IVA por 16/8/0/exento/otra, retenciones) | `TotTasa16`, `BaseTasa16`, `IVATasa16`, … `IVARetenido`, `ISRRetenido`, `IEPS` |
| **`MC`** | `movimientocfd.1` | Movimiento con **flujo de efectivo** detallado (cuenta neto/IVA/impuestos/retenciones/otros gastos) para contabilidad electrónica avanzada | `UUID`, `IdCuentaNeto`, `ImporteIVA`, `IdCuentaIVA`, retenciones, `TipoCambio`… |
| **`FE`** | `poliza.2` | Adjunta un **archivo/anexo** a la póliza (`Polizas.RutaAnexo` / `ArchivoAnexo`) | `RutaAnexo` (254), `ArchivoAnexo` (254) |

Para un **MVP de exportación** basta con `P` + `M` (+ `AD` para conservar la trazabilidad del
UUID). `V`/`C`/`D`/`MC` se agregan cuando se quiera que la póliza además alimente DIOT y control
de IVA dentro de CONTPAQi.

## 5. Variantes de esquema y cuál usar

En `C:\Compac\Empresas\Esquemas\Contpaq\` conviven varias estructuras; difieren en longitudes y
en si el número de póliza es de 1 dígito (`ContPAQ WIN` clásico) o multi-dígito (`ContPAQ NG`):

| Esquema | Uso | Diferencia clave |
|---|---|---|
| **`CT_EST_Poliza_NG.xls`** | **Recomendado** para CONTPAQi Contabilidad moderno | `Referencia` de 30 en el registro `M1`, catálogo completo de registros (AD/AM/V/MC/FE) |
| `CT_EST_Poliza_NG_Referencia10.xls` | Igual pero `Referencia` a 10 | Menos registros opcionales |
| `CT_EST_Poliza_WIN_TIPOPOL_1.xls` | ContPAQ Windows heredado, tipo de póliza de **1 dígito**, cuentas a **20** chars | `TipoPol` Long. 1, `IdCuenta` Long. 20, sin `Guid` |
| `CT_EST_Poliza_WIN_TIPOPOL_3.xls` | Igual pero tipo de póliza de 3 dígitos | |
| `CT_EST_Prepoliza_NG.xls` | **Prepólizas** (plantillas revisables antes de afectar) — vía aún más segura, el contador revisa antes de generar la póliza real | Registro `R`=`prepolizas.1`, importes pueden ser fórmulas (`%`, `(1)`=base+IVA, `(4)`=ret ISR 10%, etc.) |
| `CT_EST_Cuenta_NG.xls` | Alta/actualización del **catálogo de cuentas** (registro `F`/`C`/`E`) | `Codigo`(30), `Nombre`(50), `CtaMayor`, `IdAgrupadorSAT`(20) |

**Decisión para sat-dm**: generar contra `CT_EST_Poliza_NG` (registros `P`+`M`+`AD`), y ofrecer
`CT_EST_Prepoliza_NG` como modo "revisar antes de afectar". La estructura elegida debe empatar la
que el usuario seleccione en CONTPAQi al importar; se documenta como paso de configuración.

## 6. Procedimiento de importación en CONTPAQi y errores típicos

1. En CONTPAQi Contabilidad: menú **Importación → Importar otros sistemas** (o *Formatos de
   importación*), elegir la estructura `CT_EST_Poliza_NG` y el archivo `.txt` generado.
2. CONTPAQi lee cada línea según la estructura y crea las pólizas.
3. Con `Clase = 1` las pólizas quedan afectadas; con `Clase = 2` quedan "sin afectar" para revisión.

Errores frecuentes (a manejar/prevenir desde el generador):

- **Cuenta inexistente**: `IdCuenta` no existe en el catálogo → la póliza se rechaza. Mitigación:
  validar contra el catálogo leído por SQL (ver `03-lectura-sql-server.md`) antes de exportar.
- **Póliza descuadrada**: Σcargos ≠ Σabonos → error. El generador debe cuadrar (cuenta de
  redondeo si hace falta).
- **Periodo cerrado / fecha fuera de ejercicio**: `Fecha` cae en un periodo ya cerrado.
- **Formato posicional corrido**: un campo que excede su ancho recorre todo el resto de la línea.
  Por eso el layout es DATO estricto y debe validarse con un golden file (como la DIOT).

## 7. Ejemplo (factura de ingreso PUE, IVA 16%)

Factura emitida: subtotal $1,000.00, IVA 16% $160.00, total $1,160.00, cobrada al contado.
Póliza de ingreso (tipo 1), 3 movimientos que cuadran ($1,160 = $1,160):

```
Cargo  Bancos                1101-0001   1160.00
Abono  Ventas                4101-0001   1000.00
Abono  IVA trasladado        2102-0001    160.00
```

Representación conceptual del archivo (marcadores al inicio de línea; `▯` = separador):

```
P▯20260709▯1▯000000123▯1▯          ▯Ingreso factura A-123 PUE ...▯11 ▯0▯0▯...
M▯11010001                     ▯A-123     ▯0▯1160.00             ▯          ▯0.00                ▯Cobro cliente ACME ...▯
M▯41010001                     ▯A-123     ▯1▯1000.00             ▯          ▯0.00                ▯Venta ACME ...▯
M▯21020001                     ▯A-123     ▯1▯160.00              ▯          ▯0.00                ▯IVA trasladado ...▯
AD▯5F2A1C0E-...-UUID-36-chars-...
```

> El ejemplo ilustra el orden y los campos; el relleno exacto a ancho fijo lo produce el
> serializador (§Propuesta) y debe validarse posición por posición contra `CT_EST_Poliza_NG.xls`.

## 8. Propuesta de implementación en sat-dm *(no implementado)*

Gemelo estructural del módulo DIOT. **El layout es DATO, no código** — misma filosofía que
`sat_descarga/diot/layout.py`. **Multiplataforma**: generar el TXT es Python puro (encoding +
formateo), sin SQL ni COM ni CONTPAQi local → corre igual en Mac/Windows/Linux. El **catálogo de
cuentas** entra como input cargado (archivo) o auto-leído por SQL cuando aplica; ver
`04-mapeo-cfdi-poliza.md` §3.

**Módulo nuevo `sat_descarga/contpaq/`:**

- `layout_poliza.py` — dataclass `CampoPoliza(clave, tipo, longitud, formato, alineacion)` y las
  tuplas `REGISTRO_P`, `REGISTRO_M`, `REGISTRO_AD` en orden exacto (transcritas de
  `CT_EST_Poliza_NG.xls`), más `formatear_registro(marcador, campos, fila)` que rellena a ancho
  fijo en `windows-1252`. Espejo de `CampoDiot` / `formatear_linea`.
- `exportar_poliza.py` — `exportar_txt(polizas: list[Poliza]) -> bytes` (encoding `cp1252`,
  CRLF), `nombre_archivo(rfc, periodo)`. Espejo de `sat_descarga/diot/exportar.py`.
- `mapeo.py` — CFDI → asientos (ver `04-mapeo-cfdi-poliza.md`).
- `modelo.py` — dataclasses `Poliza` (tipo, fecha, folio, clase, concepto, movimientos) y
  `MovimientoPoliza` (codigo_cuenta, tipo_movto, importe, referencia, concepto, uuid).

**Router `sat_descarga/api/routers/contpaq.py`** (montar en `sat_descarga/api/server.py`, junto a
los `include_router` existentes; contrato calcado de `routers/diot.py`):

- `POST /contpaq/polizas/preview` — body: `{ rfc, periodo, config_cuentas }` → arma las pólizas
  desde los CFDIs del buffer del procesador y devuelve JSON revisable (asientos, cuadre, warnings
  de cuentas faltantes). No escribe archivo.
- `POST /contpaq/polizas/exportar` — igual, pero devuelve el `.txt` (`StreamingResponse`,
  `text/plain; charset=windows-1252`), como el export de la DIOT.
- `GET /contpaq/esquemas` — lista las estructuras `CT_EST_*` detectadas en
  `C:\Compac\Empresas\Esquemas\Contpaq\` para que la UI diga cuál seleccionar al importar.

**Fuente de datos**: la tabla `cfdis` de `~/.sat-descarga/procesador.db`
(`sat_descarga/procesador/db.py`), que ya guarda cada CFDI parseado con `raw_json` = `CfdiData`
completo. No se re-parsea nada.

**Verificación** (espejo del golden file de la DIOT): fixture con un CFDI de ingreso y su TXT
esperado, comparado byte a byte; y una prueba de cuadre (Σcargos == Σabonos por póliza).

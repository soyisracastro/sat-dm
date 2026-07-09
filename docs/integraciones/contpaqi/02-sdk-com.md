# CONTPAQi Contabilidad — Escritura vía SDK COM (vía B)

> **Fuente**: **type library del SDK extraída de la instalación 14.4.2**
> (`C:\Program Files (x86)\Compac\SDK\SDKCONTPAQNG.exe`, recurso `TYPELIB`, "SDKCONTPAQNG 1.0
> Type Library"), el registro de Windows, y el diccionario de BD. Todos los nombres de clase,
> método y enum de este documento están **verificados contra la type library instalada**, salvo
> los marcados *(por verificar)* — cuya firma exacta (parámetros/orden) se confirma abriendo la
> type library con el Object Explorer de Visual Studio o con `comtypes`/`win32com` sobre la
> instalación real.

Vía de escritura **en tiempo real**: registra pólizas directamente en CONTPAQi respetando sus
reglas de negocio y asociando el UUID al ADD al instante. Es la **Fase 2 profunda** del pitch
(línea 206). Requiere **licencia del SDK habilitada** (ver §2).

## 1. Naturaleza del SDK (lo que se confirmó en esta máquina)

- Es un **componente COM (ActiveX) orientado a objetos** llamado **`SDKCONTPAQNG`** (NG = Nueva
  Generación). **No** es la DLL nativa `MGWServicios.dll` (esa es del SDK **Comercial**/Adminpaq,
  con Firebird y funciones `f...`). Confusión común: aquí es COM + SQL Server.
- **51 clases COM registradas** (`SDKCONTPAQNG.T*`), entre ellas `TSdkSesion`, `TSdkPoliza`,
  `TSdkMovimientoPoliza`, `TSdkCuenta`, `TSdkAsocCFDI`, `TSdkEmpresa`, `TSdkListaEmpresas`,
  `TSdkProveedor`, `TSdkCliente`, `TRepBalanza`, `TRepEstadoResultados`. (Lista completa en el
  apéndice.)
- **Servidor COM fuera de proceso** (`LocalServer32` → `SDKCONTPAQNG.exe`), **no** in-proc DLL.
  Detalle de arquitectura importante (ver §4): al ser out-of-process y x86, el *marshalling* de
  COM puede cruzar la frontera de bits, por lo que un cliente **x64** podría instanciarlo.
  - `TSdkSesion` → CLSID `{37832F46-19C5-4B16-A738-CF54CAE1226E}`, ProgID
    `SDKCONTPAQNG.TSdkSesion` / `.1`, TypeLib `{4A6A81F3-B2B3-448C-A557-A005091BE801}` v1.0.
- **Motor de datos**: SQL Server (las mismas bases `ct*` de `03-lectura-sql-server.md`); el SDK
  aplica las reglas de negocio (afectación de saldos, control de IVA, ADD) que un `INSERT` crudo
  no haría.

## 2. Requisitos y cómo verificar si el SDK está habilitado

Requisitos duros:

- **Windows** con CONTPAQi Contabilidad instalado (el servidor COM y el motor SQL son locales).
- **Licencia del SDK habilitada.** El registro estar presente **no** implica licencia activa: la
  activación se contrata con CONTPAQi o un distribuidor autorizado (p. ej. Compuflash). Sin
  licencia, `abreEmpresa` falla.
- **Ejecución como Administrador** (recomendado por el SDK).

**Cómo verificar en la máquina objetivo** (todo solo-lectura):

1. **¿El SDK está instalado/registrado?** — En esta máquina **sí**:
   `HKLM\SOFTWARE\WOW6432Node\Computación en Acción, SA CV\CONTPAQ I SDK` existe con
   `VERSION = 14.4.2`, `DIRECTORIOBASE = C:\Program Files (x86)\Compac\SDK`,
   `DIRECTORIOEMPRESAS = C:\Compac\Empresas`, y subclaves de versiones históricas
   (`12.1.1`, `12.2.5`, `13.5.1`, `14.0.1`, `14.4.1`, `14.4.2`).
2. **¿El servidor COM responde?** — `SDKCONTPAQNG.exe` está en `C:\Program Files (x86)\Compac\SDK\`
   y los ProgID `SDKCONTPAQNG.*` están en `HKLM\SOFTWARE\Classes`. Instanciar `TSdkSesion` +
   `iniciaConexion()` prueba el registro; **abrir una empresa** prueba la **licencia**.
3. **¿La licencia cubre el SDK?** — sólo se confirma intentando `abreEmpresa()` sobre una empresa
   real, o preguntando al distribuidor. Documentar como paso de habilitación previo a la Fase 2.

## 3. Referencia de la API (verificada contra la type library instalada)

### `TSdkSesion` — sesión y empresa
| Método | Uso |
|---|---|
| `iniciaConexion()` | Inicia el SDK / la conexión |
| `firmaUsuario(usuario, password)` · `firmaUsuarioParams(...)` | Autenticación de usuario CONTPAQi |
| `abreEmpresa(aliasEmpresa)` | Abre la empresa (prueba la licencia del SDK) |
| `cierraEmpresa()` | Cierra la empresa |
| `finalizaConexion()` | Cierra el SDK |
| `conexionActiva` | Bandera de conexión |
| `iniciaLoteFunciones()` · `guardaPolizasEnLote(...)` | Alta de pólizas **en lote** (más rápido para volumen) |
| `getCodigoError()` · `getMensajeError()` · `UltimoMsjError` · `DespliegaMensajesError()` | **Manejo de errores** (ver §5) |

### `TSdkPoliza` — encabezado de póliza
| Miembro | Uso |
|---|---|
| `iniciarInfo()` | Inicializa una póliza nueva en blanco |
| propiedades `Fecha`, `Tipo`/`TipoPoliza`, `Numero`/`Folio`, `Clase`, `Concepto`, `SistOrig`, `Guid` | Datos del encabezado |
| `agregaMovimiento(movimiento)` | Agrega un `TSdkMovimientoPoliza` a la póliza |
| `crea()` | **Persiste** la póliza con sus movimientos |
| `borra()` | Elimina |
| `getMovimientoPrimero()` · `getMovimientoSiguiente()` · `obtenerMovtosPoliza()` | Recorre movimientos (lectura) |
| `consultaGuid_buscaPorLlavePoliza(...)` · `consultaPolizasPorSistOrigenRango_*` | Consulta de pólizas existentes |

### `TSdkMovimientoPoliza` — asiento
| Miembro | Uso |
|---|---|
| `iniciarInfo()` *(por verificar)* | Inicializa un movimiento |
| propiedades `CodigoCuenta`, `TipoMovto`, `Importe`, `ImporteME`, `Referencia`, `Concepto`, `IdDiario`, `SegNeg`, `Guid` | Datos del movimiento. `CodigoCuenta` = código de cuenta **sin guiones** (asignar una cuenta inexistente lanza HRESULT `0x80010105`) |
| `creaMovimiento()` · `borraMovimiento()` | Alta/baja de movimiento |

### `TSdkAsocCFDI` — asociación de CFDI (UUID → ADD)
| Miembro | Uso |
|---|---|
| propiedad `UUID` | UUID del CFDI a asociar a la póliza/movimiento |
| `borraPorUUID(uuid)` | Elimina la asociación |

Asocia el CFDI descargado a la póliza dentro del ADD (tabla `AsocCFDIs`). Es el equivalente en SDK
del registro `AD` del archivo TXT.

### `TSdkCuenta` — catálogo de cuentas
`ejecutaBusquedaCuenta(...)`, `getCuenta(...)`, `obtenerCuentas()`, `obtenerCuentasHijas()`,
`siguienteCuenta()`, `existenCuentasConConsumo`, `crea()` *(para dar de alta cuentas)*. Útil para
validar/crear cuentas antes de asentar.

### Enumeraciones (verificadas)
- **Tipo de póliza** (`ETIPOPOLIZA`): `TIPO_INGRESOS`, `TIPO_EGRESOS`, `TIPO_DIARIO`, `TIPO_ORDEN`,
  `TIPO_ESTADISTICAS`.
- **Clase** (`ECLASEPOLIZA`): `CLASE_AFECTAR`, `CLASE_SINAFECTAR`.
- **Tipo de movimiento** (`ETIPOIMPORTEMOVPOLIZA`): `MOVPOLIZA_CARGO`, `MOVPOLIZA_ABONO`.

### Reportes de lectura (alternativa al SQL directo)
`TRepBalanza`, `TRepCuenta`, `TRepEstadoResultados`, `TRepEstadoFinanciero` permiten leer saldos y
estados financieros **por SDK** respetando reglas de negocio (más seguro que el SQL crudo del
doc 03, aunque más lento).

## 4. Arquitectura de host: cómo llamar COM desde el agente Python

El agente principal (`sat_descarga/`) es Python empaquetado x64. Tres opciones, con recomendación:

**Opción A — Cliente COM directo desde el agente (a validar primero).**
Como el servidor es **out-of-process** (`LocalServer32`), el marshalling de COM cruza la frontera
x86/x64: el agente x64 podría hacer `win32com.client.Dispatch("SDKCONTPAQNG.TSdkSesion")` (pywin32)
o `comtypes.client.CreateObject(...)` **sin sidecar**. Es la opción más simple **si funciona** en
la práctica (el SDK de CONTPAQi ha sido históricamente quisquilloso; **hay que probarlo**). Agregar
`pywin32`/`comtypes` a `install_requires` y a `hiddenimports` de `packaging/sat-agent.spec`.

**Opción B — Sidecar Python x86 (recomendada si A falla).**
Un proceso auxiliar **de 32 bits** empaquetado con su propio `.spec` de PyInstaller (paralelo a
`packaging/sat-agent.spec`), que usa `comtypes`/`pywin32` contra el SDK y expone un mini-protocolo
(JSON por stdio, o un HTTP local en 127.0.0.1) al agente principal. **Ventaja**: stack homogéneo
Python, sin toolchain .NET; el agente x64 no se contamina y el sidecar sólo se lanza cuando hay que
escribir. Elimina cualquier duda de bitness.

**Opción C — Host Web API .NET x86 (alternativa madura).**
Un servicio .NET Framework compilado x86 que envuelve el SDK y expone REST, siguiendo el patrón
público `ARSoftware.Contpaqi.Contabilidad.Api` (repos de AndresRamos, junto con
`Contpaqi.Sdk.Contabilidad`). Más robusto y con ejemplos, pero **introduce .NET** al proyecto.

**Descartada** — migrar todo el agente a Python x86: penaliza `lxml`/rendimiento y reempaqueta todo
por una sola integración.

> Recomendación: **probar A** (barato); si el SDK no coopera cross-bitness, caer a **B**. Reservar
> **C** si se quiere reutilizar el ecosistema .NET existente de CONTPAQi.

## 5. Manejo de errores

El SDK NG reporta por dos vías: **excepciones COM/HRESULT** (p. ej. `0x80010105`
`RPC_E_SERVERFAULT` al asignar una `CodigoCuenta` inexistente) y **códigos consultables**
(`getCodigoError()` / `getMensajeError()` / `UltimoMsjError`). El wrapper debe: envolver cada
llamada, mapear HRESULT + `getMensajeError()` a un error de dominio, y **nunca** dejar una empresa
abierta si falla (`cierraEmpresa` + `finalizaConexion` en `finally`).

## 6. Flujo de alta de póliza (pseudocódigo)

```text
sesion = COM("SDKCONTPAQNG.TSdkSesion")
sesion.iniciaConexion()
sesion.firmaUsuario(usuario, password)
sesion.abreEmpresa(alias_empresa)          # falla aquí si no hay licencia SDK
try:
    pol = COM("SDKCONTPAQNG.TSdkPoliza")
    pol.iniciarInfo()
    pol.Fecha = fecha; pol.Tipo = TIPO_INGRESOS; pol.Concepto = concepto
    pol.Clase = CLASE_AFECTAR               # o CLASE_SINAFECTAR para revisar antes
    for asiento in asientos:
        m = COM("SDKCONTPAQNG.TSdkMovimientoPoliza")
        m.CodigoCuenta = asiento.codigo_cuenta   # sin guiones
        m.TipoMovto = MOVPOLIZA_CARGO if asiento.es_cargo else MOVPOLIZA_ABONO
        m.Importe = asiento.importe
        m.Referencia = asiento.referencia; m.Concepto = asiento.concepto
        pol.agregaMovimiento(m)
    pol.crea()                              # persiste la póliza cuadrada
    # asociar el CFDI al ADD:
    asoc = COM("SDKCONTPAQNG.TSdkAsocCFDI"); asoc.UUID = uuid    # (firma exacta por verificar)
    # ... vincular asoc a la póliza recién creada
finally:
    sesion.cierraEmpresa()
    sesion.finalizaConexion()
```

Para volumen: `iniciaLoteFunciones()` + `guardaPolizasEnLote()` en lugar de `crea()` por póliza.

## 7. Propuesta de implementación en sat-dm *(no implementado)*

- **Módulo `sat_descarga/contpaq/sdk/`** (o sidecar `sat_descarga/contpaq_sdk_host/` si Opción B):
  cliente COM que traduce los modelos `Poliza`/`MovimientoPoliza` (los mismos de
  `01-importacion-txt-polizas.md`) a llamadas del SDK.
- **Router `routers/contpaq.py`**:
  - `GET /contpaq/sdk/estado` — verifica registro + intenta `abreEmpresa` para reportar si la
    licencia está habilitada.
  - `POST /contpaq/sdk/polizas` — alta directa (o en lote) con asociación de UUID.
- **Reutiliza el mapeo** de `04-mapeo-cfdi-poliza.md`: la diferencia con la vía TXT es sólo el
  *sink* (COM en vez de archivo); el armado de asientos es idéntico.
- **Verificación**: contra una empresa demo con licencia SDK, dar de alta una póliza de prueba,
  confirmarla en CONTPAQi (afectada + UUID asociado en el ADD) y luego borrarla.

## Apéndice — Clases COM registradas (`SDKCONTPAQNG.T*`, 14.4.2)

`TSdkSesion`, `TSdkEmpresa`, `TSdkListaEmpresas`, `TSdkUsuario`, `TSdkEjercicio`, `TSdkPoliza`,
`TSdkMovimientoPoliza`, `TSdkTipoPoliza`, `TSdkDialogoPoliza`, `TSdkCuenta`, `TSdkCuentaAgrupadora`,
`TSdkAgrupadorSAT`, `TSdkDiarioEspecial`, `TSdkSegmentoNegocio`, `TSdkMoneda`, `TSdkPais`,
`TSdkCliente`, `TSdkProveedor`, `TSdkConcepto`, `TSdkFolio`, `TSdkDigitoFiscal`, `TSdkFlujoEfectivo`,
`TSdkControlIVA`, `TSdkCausacionIVA`, `TSdkAsocCFDI`, `TSdkAsociacion`, `TSdkAsociacionAdminPAQ`,
`TSdkAsociacionCategoria`, `TSdkAsocCompraVenta`, `TAsocCargoAbono`, `TAsocCompraVenta`,
`TSdkCategoria`, `TSdkPresupuestoCategoria`, `TSdkBanco`, `TSdkCuentaCheque`, `TSdkCheque`,
`TSdkEgreso`, `TSdkIngreso`, `TSdkIngresoNoDepositado`, `TSdkDeposito`, `TSdkTraspaso`,
`TSdkSaldosCtaCheques`, `TSdkDocumentoDe`, `TSdkTipoDocumento`, `TSdkHojaElectronica`,
`TSdkConvierteProyectadosRe`, `TImportes12P`, `TRepBalanza`, `TRepCuenta`, `TRepEstadoResultados`,
`TRepEstadoFinanciero`, `TRepLegal`.

## Nota de versión (14 → 19)

Esta referencia se extrajo de **14.4.2**. En la v19 los ProgID/CLSID, la firma exacta de métodos y
los requisitos de licencia **pueden cambiar** (el instalador v19 trae un instalador dedicado del
SDK, `CTNGSDK\CONTPAQi_SDK.exe`). Antes de implementar la Fase 2 contra v19, re-extraer la type
library de esa versión y hacer diff (ver `05-roadmap.md`).

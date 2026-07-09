# CONTPAQi Contabilidad — Lectura de información (vía C, SQL Server read-only)

> **Fuente**: *Diccionario de la Base de Datos de CONTPAQi Contabilidad*
> (`C:\Program Files (x86)\Compac\Contabilidad\BDDCONTPAQi.pdf`, "Última modificación: 18 junio
> 2020"), más el registro de Windows de la instalación **14.4.2**. Los nombres de tabla y campo de
> este documento están transcritos de ese diccionario.

Esta es la vía de **solo lectura**: la más realista y cercana según
`docs/presentacion-pitch.md` (líneas 196-202, "Fase 1 — LEER"). Habilita **conciliación
CFDI↔póliza** y lectura del **catálogo de cuentas y saldos** sin recapturar nada. **No requiere
licencia del SDK.**

## 1. Motor y descubrimiento de conexión

- **Motor**: Microsoft SQL Server (Express). Confirmado: no hay Firebird en la instalación
  (`DigitalStorage.dll.config` → `Data Source=.\SQLExpress`), las empresas se respaldan como `.bak`
  nativos de SQL Server, y `C:\Compac\Empresas\` contiene los datos.
- **Instancia**: típicamente `.\COMPAC` o `.\SQLEXPRESS` (localhost). El instalador la registra;
  se puede descubrir enumerando instancias SQL locales o leyendo la config de CONTPAQi.
- **Mapa empresa → base de datos**: cada empresa es una base cuyo nombre es el de su carpeta en
  `C:\Compac\Empresas\` (p. ej. `CtEmpresa1`, `ctAJUCHITLAN`), con una base **ADD** asociada
  (`adCtEmpresa1`) para el almacén digital de documentos. El directorio base de empresas está en el
  registro: `HKLM\SOFTWARE\WOW6432Node\Computación en Acción, SA CV\CONTPAQ I SDK\DIRECTORIOEMPRESAS`
  = `C:\Compac\Empresas`.
- **Autenticación**: instancia local; usar el usuario de SQL de CONTPAQi (existe un
  `SuaConnection.ini` con credenciales en `C:\Compac\Empresas\` — tratar con cuidado, no loguear) o,
  mejor, **crear un login SQL de solo lectura** dedicado para TodoConta (ver §3).

## 2. Tablas clave (transcritas del diccionario)

### `Cuentas` — Catálogo de Cuentas
Campos relevantes: `Id`, **`Codigo`** (Varchar 30 — el código contable, la llave de negocio que usa
la importación TXT), `Nombre` (Varchar 50), `Tipo`, `CtaMayor` (1=Mayor, 2=No, 3=Título,
4=Subtítulo), `Afectable` (0=No, 1=Sí), `IdAgrupadorSAT`, `SistOrigen` (11=CONTPAQi Contabilidad).

### `Polizas` — encabezados de póliza
`Id`, `Ejercicio`, `Periodo`, **`TipoPol`** (1=Ingresos, 2=Egresos, 3=Diario, 4=Orden,
5=Estadística, 6+=usuario), **`Folio`**, `Clase` (1=Normal, 2=Sin afectar), `Concepto` (Varchar
100), **`Fecha`**, **`Cargos`** / **`Abonos`** (totales), `IdDiario`, `SistOrig` (11=CONTPAQi),
`RutaAnexo` / `ArchivoAnexo` (CFDI/anexo asociado, Varchar 254), **`Guid`** (36).

### `MovimientosPoliza` — asientos de cada póliza
`Id`, **`IdPoliza`** (FK a `Polizas`), `Ejercicio`, `Periodo`, `TipoPol`, `Folio`, `NumMovto`,
**`IdCuenta`** (FK a `Cuentas`), **`TipoMovto`** (`False`=Cargo, `True`=Abono), **`Importe`**,
`ImporteME`, `Referencia` (Varchar 10), `Concepto` (Varchar 100), `IdDiario`, `Fecha`, `IdSegNeg`,
`Guid` (36).

### `AsocCFDIs` — asociación de CFDI (UUID) a documentos/pólizas
`Id`, `GuidRef` (Varchar 36 — referencia del comprobante en CONTPAQi), **`UUID`** (Varchar 36 — el
UUID del CFDI timbrado), `Referencia` (Varchar 1000), `AppType` (Varchar 30). **Esta es la tabla
puente para la conciliación UUID↔póliza.**

### `Ejercicios` — ejercicios y periodos
`Id`, `Ejercicio`, `TipoPer` (Mensual/Bimestral/…), `Periodos`, `FecIniEje`/`FecFinEje`,
`FecIniPer1..14`, `IdPolCierre`. Sirve para saber qué periodos están abiertos antes de exportar.

### `SaldosCuentas` — saldos por cuenta/ejercicio/periodo
`Id`, **`IdCuenta`**, `Ejercicio`, `Tipo` (1=Saldos, 2=Cargos, 3=Abonos, 4-6=moneda extranjera),
`SaldoIni`, **`Importes1..14`** (saldo por periodo). Para balanza y reportes sin recapturar.

## 3. Principios de seguridad (obligatorios)

- **Solo `SELECT`.** Jamás `INSERT/UPDATE/DELETE` contra la BD de CONTPAQi: la escritura va por TXT
  (`01-importacion-txt-polizas.md`) o SDK (`02-sdk-com.md`). Escribir directo **corrompe la
  contabilidad y anula el soporte** — regla firme del pitch (línea 224).
- **Login SQL dedicado de solo lectura**: crear un usuario con permiso `db_datareader` sobre las
  bases `ct*`, no reutilizar el `sa` ni las credenciales de la app.
- **Timeouts cortos** y `ApplicationIntent=ReadOnly` cuando aplique. Conexión efímera por consulta.
- No registrar credenciales en logs ni telemetría.

## 4. Casos de uso (con query de ejemplo)

### 4.1 Catálogo de cuentas (para el configurador de mapeo)
```sql
SELECT Codigo, Nombre, CtaMayor, Afectable, IdAgrupadorSAT
FROM   Cuentas
WHERE  Afectable = 1
ORDER  BY Codigo;
```
Alimenta el selector de cuentas por defecto del mapeo (`04-mapeo-cfdi-poliza.md`) y valida que las
cuentas existan antes de exportar el TXT.

### 4.2 Conciliación UUID↔póliza *(el caso estrella del pitch)*
UUIDs contabilizados en CONTPAQi (para cruzar contra los CFDIs de `procesador.db`):
```sql
SELECT a.UUID, p.Ejercicio, p.Periodo, p.TipoPol, p.Folio, p.Fecha, p.Concepto
FROM   AsocCFDIs a
JOIN   Polizas   p ON p.Guid = a.GuidRef      -- o vía MovimientosPoliza según el AppType
ORDER  BY p.Fecha;
```
Del lado TodoConta, los UUID están en `cfdis.uuid` (`~/.sat-descarga/procesador.db`,
`sat_descarga/procesador/db.py`). El agente cruza ambos conjuntos y reporta:
- **CFDIs descargados del SAT que NO están contabilizados** (`cfdis.uuid` ∉ `AsocCFDIs.UUID`).
- **Pólizas sin CFDI que las respalde** (opcional, la dirección inversa).

### 4.3 Pólizas de un periodo (anti-duplicados antes de exportar)
```sql
SELECT TipoPol, Folio, Fecha, Concepto, Cargos, Abonos
FROM   Polizas
WHERE  Ejercicio = @ejercicio AND Periodo = @periodo
ORDER  BY TipoPol, Folio;
```
Evita re-exportar pólizas ya cargadas.

### 4.4 Balanza de comprobación
```sql
SELECT c.Codigo, c.Nombre, s.SaldoIni,
       s.Importes1, s.Importes2 /* ... hasta el periodo deseado */
FROM   SaldosCuentas s
JOIN   Cuentas c ON c.Id = s.IdCuenta
WHERE  s.Ejercicio = @ejercicio AND s.Tipo = 1
ORDER  BY c.Codigo;
```
Cruzable con los XSD de Contabilidad Electrónica del SAT en
`Servidor de Aplicaciones\Extras\schemas\localxsd\` (`BalanzaComprobacion_1_3.xsd`).

## 5. Propuesta de implementación en sat-dm *(no implementado)*

- **Driver**: `pymssql` (más simple de empaquetar con PyInstaller, sin depender del ODBC Driver del
  sistema) o `pyodbc` (requiere el *Microsoft ODBC Driver 17/18 for SQL Server* instalado). **Hoy el
  agente no incluye ninguno** — habría que agregarlo a `install_requires` y a `hiddenimports` en
  `packaging/sat-agent.spec` (la lista donde ya viven los `uvicorn.*`). Recomendación: **`pymssql`**
  por autocontenido.
- **Módulo `sat_descarga/contpaq/lectura.py`**: `descubrir_instancias()`, `listar_empresas()`,
  `catalogo_cuentas(empresa)`, `conciliar_uuids(empresa, rfc)`. Conexión por consulta, solo lectura.
- **Router `routers/contpaq.py`**:
  - `GET /contpaq/conexion/estado` — detecta instancia y empresas disponibles.
  - `GET /contpaq/cuentas?empresa=...` — catálogo de cuentas.
  - `GET /contpaq/conciliacion?empresa=...&rfc=...&periodo=...` — el reporte CFDI↔póliza.
- **Fuente TodoConta**: la tabla `cfdis` (ya existe). El cruce es un `SELECT` local + un `SELECT`
  remoto, unidos en Python por `uuid`.
- **Verificación**: probar contra una empresa demo (p. ej. `CtEmpresa1`); confirmar que la
  conciliación detecta correctamente un UUID contabilizado y uno no contabilizado.

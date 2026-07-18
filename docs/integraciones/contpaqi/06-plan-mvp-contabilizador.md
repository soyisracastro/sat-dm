# Plan de implementación — MVP "Contabilizador CFDI → TXT de pólizas"

Plan accionable de la **Fase 1** (ver `05-roadmap.md`). Objetivo: desde los CFDIs ya parseados en
TodoConta, generar el **archivo TXT de pólizas** que CONTPAQi importa, con **UUID + folio
asociados**, **sin CONTPAQi local** (funciona en Mac). El catálogo de cuentas entra como **input
cargado** (archivo) o auto-leído por SQL cuando aplica.

Todo esto **espeja el módulo DIOT existente** (`sat_descarga/diot/` + `routers/diot.py` +
`docs/producto/diot-2025.md`), que ya resuelve el mismo problema (exportar un archivo de formato fijo desde
los CFDIs) y está probado en producción.

## 0. Decisiones de alcance del MVP

| Decisión | MVP | Diferido |
|---|---|---|
| Escenarios CFDI | Ingreso (I) y Egreso (E), **PUE y PPD** | Pagos (P), Nómina (N), notas de crédito complejas |
| Agrupación | **Una póliza por CFDI** (trazabilidad UUID limpia, un `AD` por póliza) | Póliza agrupada por día/tipo |
| Catálogo | Carga de **CSV / XLSX** (+ `CT_EST_Cuenta_NG`) | Auto-lectura SQL (Fase 2) |
| Dependencias nuevas | **Ninguna** — `openpyxl` (XLSX) ya es dependencia; CSV es stdlib | `pymssql` (Fase 2) |
| Plataforma | Mac/Windows/Linux | — |

> **Cero dependencias nativas nuevas** → el empaquetado PyInstaller (`packaging/sat-agent.spec`) no
> cambia para el MVP. `openpyxl` ya viene con el agente (se usa en `procesador/exportar.py`).

## 1. Módulos nuevos — `sat_descarga/contpaq/`

Estructura gemela de `sat_descarga/diot/`:

### `modelo.py` — modelo contable neutro (independiente del sink TXT/SDK)
```python
@dataclass
class MovimientoPoliza:
    codigo_cuenta: str        # código del catálogo, sin guiones
    es_cargo: bool            # True=cargo, False=abono
    importe: float
    referencia: str = ""      # serie+folio, ≤10
    concepto: str = ""
    importe_me: float = 0.0

@dataclass
class Poliza:
    tipo: int                 # 1=Ingreso, 2=Egreso, 3=Diario
    fecha: str                # yyyyMMdd
    concepto: str
    movimientos: list[MovimientoPoliza]
    clase: int = 2            # 2=Sin afectar (revisar antes) por defecto
    uuid: str = ""            # para el registro AD
    folio: str | None = None  # None → CONTPAQi lo asigna
    def cuadra(self, tol=0.02) -> bool: ...
```

### `layout_poliza.py` — el layout como DATO (espejo de `diot/layout.py`)
- `@dataclass(frozen=True) CampoPoliza(clave, tipo, longitud, formato, alineacion)`.
- Tuplas `REGISTRO_P`, `REGISTRO_M`, `REGISTRO_AD` **transcritas exactamente** de
  `CT_EST_Poliza_NG.xls` (posiciones ya verificadas en `01-importacion-txt-polizas.md` §2-3).
- `formatear_registro(marcador: str, campos, valores: dict) -> str`: rellena cada campo a su ancho
  fijo, alineación y formato (booleanos `1,0`, fecha `yyyyMMdd`), incluyendo los separadores.
- `assert` de longitudes de línea (como el `assert len(CAMPOS_DIOT) == 54`).

### `exportar_poliza.py` — serialización a bytes (espejo de `diot/exportar.py`)
```python
def exportar_txt(polizas: list[Poliza]) -> bytes:
    # valida (cuadre + cuentas) → arma líneas P/M/AD → encode cp1252, CRLF
    ...
def nombre_archivo(rfc: str | None, periodo: str) -> str:  # {RFC}_polizas_{YYYY-MM}.txt
```
Diferencia con la DIOT: encoding **`windows-1252`** (no UTF-8) y una línea por registro P/M/AD.

### `catalogo.py` — ingesta del catálogo de cuentas (el habilitador multiplataforma)
```python
@dataclass
class Cuenta:
    codigo: str; nombre: str
    naturaleza: str = ""      # deudora/acreedora si el archivo la trae
    agrupador_sat: str = ""
    afectable: bool = True

def parse_catalogo(data: bytes, formato: str) -> list[Cuenta]:
    # formato ∈ {"csv", "xlsx", "ct_est_cuenta_ng"}
    # csv/xlsx: detecta columnas Codigo/Nombre (+ opcionales)
    # ct_est_cuenta_ng: registros F/C/E del layout doc 01 §5
def guardar_catalogo(rfc, cuentas): ...   # ~/.sat-descarga/contpaq/catalogo_{RFC}.json
def cargar_catalogo(rfc) -> list[Cuenta] | None: ...
def existe_codigo(catalogo, codigo) -> bool: ...
```
`xlsx` con `openpyxl` (ya disponible), `csv` con stdlib. Sin dependencias nuevas.

### `config.py` — mapeo de cuentas por empresa (espejo de `diot/store.py`)
```python
@dataclass
class ConfigCuentasContpaq:
    clientes: str = ""; proveedores: str = ""
    bancos: str = ""; ventas: str = ""; gastos_default: str = ""
    iva_trasladado_cobrado: str = ""; iva_trasladado_pendiente: str = ""
    iva_acreditable_pagado: str = ""; iva_acreditable_pendiente: str = ""
    iva_retenido: str = ""; isr_retenido: str = ""; ieps: str = ""
    redondeo: str = ""
    reglas_por_rfc: dict[str, str] = field(default_factory=dict)  # RFC → cuenta gasto

def guardar_config(rfc, cfg): ...   # ~/.sat-descarga/contpaq/config_{RFC}.json
def cargar_config(rfc) -> ConfigCuentasContpaq: ...
```
Persistencia idéntica al patrón de la DIOT (`~/.sat-descarga/…/{RFC}.json`).

### `mapeo.py` — CFDI → Poliza (implementa `04-mapeo-cfdi-poliza.md`)
```python
def mapear_cfdi(cfdi: CfdiData, mi_rfc: str, cfg: ConfigCuentasContpaq) -> Poliza:
    es_emitido = (cfdi.emisor_rfc == mi_rfc)
    # dispatch por (tipo_comprobante, es_emitido, metodo_pago) → _ingreso_pue / _egreso_ppd / ...
```
Una función privada por escenario del doc 04 §4. Cada una arma los `MovimientoPoliza` y **exige
cuadre**; si por redondeo no cuadra, ajusta con `cfg.redondeo`.

### `validaciones.py` — pre-export
- `validar_polizas(polizas, catalogo) -> {errores, warnings}`: cuadre por póliza, y **cada
  `codigo_cuenta` existe en el catálogo cargado** (si no, warning con la cuenta faltante).

### `agregacion.py` — fuente de datos
- `construir_polizas(rfc, periodo, cfg, catalogo) -> list[Poliza]`: lee los CFDIs del periodo desde
  `procesador.db` (tabla `cfdis`, `raw_json` → `CfdiData`, vía `ProcesadorDB` de
  `sat_descarga/procesador/db.py`), aplica `mapear_cfdi` a cada uno, devuelve las pólizas. **No
  re-parsea XML.**

## 2. Router — `sat_descarga/api/routers/contpaq.py`

Montar en `sat_descarga/api/server.py` con `app.include_router(...)` junto a los existentes.
Contrato calcado de `routers/diot.py` (mismo `_rfc_requerido`, `_validar_periodo_http`).

| Método | Endpoint | Body / query | Devuelve |
|---|---|---|---|
| `POST` | `/contpaq/catalogo` | multipart: archivo + `rfc` + `formato` | `{cargadas: N, muestra: [...]}` |
| `GET` | `/contpaq/catalogo` | `rfc` | estado del catálogo (N cuentas, origen, fecha) |
| `GET` | `/contpaq/config` | `rfc` | `ConfigCuentasContpaq` actual |
| `PUT` | `/contpaq/config` | `{rfc, config}` | config guardada |
| `POST` | `/contpaq/polizas/preview` | `{rfc, periodo}` | `{polizas:[{cfdi_uuid, tipo, asientos, cuadra}], warnings, cuentas_faltantes}` |
| `POST` | `/contpaq/polizas/exportar` | `{rfc, periodo}` | `StreamingResponse` TXT `text/plain; charset=windows-1252` |
| `GET` | `/contpaq/esquemas` | — | estructuras `CT_EST_*` detectadas (solo si CONTPAQi local; opcional) |

Como en la DIOT (`routers/diot.py`), el gating premium del export vive en el frontend; el agente no
re-valida licencia por endpoint.

## 3. Contrato del feature de UI

Pantalla **"Contabilizador CONTPAQi"** por empresa (RFC) y periodo, estilo asistente. Usa
`window.satAgent` (baseUrl + token) como el resto de la UI (`desktop/preload.js`).

1. **Catálogo de cuentas** — botón *Cargar archivo* (CSV/XLSX) → `POST /contpaq/catalogo`; muestra
   "N cuentas cargadas". Si el agente detecta CONTPAQi local (Fase 2), ofrece *Leer de CONTPAQi*.
2. **Mapeo de cuentas** — formulario con cada campo de `ConfigCuentasContpaq`; cada uno es un
   **selector que autocompleta desde el catálogo cargado** (código + nombre). Guarda con
   `PUT /contpaq/config`.
3. **Vista previa** — `POST /contpaq/polizas/preview`: tabla por CFDI → asientos (cargo/abono,
   cuenta, importe), indicador de **cuadre** ✓/✗, y panel de **cuentas faltantes** (las que hay que
   dar de alta en CONTPAQi o remapear).
4. **Descargar TXT** — `POST /contpaq/polizas/exportar` → descarga `{RFC}_polizas_{YYYY-MM}.txt` +
   instrucciones de *Importar otros sistemas → CT_EST_Poliza_NG* (doc 01 §6).

Estado por defecto amable: `clase = 2` (Sin afectar) para que el contador revise en CONTPAQi antes
de afectar; toggle a `1` (Normal) cuando confíe en el mapeo.

## 4. Pruebas (espejo del golden file de la DIOT)

- **Golden file**: fixtures de CFDI (ingreso PUE, ingreso PPD, egreso con retención) → TXT esperado,
  comparado **byte a byte** contra el layout de `CT_EST_Poliza_NG.xls`.
- **Cuadre**: property test — toda `Poliza` generada cumple Σcargos == Σabonos (±tolerancia).
- **Catálogo**: parseo de un CSV y un XLSX de ejemplo → lista de `Cuenta` correcta; validación
  detecta una cuenta faltante.
- **Integración real** (manual, antes de liberar): importar el TXT en una empresa demo de CONTPAQi
  y confirmar pólizas cuadradas + UUID asociado en el ADD (valida el serializado posicional).

## 5. Orden de trabajo sugerido

1. `modelo.py` + `layout_poliza.py` + `exportar_poliza.py` con golden file (el corazón verificable).
2. `catalogo.py` (parseo CSV/XLSX) + `config.py`.
3. `mapeo.py` (empezar con ingreso PUE, ir agregando escenarios) + `validaciones.py` +
   `agregacion.py`.
4. `routers/contpaq.py` + montaje en `server.py`.
5. Feature de UI (asistente de 4 pasos).
6. Prueba de importación real en empresa demo → ajustar layout si hace falta (solo se toca la tupla
   de `layout_poliza.py`, no la lógica).

## 6. Qué NO hace el MVP (explícito)

- No lee ni escribe la BD de CONTPAQi (eso es Fase 2/3).
- No usa el SDK COM (Fase 3).
- No maneja Pagos (P) ni Nómina (N) todavía — se agregan como escenarios nuevos en `mapeo.py` sin
  tocar el resto.
- No da de alta cuentas faltantes automáticamente (solo las reporta; el alta por `CT_EST_Cuenta_NG`
  es una mejora posterior).

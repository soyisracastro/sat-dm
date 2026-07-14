# Brief de diseño de UI — Contabilizador CONTPAQi

Documento para diseñar la interfaz del nuevo feature. Autocontenido: no requiere conocer el backend.
Objetivo: que un diseñador (o una herramienta de diseño asistida) produzca las pantallas del
**Contabilizador CONTPAQi** dentro de TodoConta Desktop.

---

## 1. Contexto del producto

**TodoConta Desktop** es una app de escritorio (Windows/Mac/Linux) para contadores y despachos
contables en México. Su core es administrar los **CFDI** (facturas electrónicas del SAT):
descargarlos, validarlos, leerlos y analizarlos. Ya tiene pantallas de Empresas, Descarga masiva,
Historial de CFDIs y una calculadora de DIOT.

Sistema de diseño (respetar):
- **Color primario**: `#0B5FFF` ("Azul Legal"). Tokens de success/warning/destructive/muted ya
  definidos, con **modo claro y oscuro**.
- **Tipografía**: Inter.
- **Componentes**: shadcn estilo *new-york*. Ya existen y deben reutilizarse: `EmptyState`
  (icono + título + CTA), `StatusBadge` (tonos success/warning/error/info/neutral), `StatusIndicator`
  (icono + texto inline), `ResourceList` (lista/tabla con columnas, fila expandible y acciones),
  `EmpresaCombobox` (selector de empresa con búsqueda).
- **Iconos**: Phosphor **light** (stroke 1.5px) vía `ph:<nombre>-light`. Spinner =
  `ph:circle-notch-light` animado.
- **Ambiente**: limpio, profesional, mucho aire, jerarquía tipográfica clara. Nada de recargado.

---

## 2. Qué es el feature y por qué importa

El contador ya tiene sus **XML del SAT** dentro de TodoConta. Este feature da el salto que ninguna
herramienta web puede dar: **convierte esos CFDIs en un archivo de pólizas listo para importar en
CONTPAQi Contabilidad** (el software contable más usado en México), con cada factura ya asociada a su
**UUID y folio**.

Frase que resume el valor: *"De tus facturas del SAT a tu contabilidad, sin recapturar nada."*

Diferenciadores a comunicar visualmente:
- **No necesita tener CONTPAQi instalado** en la misma máquina (funciona en Mac). Se genera un
  archivo `.txt` que el contador importa después en CONTPAQi.
- Cada póliza queda **trazada a su CFDI** (UUID), para que la contabilidad y las facturas cuadren.

---

## 3. Usuario y objetivo

- **Quién**: contador de despacho que maneja varias empresas (RFC), o el contador interno de una
  empresa. Conoce contabilidad (cargos/abonos, catálogo de cuentas) pero valora que la herramienta
  le ahorre captura.
- **Objetivo**: para una **empresa** y un **periodo** (mes), obtener el archivo de pólizas de sus
  CFDIs, revisarlo, y descargarlo para importarlo en CONTPAQi.
- **Estado emocional**: quiere confianza de que "va a cuadrar" y de que no va a meter basura a su
  contabilidad. La UI debe transmitir **control y revisión antes de nada definitivo**.

---

## 4. Flujo general: asistente de 4 pasos

Un **wizard** (asistente por pasos) dentro de la pantalla del feature, encabezado por el selector de
**empresa** (`EmpresaCombobox`) y **periodo** (mes/año). Los 4 pasos:

```
[ Empresa ▾ ]  [ Periodo: Julio 2026 ▾ ]

 ①  Catálogo de cuentas  →  ②  Mapeo de cuentas  →  ③  Vista previa  →  ④  Descargar
```

Indicador de progreso (stepper) arriba. Cada paso se habilita cuando el anterior está completo.
El usuario puede volver atrás. El estado se recuerda por empresa (si vuelve, sus cuentas y mapeo
siguen ahí).

---

## 5. Pantalla por pantalla

### Paso ① — Catálogo de cuentas

**Objetivo**: cargar el catálogo de cuentas de la empresa (los códigos y nombres de cuenta reales
que existen en CONTPAQi). Es el insumo para poder mapear.

**Contenido**:
- Explicación breve: *"Sube el catálogo de cuentas de esta empresa (exportado de CONTPAQi). Lo
  usaremos para armar las pólizas. En Mac o si CONTPAQi no está en esta computadora, sube el archivo;
  si CONTPAQi está instalado aquí, podemos leerlo directo."*
- **Zona de carga** (dropzone) para arrastrar/seleccionar un archivo **CSV o Excel (.xlsx)**.
- Botón secundario **"Leer de CONTPAQi"** (solo visible/activo si el sistema detecta CONTPAQi local;
  en Mac aparece deshabilitado con tooltip explicativo).

**Estados**:
- **Vacío** (`EmptyState`): icono `ph:table-light`, título "Aún no hay catálogo", CTA "Cargar
  archivo".
- **Cargando**: spinner + "Leyendo catálogo…".
- **Cargado (éxito)**: `StatusIndicator` success → "245 cuentas cargadas" + fecha/origen + botón
  "Reemplazar". Muestra una **muestra** de 5-6 cuentas en una mini-tabla (Código | Nombre).
- **Error**: `StatusBadge` error → "No pudimos leer el archivo. Revisa que tenga columnas Código y
  Nombre." + link a formato esperado.

**Datos de ejemplo para el mockup** (mini-tabla):
| Código | Nombre |
|---|---|
| 1120-001 | Bancos — BBVA |
| 1050-001 | Clientes nacionales |
| 2010-001 | Proveedores nacionales |
| 4010-001 | Ventas |
| 2080-001 | IVA trasladado cobrado |
| 1180-001 | IVA acreditable pagado |

### Paso ② — Mapeo de cuentas

**Objetivo**: decir qué cuenta contable usar para cada tipo de asiento. Se hace una vez por empresa y
se recuerda.

**Contenido**: formulario de ~10-13 campos, agrupados por secciones con subtítulos. Cada campo es un
**selector con autocompletado** que busca dentro del catálogo cargado (muestra "código — nombre").

Grupos y campos:
- **Cuentas de balance**: Clientes, Proveedores, Bancos/Caja.
- **Resultados**: Ventas (ingresos), Gastos por defecto.
- **Impuestos**: IVA trasladado cobrado, IVA trasladado pendiente, IVA acreditable pagado, IVA
  acreditable pendiente, IVA retenido, ISR retenido, IEPS.
- **Ajustes**: Cuenta de redondeo.
- (Avanzado, colapsable) **Reglas por proveedor**: mapear un RFC específico a una cuenta de gasto.

**Estados**:
- Campos sin asignar se marcan con un aviso sutil (borde/ícono warning) pero **no bloquean** hasta
  que ese tipo de asiento realmente se necesite.
- Botón "Guardar mapeo" (o guardado automático con indicador "Guardado ✓").

**Detalle UX**: al enfocar un selector, sugerir cuentas por su naturaleza (p. ej. para "Bancos"
priorizar cuentas cuyo nombre contenga "banco/caja"). Mostrar código y nombre juntos.

### Paso ③ — Vista previa de pólizas

**Objetivo**: mostrar las pólizas que se generarán, para revisar **antes** de descargar. Es el
momento de mayor confianza: aquí el contador ve que todo cuadra.

**Contenido**:
- **Resumen arriba** (tarjetas/stat tiles): "38 CFDIs → 38 pólizas", "36 cuadran ✓", "2 con avisos",
  "Total cargos: \$1,240,500.00 = Total abonos".
- **Panel de cuentas faltantes** (si aplica): banner warning → "2 cuentas usadas en el mapeo no
  existen en el catálogo: `6010-050`, `2130-001`. Corrígelas antes de importar." Con acción "Ir al
  mapeo".
- **Lista de pólizas** (`ResourceList`, filas expandibles): una fila por CFDI/póliza. Columnas:
  - Estado de cuadre (`StatusBadge` success "Cuadra" / warning "Revisar").
  - Tipo (Ingreso/Egreso), badge por color.
  - Fecha.
  - Tercero (emisor o receptor).
  - Serie-Folio.
  - Total.
  - UUID (truncado, con tooltip completo + icono de "asociado" `ph:link-light`).
  - **Al expandir**: tabla de asientos de esa póliza — Cuenta (código + nombre) | Cargo | Abono, con
    la fila de totales que cuadra.

**Datos de ejemplo para el mockup** (una póliza expandida, factura de ingreso PUE):
| Cuenta | Cargo | Abono |
|---|---|---|
| 1120-001 Bancos — BBVA | 1,160.00 | |
| 4010-001 Ventas | | 1,000.00 |
| 2080-001 IVA trasladado cobrado | | 160.00 |
| **Totales** | **1,160.00** | **1,160.00** |

**Estados**:
- **Vacío** (no hay CFDIs en el periodo): `EmptyState` icono `ph:file-x-light`, "No hay CFDIs en este
  periodo", sugerencia de ir a Descarga.
- **Calculando**: skeleton de la lista + "Armando pólizas…".
- **Con avisos**: filas "Revisar" ordenadas arriba.

### Paso ④ — Descargar e importar

**Objetivo**: entregar el archivo y explicar cómo importarlo en CONTPAQi.

**Contenido**:
- Botón primario grande **"Descargar archivo de pólizas"** → genera `EMPRESA_polizas_2026-07.txt`.
- **Instrucciones de importación** en CONTPAQi (pasos numerados, breves): *"En CONTPAQi Contabilidad:
  Importación → Importar otros sistemas → elige la estructura `CT_EST_Poliza_NG` → selecciona el
  archivo descargado."*
- Nota tranquilizadora: *"Las pólizas se importan como 'Sin afectar' para que las revises en CONTPAQi
  antes de aplicarlas."* con toggle opcional "Importar como afectadas (normal)".
- (Opcional) resumen de lo generado y botón "Empezar de nuevo / otro periodo".

**Estados**:
- **Éxito**: confirmación visual (check grande, tono success) + "Archivo listo. 38 pólizas."
- El botón puede usar `window.satDesktop` para elegir carpeta destino (patrón ya existente en la app).

---

## 6. Estados globales y casos borde a diseñar

- **Sin empresa seleccionada**: el wizard está en gris/deshabilitado con un `EmptyState` que invita a
  elegir empresa.
- **Catálogo cargado pero mapeo incompleto** al llegar al paso ③: avisar qué falta, permitir volver.
- **Cuentas faltantes**: el caso más importante de comunicar (bloquea una importación limpia). Debe
  ser muy visible pero no alarmista: es corregible.
- **Modo Mac vs Windows**: en Mac, "Leer de CONTPAQi" aparece deshabilitado con tooltip. En Windows
  con CONTPAQi, aparece habilitado y puede reemplazar la carga de archivo.
- **Periodo sin CFDIs** o **CFDIs sin timbrar/cancelados**: mostrar con claridad.

---

## 7. Tono y microcopy

- Español de México, profesional pero cercano. Tratar de "tú".
- Transmitir **control y reversibilidad**: nada es definitivo hasta que el contador importa en
  CONTPAQi, y aún ahí entra "sin afectar".
- Evitar jerga técnica del backend (nada de "SDK", "TXT posicional", "cp1252"). Sí usar el vocabulario
  del contador: póliza, cargo, abono, catálogo de cuentas, cuadre, UUID/folio.
- Mensajes de error accionables ("Revisa que el archivo tenga columnas Código y Nombre"), no códigos.

---

## 8. Fuera de alcance (para esta primera versión)

- No se conecta en tiempo real con CONTPAQi (no escribe directo; entrega un archivo).
- Solo facturas de **Ingreso y Egreso** (Pagos y Nómina llegan después) — el diseño debe permitir
  crecer a más tipos sin rediseñar.
- No da de alta cuentas faltantes automáticamente (solo las señala).

---

## 9. Entregables de diseño esperados

- Los **4 pasos** del wizard en modo claro (y, si es posible, oscuro).
- Estados clave: vacío, cargando, éxito, con avisos/errores, cuentas faltantes.
- La **fila expandida** de la vista previa con los asientos (el momento "wow" del cuadre).
- El stepper/encabezado con selector de empresa + periodo.
- Coherencia total con el sistema de diseño descrito en §1.

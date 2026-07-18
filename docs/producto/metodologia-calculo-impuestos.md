# Metodología de cálculo de impuestos — TodoConta Desktop

Documento de referencia para replicar en la aplicación **TodoConta Desktop** el flujo de trabajo mensual que se ha aplicado con clientes reales durante las sesiones de análisis con el contador. La aplicación automatiza las tareas mecánicas (identificación, clasificación, cálculo, generación de papel de trabajo, emisión de CFDI global) y deja al contador las decisiones de criterio.

Enfocado en **RESICO Personas Físicas** por ser el régimen que hemos trabajado hasta ahora, pero la arquitectura debe generalizarse a cualquier régimen (Actividad Empresarial, Arrendamiento, Régimen General PM, etc.).

---

## 1. Filosofía rectora — "SAT como default, contador como override"

El principio central de la aplicación:

> **La app aplica siempre el criterio conservador que el SAT aceptaría sin discusión.** El contador puede cambiar clasificaciones puntuales cuando decida asumir un criterio más agresivo. Cada override queda registrado con su motivo.

Esto significa:

- Cuando el SAT no prellena un CFDI en el visor (por Uso S01, forma de pago 01 combustible, etc.), la app lo trata como **NO acreditable / NO deducible por default**.
- El contador puede editar manualmente cualquier CFDI para reclasificarlo como acreditable — aparece un banner de "criterio agresivo" y se pide una razón textual.
- El papel de trabajo generado siempre marca visualmente qué CFDIs se acreditaron por override y por qué, para trazabilidad.

**Ejemplo canónico:** los CFDIs de BBVA con Uso S01 (comisiones bancarias) — para el SAT no acreditan (uso "sin efectos fiscales"). En la práctica, muchos contadores los acreditan porque la clasificación no depende del receptor. La app **NO los acredita por default**; si el contador decide acreditarlos, lo hace explícitamente y queda documentado.

---

## 2. Flujo general por contribuyente y mes

```
[1] Descarga de CFDIs                → sat-dm (ya existe en la app)
[2] Carga de movimientos bancarios   → usuario aporta CSV
[3] Conciliación banco ↔ CFDI        → asistida por app
[4] Clasificación de CFDIs recibidos → default SAT + overrides
[5] Determinación de IVA             → automática
[6] Determinación de ISR (régimen)   → automática
[7] Generación de papel de trabajo   → Excel con formato TodoConta
[8] Emisión de CFDI global si aplica → integración con PAC
[9] Archivo del expediente           → estructura consistente
```

---

## 3. Módulo de INGRESOS

### 3.1 Fuentes de ingreso

| Tipo | Origen | Requiere emisión CFDI |
|---|---|---|
| CFDI de ingreso individual | Ya emitido por el contribuyente | No — ya está |
| CFDI global (público en general) | A emitir por depósitos no facturados | Sí |
| Depósitos sin factura identificados como venta | Estado de cuenta | Sí (vía CFDI global) |
| Depósitos ambiguos | Estado de cuenta | Requiere confirmación con contribuyente |

### 3.2 Conciliación banco ↔ CFDI

Estrategias de empate en orden de preferencia:

1. **Por RFC del receptor** — si el CFDI empatado tiene el mismo RFC que aparece en el detalle SPEI del depósito.
2. **Por monto y fecha próxima** — si el depósito y el CFDI tienen el mismo importe (±$0.05 por redondeo) y están en un rango de ±5 días.
3. **Por remitente conocido** — patrones detectables (PayPal Zettle = OPM150323DI1, Mercado Pago = MER991006JMA, Uber, etc.).
4. **Sin empate** — depósito que no corresponde a ningún CFDI individual; entra al monto que se cubre con CFDI global.

Cada movimiento queda con uno de estos estados:

| Estado | Significado |
|---|---|
| `FACTURADO_INDIVIDUAL` | Empata con un CFDI individual ya emitido |
| `POR_FACTURAR_GLOBAL` | No hay CFDI; entra al CFDI global del mes |
| `EXCLUIDO` | No es ingreso del contribuyente (transferencia propia, familiar, cuenta prestada) |
| `DUDOSO` | Requiere confirmación del contribuyente |

### 3.3 Tipos de depósito y su tratamiento default

| Tipo | Default en la app | Notas |
|---|---|---|
| **Ventas TPV** (afiliación bancaria) | POR_FACTURAR_GLOBAL o FACTURADO_INDIVIDUAL | Detectar patrón de la afiliación |
| **Cobros por plataforma** (Zettle, MP, Stripe) | POR_FACTURAR_GLOBAL | El neto en banco es lo que se declara (comisión ya la retuvo la plataforma) |
| **SPEI de cliente identificado** (mismo RFC en descripción) | Empatar con CFDI si existe |  |
| **SPEI de tercero ambiguo** | DUDOSO | Preguntar contribuyente |
| **Depósito en efectivo** | POR_FACTURAR_GLOBAL | Detectar PractiCaja / cajeros |
| **Traspaso "Transf a NOMBRE_PROPIO"** | EXCLUIDO | Cuando el nombre coincide con el titular |
| **Pagos recurrentes idénticos de familiares** | DUDOSO → EXCLUIDO (con confirmación) | Ver sección 8.4 |

### 3.4 Casos especiales de ingreso

#### 3.4.1 Retención 1.25% de ISR (Art. 113-J LISR)

Cuando una **PM le paga a un RESICO PF** por servicios / actividad empresarial, la PM debe retener 1.25% de ISR. El neto en banco YA está deducido de esa retención.

**Método correcto para el papel de trabajo:**
- Tomar la base gravable **directamente del CFDI** (subtotal), no dividir el neto entre 1.16.
- Alternativamente, aplicar factor **1.1475** (= 1 + 0.16 – 0.0125) al neto para obtener la base.
- La retención de ISR del CFDI se acredita contra el ISR causado del mes.

**Ejemplo:** CFDI de $2,636 subtotal + $421.76 IVA – $31.25 retención = $3,026.51 neto en banco.
- Base declarada: $2,636 (del CFDI, no $3,026.51 / 1.16 = $2,609.06 que sería incorrecto)
- IVA trasladado: $421.76 (del CFDI)
- ISR retenido acreditable: $31.25

#### 3.4.2 Cobros netos de comisión (Zettle, MP, PayPal)

Las plataformas cobran comisión (~3%) y depositan neto. **Se declara el neto** (es lo que efectivamente cobró el contribuyente); la comisión no se ve nunca y no hay CFDI para acreditarla.

Si la plataforma emite CFDI por su comisión (algunas lo hacen), ese IVA sí acredita como gasto operativo.

#### 3.4.3 CFDI global de ingresos

Para contribuyentes que no facturan cada operación (mecánicos, estilistas, nutriólogas con público en general):

- **Monto:** Total de depósitos identificados como venta – CFDIs individuales ya emitidos.
- **RFC receptor:** `XAXX010101000` (público en general).
- **Periodicidad:** Mensual (típica). También válido semanal, quincenal, diario según preferencia del contribuyente.
- **Uso CFDI:** S01 (sin efectos fiscales para el receptor).
- **Cadena origen:** conservar bitácora de qué depósitos alimentaron el CFDI global para conciliación.

---

## 4. Módulo de GASTOS / CFDIs RECIBIDOS

### 4.1 Reglas de clasificación default (criterio SAT)

La app aplica **automáticamente** las siguientes reglas al importar los CFDIs recibidos:

#### 4.1.1 Por Uso CFDI

| Uso | Default | Notas |
|---|---|---|
| **G01** — Adquisición de mercancías | Acreditable | Sujeto a demás filtros |
| **G03** — Gastos en general | Acreditable | Sujeto a demás filtros |
| **G02** — Devoluciones/descuentos | Acreditable como corrección | |
| **I01–I08** — Inversiones | Acreditable | Requiere depreciación |
| **D01–D10** — Deducciones personales | **NO acreditable** para actividad empresarial | Aplica a la declaración anual PF |
| **S01** — Sin efectos fiscales | **NO acreditable** (criterio SAT) | ⚠️ Override común: acreditable si es comisión bancaria |
| **CP01** — Pagos (REP) | No aplica IVA propio | Sirve para desbloquear PPD relacionado |
| **CN01** — Nómina | No aplica al régimen del receptor | Solo asalariado |

#### 4.1.2 Por Forma de Pago (Art. 27 fracc. III LISR)

| Forma | Descripción | Acredita default |
|---|---|---|
| **01** | Efectivo | ⚠️ Ver reglas |
| **02** | Cheque nominativo | Sí |
| **03** | Transferencia electrónica | Sí |
| **04** | Tarjeta crédito | Sí |
| **05** | Monedero electrónico autorizado | Sí |
| **06** | Dinero electrónico | Sí |
| **28** | Tarjeta débito | Sí |
| **99** | Por definir (típico PPD) | Depende del REP |

**Reglas para forma 01 (efectivo):**
- **Combustible vehicular** → NO acredita SIEMPRE (Art. 27 fracc. III párr. 2, sin importar el monto). Aplica a todos los régimenes, incluido RESICO PF.
- **Otros gastos > $2,000** → NO acredita.
- **Otros gastos ≤ $2,000** → SÍ acredita.

#### 4.1.3 Por Método de Pago

| Método | Tratamiento |
|---|---|
| **PUE** — Pago en una exhibición | Acredita en el mes que se emite el CFDI |
| **PPD** — Pago en parcialidades o diferido | NO acredita hasta que se emita el REP correspondiente. IVA acreditable = proporcional al pago cubierto por el REP. |

**Cálculo del PPD con REP parcial:**

```
IVA proporcional = (Monto pagado / Total del CFDI original) × IVA del CFDI original
```

Ejemplo: CFDI PPD por $7,253 con IVA $1,000.41. Se pagan $2,900 y se emite REP:
- IVA acreditable = ($2,900 / $7,253) × $1,000.41 = $400.00
- Resto ($4,353) queda pendiente hasta un futuro REP

### 4.2 Detección automática de gastos personales

Aunque el CFDI venga a nombre del RFC del contribuyente y con Uso G03, la app debe **flaggear como dudoso** patrones típicos de gasto personal:

| Emisor (RFC / patrón) | Categoría sugerida | Default |
|---|---|---|
| Costco / Walmart / Chedraui / Soriana (alimentos) | Despensa | NO acreditable ⚠️ |
| Farmacias | Salud personal | NO acreditable |
| Restaurantes (no operativos) | Alimentación personal | NO acreditable |
| Gasolineras (si actividad no requiere vehículo) | Combustible personal | NO acreditable |

**Override importante:** algunas actividades sí requieren estos gastos (nutrióloga que graba recetas → alimentos son insumo; venta de comida → alimentos son materia prima). El contador puede reclasificar.

### 4.3 Categorías de gasto para el papel de trabajo

Para facilitar la lectura, la app agrupa los CFDIs por categoría. Categorías sugeridas (ampliables):

- Materia prima / mercancía
- Renta de local / oficina
- Servicios profesionales (contador, abogado, consultor)
- Adecuación / mantenimiento local
- Combustible
- Peajes / traslados
- Servicios básicos (agua, luz, internet, teléfono)
- Suscripciones digitales (Canva, Adobe, Zoom, etc.)
- Comisiones bancarias
- Herramientas / equipo
- Capacitación / cursos / congresos
- Publicidad / marketing
- Alimentos (evaluar caso por caso)
- Otros

---

## 5. Cálculo de IVA

### 5.1 IVA trasladado

```
Base gravable = Ingresos totales cobrados / 1.16
IVA trasladado = Base × 0.16
```

Ajuste por retención 1.25% (RESICO PF cobrando a PM):

```
Base porción con retención = Ingresos con retención / 1.1475
Base porción sin retención = Ingresos sin retención / 1.16
Base total = suma
```

### 5.2 IVA acreditable

```
IVA acreditable = SUMA de IVA de CFDIs recibidos que cumplan:
  - Uso acreditable (G01, G03) OR override del contador
  - Forma de pago acreditable (por Art. 27 fracc. III)
  - Método PUE (o PPD con REP proporcional)
  - Categoría estrictamente indispensable para la actividad
```

### 5.3 IVA a cargo o a favor

```
IVA resultado = IVA trasladado – IVA acreditable

Si > 0 → IVA A CARGO (se paga)
Si < 0 → IVA A FAVOR (se acredita en meses futuros o se pide devolución vía FED)
```

---

## 6. Cálculo de ISR — según régimen

### 6.1 RESICO Personas Físicas (Art. 113-E LISR)

Tarifa mensual:

| Límite inferior | Límite superior | Tasa |
|---:|---:|:---:|
| $0.01 | $25,000.00 | 1.00% |
| $25,000.01 | $50,000.00 | 1.10% |
| $50,000.01 | $83,333.33 | 1.50% |
| $83,333.34 | $208,333.33 | 2.00% |
| $208,333.34 | $3,500,000.00 | 2.50% |

Cálculo:

```
ISR causado = Base gravable × Tasa aplicable
ISR retenido = Suma de retenciones ISR de CFDIs emitidos a PM (1.25%)
ISR a pagar = MAX(0, ISR causado – ISR retenido)
```

### 6.2 Otros régimenes (roadmap)

- **Actividad Empresarial y Profesional** (Personas Físicas) — Art. 109 LISR. Requiere: ingresos acumulables, deducciones autorizadas, base gravable, tarifa progresiva mensual.
- **Régimen de Arrendamiento** (Personas Físicas) — Art. 114 LISR. Opción de deducción ciega 35%.
- **Régimen General** (Personas Morales) — Art. 9 LISR. ISR anual 30% con pagos provisionales.
- **RIF** (extinto, migración pendiente) — no crear módulo nuevo.

Cada régimen tiene su propio módulo de cálculo, pero la conciliación de banco/CFDI y clasificación de gastos son compartidas.

---

## 7. Casos especiales y patrones de decisión

Estos patrones se han identificado en clientes reales y deben tener soporte en la app.

### 7.1 Contribuyente con muchas ventas en efectivo (metodología N× TPV)

**Aplica cuando:** el contribuyente vende al público en general (comida, papelería, tienda), cobra parte con tarjeta (TPV) y parte en efectivo (no depositado).

**Metodología:**
- Ventas TPV del mes × factor N → ingresos declarados totales.
- Factor típico: 3× (histórico), pero puede ajustarse mes a mes según:
  - Si la suma directa de depósitos (TPV + efectivo + apps) supera 3× TPV → usar suma directa.
  - Si hay mes con muchas compras extraordinarias que dejan IVA a favor grande → subir factor (4×, 5×) para no llamar la atención SAT.

**Override en la app:** el contador define el factor (default 3, editable) por contribuyente y por mes.

### 7.2 Contribuyente que rara vez factura (mecánico, estilista)

**Aplica cuando:** el contribuyente solo emite CFDI cuando el cliente lo pide (típico en oficios).

**Metodología:**
- Identificar depósitos en banco que sean ingresos por servicio (confirmar con contribuyente los ambiguos).
- Diferencia entre total identificado y CFDIs individuales emitidos → CFDI global mensual.

### 7.3 Contribuyente en fase preoperativa

**Aplica cuando:** el contribuyente ya está inscrito en el SAT y tiene gastos (renta local, adecuación) pero aún no genera ingresos.

**Decisión estratégica:**
- **Opción A — Preoperativo puro:** declarar $0 ingresos cada mes, todo el IVA queda a favor. Riesgo: saldos a favor grandes durante meses consecutivos llaman la atención del SAT.
- **Opción B — Ingresos estimados (empate al X%):** reportar ingreso estimado (X% del "empate técnico" con el IVA acreditable). Requiere emitir CFDI global sustentado en operaciones informales reales del contribuyente.

**En la app:** ofrecer ambas opciones con cálculo comparativo del costo (multas + ISR vs. beneficio del saldo a favor).

### 7.4 Cuentas bancarias compartidas

**Aplica cuando:** el contribuyente comparte la cuenta con cónyuge, familiar, o presta la cuenta a terceros.

**Metodología:**
- Marcar depósitos DUDOSOS que no encajen con el patrón del negocio.
- Solicitar confirmación al contribuyente.
- Excluir los que sean de terceros y **documentar la razón** en el papel de trabajo (para defensa ante auditoría).
- **Advertir por escrito al contribuyente** que la práctica de compartir cuenta levanta sospechas SAT.

### 7.5 Colaboraciones con marcas / influencer

**Aplica cuando:** el contribuyente genera contenido en redes sociales y recibe pagos por promoción de marcas.

**Consideraciones:**
- Alta de actividad económica secundaria en el CSF (SCIAN 541430 publicidad o 711510 artistas independientes).
- Los gastos de producción de contenido (equipo audiovisual, software, viáticos, alimentos si son para recetas grabadas) son acreditables.
- Los pagos suelen tardar 3-4 meses (declarar cuando se cobra, no cuando se factura).
- Ingresos vía agencia intermediaria (facturar a la agencia).

### 7.6 Gasolina y combustibles

**Regla dura:** Art. 27 fracc. III párr. 2 LISR — SIEMPRE debe pagarse con medio bancarizado (cheque, tarjeta, transferencia, monedero electrónico), sin importar el monto. Aplica a **todos los régimenes** incluido RESICO PF (no hay excepción por tratamiento simplificado).

**En la app:**
- Marcar todos los CFDIs de combustible con Forma 01 (efectivo) como NO acreditables por default.
- Generar alerta al contribuyente sugiriendo migrar a tarjeta o monedero de combustible.
- Cuantificar el IVA perdido anualizado como argumento de negocio.

---

## 8. Estructura del expediente (por contribuyente)

```
<Apellido paterno Apellido materno Nombre(s)>/
├── papeles de trabajo/         # Salidas del análisis:
│                                 papel-trabajo-<mes>-<año>.xlsx
│                                 <cliente>-revision-<mes>-<año>.md
│                                 <cliente>-plan-<tema>.md
├── reportes/                    # Insumos del análisis:
│                                 CFDIs emitidos/recibidos (CSV)
│                                 Estados de cuenta bancarios
│                                 Constancia de Situación Fiscal
│                                 XMLs originales (si aplica)
└── <subcarpetas administrativas>  # Se conservan en la raíz:
                                    Declaraciones/
                                    Devoluciones/
                                    Firma electrónica/
                                    Trámites/
```

**Reglas de nomenclatura:**
- Carpeta principal: **con acentos y respetando ortografía completa**.
- No usar RFC como nombre de carpeta principal (aunque sí puede aparecer en archivos internos).
- Papeles de trabajo: `papel-trabajo-<mes>-<año>.xlsx` o `papel-trabajo-consolidado-<periodo>.xlsx`.

---

## 9. Papel de trabajo Excel — estructura

Cada declaración mensual genera un papel de trabajo con las siguientes hojas mínimas:

### Hoja 1: Resumen
- Datos del contribuyente (nombre, RFC, régimen, actividad, periodo)
- Determinación consolidada (ingresos, IVA trasladado, IVA acreditable, IVA a cargo, ISR)
- Total a pagar
- Observaciones estratégicas del mes (con override del contador si aplica)

### Hoja 2: Ingresos
- CFDIs individuales emitidos (conciliación con banco)
- Depósitos identificados por tipo (TPV, Zettle, SPEI, efectivo)
- Depósitos excluidos con razón documentada
- Cálculo del CFDI global a emitir (subtotal, IVA, total)

### Hoja 3: Gastos
- Todos los CFDIs recibidos con clasificación por categoría
- Marcado visual por acreditable / no acreditable / pendiente
- Filas coloreadas: verde (acreditables destacados), gris (no acreditables), amarillo (dudosos / con override)
- Subtotales por categoría
- Total IVA acreditable del mes

### Hoja 4: ISR
- Cálculo paso a paso (ingresos → base → tasa → ISR causado → retenido → a pagar)
- Tabla de tarifas del régimen aplicable con el rango correspondiente resaltado

### Hoja 5: IVA
- Cálculo paso a paso (base → trasladado → acreditable → resultado)
- Análisis de sensibilidad si aplica (escenarios)

### Reglas técnicas del generador
- **Nunca usar `SUM(F{row-N}:F{row-1})` con aritmética retrospectiva.** Siempre registrar `start_row` y `end_row` al iterar categorías.
- **No mezclar régimenes** en un mismo papel de trabajo (RESICO PF y Sueldos y Salarios van separados).
- **Segregar por retención** cuando aplique el Art. 113-J (ingresos con CFDI de PM con retención se separan de ingresos sin retención).

---

## 10. Sugerencias para el desarrollo de la app

### 10.1 Arquitectura por módulos

```
todoconta-desktop/
├── modules/
│   ├── ingresos/          # Conciliación banco ↔ CFDI, CFDI global
│   ├── gastos/            # Clasificación CFDIs recibidos, reglas SAT
│   ├── impuestos/
│   │   ├── iva.py         # Cálculo IVA (universal)
│   │   ├── isr_resico.py  # Cálculo ISR RESICO PF
│   │   ├── isr_ae.py      # Actividad Empresarial (roadmap)
│   │   ├── isr_arrend.py  # Arrendamiento (roadmap)
│   │   └── isr_pm.py      # PM Régimen General (roadmap)
│   ├── conciliacion/      # Motor de empate banco ↔ CFDI
│   ├── papel_trabajo/     # Generador Excel
│   └── cfdi_global/       # Integración PAC para emitir global
```

### 10.2 Motor de reglas (defaults SAT + overrides)

- Cada CFDI recibido pasa por una **cadena de reglas** que determinan su default de acreditación.
- Cada regla puede ser **sobrescrita manualmente** por el contador, con nota de motivo.
- Auditoría: la app guarda historial de overrides por CFDI (quién, cuándo, motivo).

### 10.3 Bases de datos por contribuyente

- Un archivo SQLite por contribuyente (o similar) que guarda:
  - CFDIs emitidos/recibidos con clasificación aplicada
  - Movimientos bancarios importados
  - Empates realizados
  - Overrides con motivo
  - Papeles de trabajo generados (histórico)

### 10.4 Detección automática de patrones

Aprendizaje del histórico del contribuyente:
- RFCs de proveedores recurrentes → sugerir categoría.
- Patrones de descripción de SPEI → detectar remitente típico.
- Depósitos redondos (`.00`) repetidos con mismo remitente → posible pago recurrente / renta.
- Nombres en descripción coincidentes con familiares registrados → flaggear.

### 10.5 Alertas y recomendaciones

La app debe generar alertas al contribuyente / contador cuando detecte:
- Gasolinas pagadas en efectivo (IVA perdido)
- Saldos a favor grandes por múltiples meses
- CFDIs PPD sin REP correspondiente
- Depósitos con RFC de familiar (posible cuenta compartida)
- CFDIs de despensa siendo acreditados sin override (posible error)

---

## 11. Casos ilustrativos (cartera trabajada)

Cada caso muestra un patrón distinto que debe soportar la app.

| Contribuyente | Régimen | Actividad | Patrón principal |
|---|---|---|---|
| Teresa Cedeño Almazán | RESICO PF | Venta de hamburguesas | Metodología N× TPV, cónyuge deposita, S01 acreditable (override) |
| Omar Murguía Villafuerte | RESICO PF | Instalaciones eléctricas | Cliente heredado, cuenta compartida con esposa, migración gasolina a tarjeta, PPD con REP proporcional |
| Carlo Montufar González | RESICO PF | Estéticas + bufete | Fase preoperativa, decisión entre reportar ceros vs. empate al X% |
| Abner Sánchez Hernández | RESICO PF | Mecánica automotriz | Casi no factura, uso de cuenta prestada a terceros, retención 113-J |
| Yaskin Castillo Martínez | RESICO PF | Nutrióloga + influencer | Colaboraciones con marcas, alimentos como insumo de producción, alta de actividad secundaria pendiente |

Estos casos deben quedar como fixtures / datos de prueba en la app para verificar que las reglas nuevas no rompan los resultados históricos.

---

## 12. Historial de criterios técnicos ya documentados

Estos criterios están registrados en la memoria del contador (Israel Castro) y deben trasladarse a la lógica de la app:

- **Patrón SUM en papeles de trabajo Excel:** nunca usar aritmética retrospectiva `SUM(F{row-N}:F{row-1})`; registrar `cat_start_row`/`cat_end_row` al iterar.
- **Régimenes separados:** no mezclar CFDIs de otros régimenes (nómina asalariado no va en papel RESICO PF).
- **Cuenta bancaria prestada:** al analizar estados de cuenta, no asumir que todo depósito es ingreso; confirmar con el titular. Documentar advertencia por escrito.
- **Retención 1.25% Art. 113-J:** factor 1.1475 (no 1.16) para ingresos con CFDI de PM con retención. Tomar base del CFDI directamente.

---

## 13. Próximos pasos (roadmap sugerido)

1. **Fase 1 — MVP RESICO PF:** implementar el flujo completo para RESICO PF con los 5 casos ilustrativos como pruebas.
2. **Fase 2 — Otros régimenes PF:** Actividad Empresarial y Profesional, Arrendamiento.
3. **Fase 3 — Régimen General PM:** cálculo ISR anual con pagos provisionales, coeficiente de utilidad.
4. **Fase 4 — Declaración anual PF:** consolidación de ingresos por régimen, deducciones personales (D01–D10).
5. **Fase 5 — Integración con PAC:** emisión automática de CFDI global.
6. **Fase 6 — Aprendizaje del histórico:** sugerencias automáticas basadas en meses anteriores del mismo contribuyente.

---

*Documento inicial preparado para la aplicación TodoConta Desktop*
*Basado en sesiones de análisis con contribuyentes reales durante junio-julio 2026*

# Presentación de venta — TodoConta Desktop (20-25 min)

> Guion para la primera oportunidad de venta. Objetivo: **convertir a suscripción ($299/mes o $2,990/año)** y agradecer a los fundadores que ya financiaron lo que viene.
> Estructura: problema → lo que ya hace hoy → lo que viene → el salto que solo una app instalada permite → oferta.
>
> Regla de oro de esta presentación: **solo vendemos lo que existe o lo que es realista**. Lo "que viene" se marca como roadmap; los adelantos de integración se presentan como *capacidades que la arquitectura ya habilita*, nunca como features terminadas.

---

# ⭐ USA ESTO — Versión corta (≈7 min hablado + demo en vivo)

**Formato:** ~3-4 min de apertura → **demo en vivo (la app habla)** → ~3-4 min de cierre.
Regla: los puntos fuertes **no se cuentan, se muestran**. Lo hablado es solo para lo que la demo no puede mostrar (lo que viene, integración contable, precio).

### Antes de entrar (checklist de 1 min)
- [ ] Empresa de prueba cargada con **CIEC y e.firma** (para mostrar ambos canales).
- [ ] Una carpeta con **XMLs de Nómina o Pagos** lista para arrastrar.
- [ ] Tema (claro/oscuro) y ventana a buen tamaño; cierra notificaciones de otras apps.
- [ ] App ya abierta en `/empresas` con varios RFCs visibles.

---

## ① Apertura — 3-4 min (hablado)

**Problema (90 seg):** El día del contador. Atiende 30, 50, 200 RFCs. Cada cliente que pide algo = entrar al portal, pelear con el captcha, esperar. Descargar CFDIs uno por uno, pedir constancia y opinión 32-D a mano, cuadrar pagos en Excel, revisar nómina antes de declarar, y vigilar que ningún proveedor esté en lista 69-B.
→ *"Hoy lo resuelves con XMLSAT a $2,200 al año, un pedazo con CONTPAQi, y aun así sigues tecleando captchas. Nadie te lo da completo en una sola ventana."*

**Qué es, en una frase (60 seg):** *"TodoConta Desktop es una app que instalas en tu equipo y automatiza todo el trabajo recurrente con el SAT — descargar, validar, procesar y vigilar tu cartera — sin que la e.firma de nadie salga jamás de tu computadora."*
→ 3 anclas rápidas: **nativa, no web** · **los dos canales (e.firma + CIEC)** · **privacidad: todo vive en tu equipo**.

**Transición (15 seg):** *"En vez de contártelo, déjame enseñártelo con un cliente real."* → **a la demo.**

---

## ② DEMO EN VIVO — el grueso del tiempo (run-sheet)

> Sigue este orden: cuenta una historia (tengo mis clientes → descargo sin pelear → saco documentos al instante → proceso → detecto riesgos → todo queda auditado). Una frase por paso, deja que la app impresione.

| # | Qué haces en pantalla | Qué dices (una línea) |
|---|---|---|
| 1 | En `/empresas`, cambias entre dos clientes con un clic; señala el **semáforo 🟢🟡🔴** de e.firma | *"Mis 50 clientes, un clic para cambiar. El semáforo me avisa qué e.firma está por vencer."* |
| 2 | Disparas una **descarga CIEC** y resuelves el **captcha en la mini-ventana in-app** | *"El SAT pide captcha; lo resuelvo aquí dentro. Nunca abro un navegador externo."* ← **momento wow, hazlo temprano** |
| 3 | Desde la empresa, **Constancia** y **Opinión 32-D** por e.firma (sin captcha) | *"Constancia y opinión 32-D en un clic, sin entrar al portal."* |
| 4 | **Arrastras** la carpeta de XMLs al procesador → muestras el **Excel** (Nómina o Pagos) | *"Arrastro los XMLs y obtengo el Excel que normalmente armo a mano: ISR teórico, IMSS, deducibilidad / incidencias de pago."* |
| 5 | **Listas negras**: un botón, vista **por proveedor** ordenada por riesgo | *"Un clic y sé qué facturas están en riesgo de no ser deducibles por estar en 69-B."* |
| 6 | **Validar contra SAT** (vigente/cancelado) + **Historial** con apertura directa | *"Valido estatus en masa y todo queda registrado con fecha, método y un botón para abrir el archivo."* |

*(Si falta tiempo, los imprescindibles son 1, 2 y 4. El captcha in-app y el Excel del procesador son los que más venden.)*

---

## ③ Cierre — 3-4 min (hablado): lo que la demo NO puede mostrar

**Lo que viene en semanas (90 seg):** release **cada viernes**. Pronto: las **17 listas negras** completas, parser de la **Constancia** (régimen + actividades a la ficha) y de la **Opinión 32-D** (positiva/negativa), validación masiva de RFC. Después: **declaraciones**, **DIOT**, **macOS/Linux**.
→ *"No compras un producto terminado; compras uno que mejora cada semana, y lo recibes sin pagar de nuevo."*

**El salto que solo una app instalada permite (90 seg):** *"Hasta ahora era una web. Ahora vivo en la misma computadora donde está tu contabilidad. Un navegador no puede tocar tu CONTPAQi o tu Aspel; una app instalada sí."*
→ Honesto: **leer ya es realista** (cruzar tus CFDIs contra tus pólizas: qué facturó el SAT que aún no contabilizas); **escribir pólizas viene después**, vía el archivo que tu software importa. *"¿Tú con qué trabajas hoy, CONTPAQi o Aspel?"*

**Agradecimiento + precio + CTA (60 seg):** Primero, gracias: *"La ventana de fundadores ya cerró, y quienes se sumaron financiaron todo lo que están por ver estos días."* Luego el precio actual: **$299 MXN/mes o $2,990 MXN/año.** *"Menos que un año de XMLSAT, con releases cada semana y todo lo que viene incluido. Empieza hoy y esta misma semana te ahorra horas."*

---

# 📚 Material de respaldo — versión larga y detalle por bloque

> Lo de abajo es para **prepararte** y para **profundizar si te preguntan**. En la sala, guíate por la versión corta de arriba.

## Agenda con tiempos (≈23 min + 2 buffer)

| # | Bloque | Min | Qué busca |
|---|---|---|---|
| 1 | El dolor del contador | 3 | Que el cliente se vea reflejado |
| 2 | Qué es TodoConta Desktop | 2 | Encuadre en una frase |
| 3 | **Puntos fuertes HOY** (demo en vivo) | 9 | Prueba de que ya funciona |
| 4 | **Lo que viene en semanas** | 4 | Momentum, no es un producto muerto |
| 5 | **El salto: app instalada ≠ web** (CONTPAQi) | 4 | El "wow" diferenciador |
| 6 | Agradecimiento + precio + cierre | 2 | La acción |

---

## Bloque 1 — El dolor (3 min)

**Mensaje:** "El SAT te roba horas cada semana, y ninguna herramienta te lo resuelve completo."

Cuéntalo como un día del contador, no como lista de features:

- Atiende 30, 50, 200 RFCs. Cada cliente que pide algo = entrar al portal, pelear con el captcha, esperar.
- Descargar CFDIs uno por uno; pedir la constancia o la opinión 32-D cada vez que un cliente va a facturarle a un proveedor grande.
- Cuadrar a mano PPD vs complementos de pago para cazar facturas que el cliente nunca cobró.
- Procesar nómina para validar ISR, IMSS y deducibilidad **antes** de declarar.
- Revisar que sus proveedores no estén en lista negra 69-B (EFOS) — porque si lo están, esas facturas no son deducibles y el cliente queda expuesto.

**Frase ancla:** *"Hoy resuelves esto con XMLSAT ($2,200/año), un pedazo con CONTPAQi o Aspel, y aun así sigues entrando al portal a teclear captchas. Nadie te lo da completo y en una sola ventana."*

---

## Bloque 2 — Qué es (2 min)

**Una frase:** *"TodoConta Desktop es una app que instalas en tu equipo y automatiza todo el trabajo recurrente con el SAT — descargar, validar, procesar y vigilar la cartera de tus clientes — sin que la e.firma de nadie salga jamás de tu computadora."*

Tres puntos de encuadre (no más):

1. **Nativa, no web** — se instala en Windows, abre en un clic, funciona aunque el SAT esté lento.
2. **Los dos canales del SAT** — e.firma (rápido, sin captcha) y CIEC (RFC + contraseña), más el Web Service oficial para volumen masivo.
3. **Privacidad por diseño** — la e.firma, las contraseñas y los datos del cliente viven en el equipo del contador. El agente solo escucha en `127.0.0.1`; nada queda expuesto a internet.

---

## Bloque 3 — Puntos fuertes HOY (9 min) · ESTE ES EL CORAZÓN

> Demuéstralos en vivo si puedes. Cada uno tiene una "frase de cierre" para soltar después de mostrarlo.

### 3.1 Multi-empresa instantáneo
- Da de alta 200 clientes una vez; cambias entre ellos con un clic en la barra lateral.
- **Demo:** clic entre dos empresas, mostrar cómo cambia la sesión.
- *"Lo que en CONTPAQi te toma abrir otra base de datos, aquí es un clic."*

### 3.2 Captcha dentro de la app (diferenciador único)
- El navegador corre **headless** (invisible). Cuando el SAT pide captcha, aparece una mini-ventana **dentro** de TodoConta; tecleas 4 caracteres y la descarga sigue.
- **Demo:** disparar una descarga CIEC y resolver el captcha in-app.
- *"XMLSAT te abre un Internet Explorer embebido. Aquí nunca sales de la app."*

### 3.3 Doble canal en cada trámite
- CFDIs, Constancia de Situación Fiscal y Opinión 32-D: por **e.firma** (sin captcha, desatendido) o por **CIEC**.
- Web Service oficial para volumen: **una solicitud cubre hasta 200,000 CFDIs**.
- *"Volumen masivo por FIEL, un mes suelto en ~2 min por CIEC, y si el Web Service del SAT se cae, la app te sugiere CIEC en el mismo flujo."*

### 3.4 Semáforo de e.firma + recordatorio
- Cada empresa muestra 🟢 / 🟡 / 🔴 según los días que le quedan a la e.firma; recordatorio diario si alguna está por vencer.
- *"Nunca más te enteras de que venció una e.firma cuando ya la necesitabas."*

### 3.5 Procesadores listos (el músculo que sorprende)
Carga los XMLs y obtén un **Excel listo** — esto suele ser lo que más impresiona:

- **CFDI:** emisor/receptor, conceptos, IVA/IEPS/ISR, forma y método de pago, uso CFDI.
- **Pagos (complemento 2.0):** concilia PPD vs complementos y detecta **pagos parciales, huérfanos, extemporáneos (con días de retraso) e incidencias PUE**.
- **Nómina (1.2):** calcula **ISR teórico** (tarifa SAT del año + Subsidio al Empleo) vs retenido, **IMSS** (SBC/SDI, aportación patronal/obrera), **deductibilidad por empleado-mes** y comparativo periodo vs periodo. Detecta salarios bajo el mínimo IMSS y periodos parciales.
- **Demo:** arrastra una carpeta de XMLs → mostrar el Excel generado.
- *"Esto es lo que normalmente armas a mano en hojas de cálculo. Aquí es arrastrar y soltar."*

### 3.6 Listas negras 69 y 69-B integradas
- Un botón cruza **todos** los emisores y receptores cargados contra las listas; vista agregada **por proveedor** ordenada por riesgo monetario ("este proveedor te facturó $X y está en 69-B").
- Datos actualizados desde la nube (cron mensual).
- *"En un clic sabes qué facturas de tus clientes están en riesgo de no ser deducibles."*

### 3.7 Validación masiva de estatus
- Marca masivamente qué CFDIs siguen **vigentes** y cuáles fueron **cancelados** — sin e.firma (endpoint público del SAT).
- Un solo botón dispara **en paralelo** estatus (vigente/cancelado) **y** cruce con listas negras.

### 3.8 Lo invisible que da confianza
- **Backup local automático** por RFC/año/mes; nada se pierde.
- **Historial auditado:** cada descarga con fecha, hora, método y botón para abrir el archivo.
- **Organizador:** renombrar, deduplicar y mover XMLs en árboles de carpetas.

**Cierre del bloque:** *"Todo esto ya está, probado contra el SAT real, en la versión que se instala hoy."*

---

## Bloque 4 — Lo que viene en semanas (4 min)

**Mensaje:** "No compras un producto terminado; compras uno que mejora cada viernes." (Hacemos release semanal.)

Próximo trimestre (v1.1 — cerrar paridad con XMLSAT):

- **Las 17 listas negras completas** (cancelados, condonados, no localizados, sentencias firmes, eliminados…), no solo 69/69-B.
- **Parser de la Constancia (CSF):** extrae régimen fiscal y actividades económicas automáticamente a la ficha de la empresa.
- **Parser de la Opinión 32-D:** clasifica positiva / negativa / sin obligaciones y lo pinta en el semáforo.
- **Validación masiva de RFC** (estructura + existencia) por plantilla Excel.
- **Backup local de la e.firma** por RFC (la contraseña sigue solo en el llavero del SO).
- **Atajos de teclado** + tests de UI para estabilidad.

Más adelante (v1.2, fin de año):

- **Declaraciones anuales y provisionales** (descarga de acuses) — arrancando por personas físicas.
- **DIOT y DEM.**
- **Enviar documentos por correo** desde el historial.
- **Build de macOS y Linux** (la base ya está, falta activar el CI).

**Frase ancla:** *"El mapa para igualar a XMLSAT punto por punto ya está trazado, y cada semana avanzamos un tramo a la vista del usuario."*

---

## Bloque 5 — El salto que ninguna web puede dar (4 min) · EL "WOW"

**Mensaje central:** *"Hasta ahora teníamos una web. Ahora tenemos una app **instalada en la misma computadora donde vive tu contabilidad**. Eso abre una puerta que el navegador tiene cerrada para siempre."*

### Por qué esto importa (el argumento técnico, en simple)
Un navegador está aislado por seguridad: **no puede tocar** la base de datos de CONTPAQi ni leer archivos de tu disco. Por eso ninguna herramienta web podrá nunca integrarse con tu software contable.

Nuestra app **ya** corre un motor local en tu equipo (el mismo que descarga del SAT). Ese motor sí puede — con tu permiso — **hablar con el software contable que ya tienes instalado**.

### El adelanto honesto: leer es fácil, escribir viene después

> Presenta esto como *"hacia dónde nos lleva esta arquitectura"*, con una demo conceptual, no como feature lista.

**Fase 1 — LEER (lo fácil, lo que enseñamos primero):**
CONTPAQi Contabilidad guarda todo en SQL Server, en la misma máquina. Nuestro agente local puede conectarse **en modo lectura** y cruzar dos mundos que hoy viven separados:

- **Conciliación contable ↔ CFDI:** ya tenemos cada CFDI parseado en una base local. Leemos las pólizas de CONTPAQi y te decimos **qué CFDIs descargaste del SAT que todavía NO están contabilizados** y qué pólizas no tienen CFDI que las respalde.
- **Catálogo de cuentas / saldos** a la mano para reportes, sin re-capturar nada.

*"Ya tenemos tus facturas del SAT y tu contabilidad en la misma máquina. Por primera vez se pueden cruzar solas."*

**Fase 2 — ESCRIBIR (lo poderoso, lo que viene):**
- **Pre-armar pólizas** desde los CFDIs y entregártelas en el formato que CONTPAQi importa (el camino más seguro y el primero que haríamos).
- Integración profunda vía el **SDK de CONTPAQi** para registrar pólizas directamente (es más delicado; va después y siempre con el contador en control).

**Y al revés también:** como ya leemos el XML, podemos **cargar información desde nuestra app hacia tu flujo** — exportar conceptos, impuestos y desgloses en los formatos que tus herramientas consumen.

> **Cómo decirlo sin sobrevender:** *"Leer de tu contabilidad ya es viable hoy con la arquitectura que tenemos; escribir pólizas es el siguiente paso y lo haremos con cuidado, empezando por exportar el archivo que CONTPAQi importa antes de tocar nada por dentro. Lo importante: esto **solo** es posible porque ahora vivimos en tu equipo, no en una página web."*

### No solo CONTPAQi — el principio aplica a tu software, sea cual sea

Hay dos mundos, y nuestra app instalada juega en ambos:

**A) Software contable local con base de datos en el equipo** (aquí el "solo instalada puede"):

| Software | Dónde guarda los datos | Leer | Escribir |
|---|---|---|---|
| **CONTPAQi Contabilidad** | SQL Server local (`localhost\COMPAC`) | ✅ realista, cercano | Archivo que importa → SDK CONTPAQi |
| **Aspel COI / SAE** | Firebird local (versiones recientes) | ✅ realista, cercano | "Interface / archivo de pólizas" → SDK Aspel |
| **Microsip** | SQL Server local | ✅ realista, cercano | Importación de pólizas |

Regla firme en los tres: **escribir siempre vía el archivo de importación que el propio software acepta**, nunca tocando su base de datos por dentro (eso la corrompería y anularía su soporte). El SDK es el paso profundo posterior, con el contador en control.

**B) ERPs con API abierta** (Odoo y similares):

- **Odoo** tiene API documentada (XML-RPC/JSON-RPC): leer y **registrar asientos** (`account.move`) es legítimo y soportado.
- **Honestidad clave para el pitch:** Odoo se integra por API, así que **esto NO prueba "instalada > web"** — una web también podría. Y Odoo ya procesa CFDIs con su localización mexicana. Con Odoo el valor es *automatizar la conciliación y ahorrar captura*, no exclusividad.

**Cómo cerrarlo (y descubrir qué usa el cliente):**

> *"Porque vivimos en tu equipo, nos conectamos con el software contable que ya usas — CONTPAQi, Aspel, Microsip — y con ERPs de API abierta como Odoo. ¿Tú con qué trabajas hoy?"*

Esa pregunta te dice qué integración priorizar y le demuestra al prospecto que escuchas. **No prometas integraciones con fecha** — promete el principio y prioriza por demanda de los usuarios.

---

## Bloque 6 — Agradecimiento + precio + cierre (2 min)

**Agradecimiento (primero, sin vender):** *"La ventana de fundadores ya cerró. Gracias a quienes se sumaron — son los que financiaron todo lo que están por ver salir estos días."* Genera credibilidad: el producto avanza porque ya hay gente respaldándolo.

**El precio actual:**

- **$299 MXN/mes** o **$2,990 MXN/año.**
- Comparativo: XMLSAT $2,200/**año** (solo descarga + organización), CONTPAQi/Aspel $4,000+/**año**. TodoConta cuesta parecido a XMLSAT pero cubre el flujo completo y mejora cada semana.

**Lo único de pago por consumo:** las funciones con IA (análisis de patrones, anomalías) — para todos los planes. Dilo de frente; genera confianza.

**Llamado a la acción:** *"Lo que hoy se instala ya te ahorra horas esta misma semana, y cada release que viene lo recibes incluido en tu suscripción."*

---

## Tabla comparativa de bolsillo (por si la piden)

| | XMLSAT Premium | CONTPAQi / Aspel | **TodoConta Desktop** |
|---|---|---|---|
| Precio | $2,200/año | $4,000+/año | **$299/mes · $2,990/año** |
| CIEC **y** e.firma en todo trámite | Solo CIEC | Solo FIEL | **Ambos** |
| Captcha sin salir de la app | No | No | **Sí, modal in-app** |
| Multi-empresa instantáneo | Sí | Sí (lento) | **Sí** |
| Procesador Nómina (ISR teórico + IMSS) | No | Parcial | **Sí, Excel listo** |
| Procesador Pagos (incidencias PUE) | No | No | **Sí** |
| Semáforo automático de e.firma | No | No | **Sí + recordatorio** |
| e.firma/datos nunca salen del equipo | Sí | Sí | **Sí** |
| Actualización automática | No | Manual | **Sí (auto-update)** |
| Integración con tu contabilidad local | No | (es su propio software) | **En camino — solo posible por ser app instalada** |

---

## Guardarraíles para no sobrevender (léelos antes de presentar)

- ✅ **Sí está hoy:** descarga (WS/CIEC/e.firma), constancia, opinión 32-D, validación de estatus, listas 69/69-B, procesadores CFDI/Pagos/Nómina con Excel, organizador, historial, multi-empresa, semáforo, auto-update.
- 🔜 **Es roadmap (dilo como tal):** 17 listas, parsers PDF de CSF/32-D, declaraciones, DIOT/DEM, correo, macOS/Linux.
- 🧪 **Es adelanto / capacidad de arquitectura (no feature lista):** integración con CONTPAQi, Aspel, Microsip (apps locales — solo posible por estar instalados) y con ERPs de API abierta como Odoo. **Leer = realista y cercano; escribir pólizas = más adelante, vía el archivo de importación del propio software.** Nunca digas "ya se conecta" — di "la arquitectura instalada lo habilita, empezando por lectura".
- ⚠️ **Odoo no es prueba de "instalada > web":** tiene API abierta y ya maneja CFDIs; preséntalo como automatización/conciliación, no como exclusividad nuestra.
- ❌ **No prometas:** fechas exactas de ninguna integración contable, escritura directa a la base de datos de CONTPAQi/Aspel/Microsip (solo vía su archivo de importación), ni funciones de IA gratis.
```

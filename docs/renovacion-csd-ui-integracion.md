# Integración a la UI — Renovación de e.firma y CSD (handoff para el sprint)

> **Estado 2026-07-09: IMPLEMENTADO.** La capa de integración ya existe:
> router `api/routers/certifica.py` + wizards del renderer
> (`ui/src/components/fiel/{renovar-efirma,generar-csd}-wizard.tsx`).
> Ver «Cómo quedó» al final; el resto del doc se conserva como referencia
> del diseño original.

El **núcleo Python está completo y probado contra el SAT real** (ver
[renovacion-efirma-csd.md](renovacion-efirma-csd.md)). Lo que falta para exponerlo
en la app es la **capa de integración**: endpoints del agente + pantallas del
renderer. Este doc reúne todo lo necesario para hacerlo sin re-investigar.

## Lo que YA existe (núcleo, no tocar)

API pública (`from sat_descarga import ...`):

| Función | Hace | Devuelve |
|---|---|---|
| `generar_requerimiento_fiel(rfc, curp, correo, password, dir)` | e.firma nueva → `.req`+`.key` | `{key, req}` |
| `generar_renovacion_fiel(fiel, correo, password, dir)` | renovación PF → `.ren`+`.key` | `{key, ren}` |
| `generar_renovacion_fiel_moral(fiel, rfc, correo, password, dir)` | renovación PM | `{key, ren}` |
| `generar_solicitud_csd(fiel, sucursal, password, dir)` | CSD → `.sdg`+`.key` | `{key, sdg}` |
| `enviar_solicitud_csd_fiel(cer, key, pass, sdg, dir, key_nueva_path=…)` | login+sube el `.sdg`+acuse+recupera CSD | `{numero_operacion, acuse_pdf, estado, cer}` |
| `recuperar_ultimo_csd_fiel(cer, key, pass, dir, key_nueva_path=…)` | baja el CSD emitido (después) | `{cer}` |
| `enviar_renovacion_fiel(cer, key, pass, ren, dir, key_nueva_path=…)` | login+sube el `.ren`+acuse+recupera cert | `{numero_operacion, acuse_pdf, estado, cer}` |
| `recuperar_renovacion_fiel(cer, key, pass, dir, key_nueva_path=…)` | baja el `.cer` renovado (después) | `{cer}` |

CLI equivalente: `sat-dm {generar,renovar,solicitar} …`, `sat-dm enviar {csd,ren}`,
`sat-dm recuperar {csd,ren}`. La FIEL vigente se carga con `core.fiel.FIEL(cer, key, pass)`.

## Lo que FALTA (esta es la chamba del sprint)

### 1. Endpoints del agente (`api/server.py`) — como **jobs SSE**

Hoy **no hay** endpoints para esto. El envío hace login headful + scraping y **tarda
minutos** (sobre todo la recuperación del `.cer`), así que va como **job en hilo**
igual que CIEC (`api/jobs.py`, `JobRegistry` + `/events/{id}`). NO como request
síncrono. Endpoints sugeridos (espejo de `/ciec/*` y `/cfdi/fiel`):

- `POST /csd/generar` → síncrono: genera `.sdg`+`.key` (solo crypto local, rápido).
- `POST /csd/enviar` → **job**: login e.firma + sube `.sdg` + acuse (SSE de progreso).
- `POST /csd/recuperar` → **job**: baja el CSD emitido (reintenta; el `.cer` tarda).
- `POST /renovar/generar` → síncrono: genera `.ren`+`.key`.
- `POST /renovar/enviar` → **job**: sube el `.ren` (⚠️ destructivo, ver UX).
- `POST /renovar/recuperar` → **job**: baja el `.cer` renovado.

El login e.firma es **sin captcha** (no hace falta el bridge de captcha que sí usa
CIEC), pero sí conviene emitir progreso por SSE (login → subiendo → número de
operación → acuse → recuperando cert).

### 2. UX del renderer (decisiones ya tomadas)

- **Un flujo de pocos clics, con "avanzado" opcional.** El usuario NO debe teclear
  cosas técnicas; usar defaults sensatos y permitir cambiarlos:
  - **CSD → nombre de sucursal/unidad**: default **"Matriz"**, editable.
  - **Contraseña de la NUEVA `.key`** (CSD y renovación): default **la misma de la
    e.firma vigente**, editable.
- **"Bajar después" es first-class (async):** el envío devuelve el **número de
  operación al instante**; el `.cer` tarda minutos en publicarse. La UI muestra el
  número de operación + acuse enseguida y ofrece **"Descargar certificado"** como
  paso aparte (polling / botón), no bloquea. Reusar `recuperar_*`.
- **Renovación: sustituir cert/.key viejos por los nuevos.** Al completar la
  renovación, reemplazar en el catálogo de la empresa el `.cer` (empresas.json
  `cer_path`) y la `.key` (keychain/almacenamiento) por los renovados. Guardar
  respaldo del viejo. El viejo queda **revocado**.

### 3. Avisos que la UI DEBE mostrar (aprendidos en vivo)

- **Renovación = irreversible y única.** Al enviar el `.ren`, la e.firma actual queda
  **revocada** y se sustituye. Pedir **confirmación explícita** (el CLI ya lo hace).
  A diferencia del CSD (que se puede repetir sin costo), aquí no hay margen.
- **Ventana post-renovación:** tras renovar, hay un lapso (minutos–horas) en que **ni
  la e.firma vieja (revocada) ni la nueva (aún no propagada al login del SAT)**
  sirven para autenticar. Avisar "tu e.firma nueva ya está lista; el SAT puede tardar
  un rato en reconocerla para acceder al portal".
- **Guardar la nueva `.key` + su contraseña.** Sin la `.key` el certificado nuevo no
  sirve. La UI debe dejar clarísimo dónde quedó y que la contraseña es la que eligió.

## Notas técnicas que la UI no debe romper (ya resueltas en el núcleo)

- **`.key` en 3DES, no AES.** El login del SAT y sus herramientas leen la `.key` con
  un JS que **no soporta AES** → el núcleo ya cifra en 3DES (`cifrar_pkcs8_3des`).
  Cualquier código nuevo que genere/reescriba llaves debe usar esa función, no
  `BestAvailableEncryption`.
- **Login robusto** ante el stall intermitente del NIDP (`/nidp/app`) — ya manejado
  con reintento + goto directo. No bajar los reintentos.
- **Descarga del `.cer`** por HTTP directo desde `rdc.sat.gob.mx` (público) — ya
  resuelto; no intentar bajarlo por el navegador (lo trata como descarga).
- **Trámite FIEL-only:** renovación y CSD requieren e.firma; no hay variante CIEC
  (excepción a la convención de exponer ambos canales).

## Checklist del sprint

- [x] Endpoints como jobs SSE (router `certifica.py`).
- [x] Pantallas del renderer: wizards de 4 pasos con progreso por fases.
- [x] Confirmación destructiva + avisos de la ventana post-renovación.
- [x] Sustitución cert/.key en el catálogo al renovar (+ respaldo `anterior_*`).
- [ ] QA empacado en Windows (playwright/chromium ya cubierto por `portal/setup.py`).

## Cómo quedó (2026-07-09, difiere del plan de arriba a propósito)

**Endpoints fusionados: UN job por trámite** (en vez de `generar` síncrono +
`enviar`/`recuperar`). La generación local tarda <1 s y separarla creaba estados
huérfanos (`.ren`/`.sdg` generados sin enviar) que la UI tendría que administrar;
la confirmación irreversible ocurre ANTES de arrancar el job. Rutas reales
(`sat_descarga/api/routers/certifica.py`):

- `POST /renovar` — job: genera el `.ren`, firma, envía, recupera el `.cer` y
  sustituye la e.firma del catálogo. Requiere `confirmar: true` y e.firma
  vigente (400 si venció). 409 si ya hay una renovación pendiente.
- `POST /renovar/recuperar` — job no destructivo: baja el cert pendiente
  (password del keychain) y completa la sustitución.
- `POST /csd` — job: genera `.key`+`.sdg`, envía y recupera (intentos cortos:
  «bajar después» es first-class). `uso` = sucursal/OU, default
  "Facturación general".
- `POST /csd/recuperar` — job: baja el `.cer` de un CSD pendiente.

Progreso por SSE con eventos `{"event":"fase","fase":…}`
(`generando → firmando → enviando → numero_operacion → acuse → recuperando →
guardando`), emitidos por el callback `on_progreso` de `portal/csd.py`.

**Persistencia** (`cli/config_store.py`): `renovacion_pendiente` y `csds[]` en
empresas.json se escriben EN CUANTO hay número de operación (si la app muere a
media recuperación, la UI retoma con `*/recuperar`); respaldo de la e.firma
anterior en `efirma/{RFC}/anterior_{stamp}/` antes de sustituir.

**Contraseña del CSD** (decisión de producto 2026-07-09): la elige el usuario en
el wizard (mín. 8) y se guarda en el **keychain** (`csd:{RFC}`) **y** en un
`.txt` junto a la `.key` (`*_contraseña.txt`) — excepción consciente a la regla
"contraseñas solo en keychain", para que la app pueda timbrar CFDI/nómina con el
sello más adelante y el usuario conserve una copia legible. En renovación, la
contraseña de la `.key` nueva = la de la e.firma vigente (sin teclear otra).

**Renderer**: `RenovarEfirmaWizard` (fila expandida de /empresas y card e.firma
del detalle) y `GenerarCsdWizard` (sin trigger visible: se conectará desde el
Expediente fiscal; QA con `/empresas/detalle?rfc=…&labs=csd`). Ambos sobre el
hook genérico `useJob` (`use-job.ts`). La vía manual de actualizar `.cer`/`.key`
se conserva en el detalle (vencida → trámite presencial).

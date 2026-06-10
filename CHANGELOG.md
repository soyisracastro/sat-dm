# Changelog

> **Nota sobre versionado**: Las entradas previas v0.1.0–v1.2.0 corresponden al paquete Python pip-installable y a metadatos desincronizados de subproyectos. **v1.0.0 (esta) inicia la numeración del producto distribuible TodoConta Desktop** (Python + Next + Electron empaquetado). Ver [docs/versionado.md](docs/versionado.md) para la convención SemVer aplicada.

## [Unreleased]

_Cambios mergeados a `main` aún no etiquetados; el release de la semana los promueve._

## [1.1.0] - 2026-06-10

### Rediseño de la interfaz (v2)

- **Sidebar nuevo** colapsable: marca arriba, **selector de empresa** con badge PF/PM a
  color y RFC, navegación plana de 7 secciones, y footer con Ayuda + menú de cuenta
  (plan, email, suscripción, cerrar sesión; corona de Fundador con tooltip).
- **Barra de estado inferior**: conexión con el agente, CFDIs del mes y última descarga
  de la empresa activa, y semáforo de vencimiento de su e.firma (o "Acceso con CIEC").
- **Pantalla de Ayuda** nueva: FAQ con buscador, contacto de soporte y guías.
- **Alta de empresa simplificada**: ya no pide nombre — se completa solo con la razón
  social del certificado (e.firma) o el RFC (CIEC).
- **Quitar e.firma** desde el detalle de empresa (con confirmación): la empresa queda
  solo-CIEC y deja de intentarse la FIEL vencida.
- **Filtros de comprobantes colapsables** con contador de filtros activos.
- **Ajustes en rejilla de tarjetas** (Almacenamiento, Apariencia, Notificaciones,
  Acerca de).
- **Titlebar de Windows sin marco** con controles propios (minimizar/maximizar/cerrar,
  Aero Snap y doble-click conservados); macOS intacto.
- **Copy depurado en toda la app**: fuera tecnicismos de implementación (keychain,
  servidor, localhost); se quedan los términos fiscales (CFDI, RFC, e.firma, CIEC,
  EFOS, Art. 69-B).

### Login en-app (reemplaza el device-code flow)

- **Inicia sesión sin salir de la app**: pantalla de login estilo Notion con correo +
  contraseña o **código de acceso de 6 dígitos** que se teclea en la misma ventana
  (auto-avance, pegar el código completo, reenviar con timer). Antes había que abrir el
  navegador, confirmar un código de activación y esperar el polling.
- **Crear cuenta desde el desktop**: registro con nombre + correo (+ contraseña o por
  código), contra la misma base de cuentas de app.todoconta.com — la cuenta sirve igual
  en la app en línea. Botón de Google visible pero deshabilitado (próximamente).
- **La sesión ya no se cae ante un 401**: el agente renueva la sesión con el
  `refresh_token` guardado antes de desloguear (esto deslogueó a un usuario en vivo el
  2026-06-10). Aplica al license check y al checkout de Fundador.
- El device-code flow sigue disponible en el agente como fallback (`/auth/init` +
  `/auth/poll`), pero la UI ya no lo usa.

### Copy

- **Descripción de la app unificada en todas las distribuciones.** El tooltip del acceso directo en Windows mostraba un texto interno/técnico (`TodoConta Desktop — app de escritorio (Electron) sobre el agente SAT (Python)`). Ahora dice **«TodoConta Desktop — Administración de CFDIs y herramientas fiscales»** (`description` en `desktop/package.json`, mapeado al `FileDescription` del `.exe`). El `Comment` del desktop entry de Linux (`electron-builder.yml`) se alinea con el mismo copy (sin el prefijo del nombre, que el campo `Name` ya provee). Toma efecto en el próximo build del instalador.

### Rendimiento

- **El registry de jobs ya no crece sin tope**: los jobs terminados se podan al crear nuevos (se conservan los últimos 20 para `/jobs/{id}`); antes cada descarga de la sesión dejaba su job y su cola de eventos en memoria para siempre.
- **Log de jobs CIEC acotado a 500 entradas (FIFO)** en la UI: un job largo emitía miles de eventos y cada uno re-renderizaba una lista cada vez más grande.
- **El polling de `/health` se pausa con la ventana oculta** (minimizada o en background) y ya no encima requests si el agente tarda más que el intervalo; al volver el foco dispara un check inmediato. Mismo guard anti-encimado en el polling de verificación WS y en el del login.
- **Listas largas con render acotado**: paginación local opcional en `ResourceList` (aplicada a solicitudes WS) y "Mostrar más" incremental en el historial — pintar cientos de filas de golpe congelaba equipos modestos.

### Arranque y resiliencia

- **La ventana abre de inmediato.** Antes, Electron esperaba el `/health` completo del agente antes de crear la ventana: en equipos con HDD + antivirus escaneando el binario sin firma eso eran 30-60 segundos sin NADA en pantalla (la app parecía rota). Ahora el spawn asigna puerto/token, la ventana se crea al instante y el `StartupSplash` del renderer (que ya tenía mensajes por fases) por fin se ve durante el arranque real.
- **Monitor del agente con reinicio automático.** Si el agente muere después del arranque (crash, OOM), el shell lo detecta (3 checks fallidos ≈ 30s) y lo reinicia en el mismo puerto y con el mismo token, hasta 3 veces consecutivas; el renderer se recupera solo vía su polling de `/health`. Antes un crash dejaba la app muda hasta reiniciarla a mano.
- **Cierre sin huérfanos**: al salir, si el agente no responde al SIGTERM en 2 segundos se le manda SIGKILL — un Python colgado ya no queda vivo consumiendo memoria tras cerrar la app.

### Interno

- **`api/server.py` partido en routers por dominio** (`api/routers/{webservice,portal,empresas,procesador,utilidades,system}.py` + `api/state.py` para la sesión FIEL y helpers compartidos). El monolito de 2,579 líneas quedó en 177; las rutas HTTP no cambiaron ni un carácter (verificado contra snapshot pre-refactor). Sin impacto para UI/CLI.

### Interno (UI)

- **Hook genérico `useProcesadorGenerico`**: los 3 hooks de procesador (CFDI/pagos/nómina, ~135 líneas c/u con el mismo patrón de filtros + persistencia debounced + refetch) quedaron como wrappers de ~45 líneas sobre un genérico tipado. Un bug del patrón ahora se corrige en un solo lugar.
- **`lib/errores.ts` con `mensajeDeError()`**: 42 call sites dejaron de repetir `e instanceof Error ? e.message : String(e)`.

### UX

- **Captcha expirado ya no deja el modal abierto**: al agotarse los 5 minutos, el modal se cierra de inmediato y se muestra "El captcha expiró… Inicia la descarga de nuevo" en lugar de un modal congelado esperando un input que ya no sirve.

### Infra

- **Pipeline de firma de código Windows listo** (certificado pendiente): `release.yml` trae los steps de firma de `sat-agent.exe` (Azure Trusted Signing) y verificación post-build, ambos auto-saltables hasta que existan los secrets; `electron-builder.yml` documenta el bloque `azureSignOptions` + `forceCodeSigning`. ⚠️ Documentado en [docs/firma-codigo.md](docs/firma-codigo.md): la vía `WIN_CSC_LINK` (PFX) ya no aplica a certs OV/EV modernos — decidir entre Azure Trusted Signing (~$10/mes) y EV+firma en nube del CA antes de comprar. Firmar el agente, además de SmartScreen, reduce el escaneo de Defender que causa los 30-60 s del primer arranque.

### Infra (macOS)

- **El release ahora construye DMG de macOS por arquitectura** (job `release-macos`: Intel x64 en `macos-13`, Apple Silicon arm64 en `macos-latest` — PyInstaller no cross-compila el agente), con smoke test de `/health` del binario empacado. Sin los secrets de Apple salen sin firmar (QA con clic-derecho → Abrir); la config de hardened runtime + entitlements (Electron JIT + dylibs del agente PyInstaller) ya está lista y la notarización se activa descomentando `notarize` al tener el Developer ID. Checklist en [docs/firma-codigo.md](docs/firma-codigo.md).

### Seguridad

- **Token efímero entre Electron y el agente local.** El shell genera un token aleatorio por arranque y se lo pasa al agente (env `SAT_AGENT_TOKEN`) y al renderer (preload → `window.satAgent.token`); un middleware del agente rechaza con 401 cualquier request sin él (header `X-Agent-Token`, o `?token=` en SSE porque `EventSource` no acepta headers). Cierra el hueco de que cualquier otro proceso local del usuario usara el agente — que mantiene la FIEL cargada en sesión. Sin la env (CLI o `uvicorn` manual en dev) no se exige nada.
- **Anti zip-slip en la descarga WS**: los miembros del ZIP que regresa el SAT se validan antes de extraer; una ruta `../` o absoluta rechaza el paquete completo (`webservice/descarga.py`).
- **Parser lxml endurecido** para todo XML de origen externo (respuestas SOAP del SAT, CFDIs del usuario): sin resolución de entidades, sin DTD y sin red (anti-XXE). Helper central `core/xml_seguro.py` aplicado en `webservice/`, `utils/xml_reader.py` y el parser del procesador.
- **Catálogo a prueba de concurrencia**: `empresas.json`, `historial/*.json` y `settings.json` ahora se escriben de forma atómica (`.tmp` + `os.replace`) y los read-modify-write van serializados con lock — mismo patrón que ya tenían las solicitudes. Evita altas perdidas y JSON corrupto con requests concurrentes.
- **`/abrir` canonicaliza rutas** (resuelve symlinks y `..`) antes de compararlas contra la lista blanca del historial.
- **Electron**: el handler del protocolo `app://` valida el path con `path.relative`; `shell.openExternal` solo acepta `http(s):`/`mailto:`; el `code` del deep link `todoconta://` se valida con charset estricto antes de cruzar al renderer.

- Bump 1.0.6 → 1.1.0 (3 archivos; `pyproject.toml` venía desincronizado en 1.0.4).

---

## [1.0.6] - 2026-06-08

Cierra los **huecos de navegación en subrutas (2 segmentos)** que quedaron tras el protocolo `app://` de v1.0.5, y agrega un flujo para **depurar el bundle empacado en Mac sin instalador**.

### Bug fix

- **Detalle de empresa (engrane) ya no manda al dashboard.** `/empresas/[rfc]` era una ruta dinámica con `dynamicParams: false` y un único placeholder `_`. Bajo `output: 'export'`, cualquier RFC real es **404** → el handler `app://` caía al `index.html` raíz → se veía el inicio. Se reemplazó por una **ruta estática `/empresas/detalle?rfc=…`** que lee el RFC con `useSearchParams()` dentro de `<Suspense>`. Funciona igual en navegación SPA y en reload; se elimina el hack del placeholder y la limitación de 404 en reload.
- **Subrutas estáticas en blanco** (`/comprobantes/cfdi`, `/comprobantes/{nomina,pagos}`, `/descarga/rapida`): artefacto de un build sin `trailingSlash` (se exportaban como `cfdi.html`, no `cfdi/index.html`), así que el handler `app://` no las encontraba y caía al index. Con el build de v1.0.5 (`trailingSlash: true`) cada subruta exporta su `index.html`; se verificó que el handler las resuelve sin fallback.
- **Error boundaries** (`app/error.tsx` + `app/global-error.tsx`): un error de runtime ya no deja pantalla en blanco (que se confundía con "página perdida"); muestra mensaje + reintentar conservando el shell.
- **Copy**: `e-firma` → `e.firma` en la UI (consistencia con el resto del producto; el guion permitía un quiebre de línea "e-/firma").

### Tooling

- **`pnpm debug:packaged`** (en `desktop/`): hace `next build` del UI y levanta Electron sirviendo `ui/out` por `app://` con DevTools y logging del handler (vía `SAT_RENDERER_BUNDLE_DIR` + `SAT_DEBUG_RENDERER`). Reproduce el entorno empacado en Mac **sin** construir un instalador, para validar el routing de subrutas antes del build.
- Bump 1.0.5 → 1.0.6 (ui + desktop).

---

## [1.0.5] - 2026-06-06

Fix de **navegación entre secciones (white-screen), imágenes e íconos** en el bundle empacado. Continúa el diagnóstico de v1.0.4: el `assetPrefix: './'` arreglaba los chunks `_next/` del index, pero `file://` no puede servir paths absolutos ni navegación SPA.

### Bug fix

- **Protocolo propio `app://` en lugar de `file://`** (`desktop/main.js`). El renderer empacado ahora se sirve por un esquema privilegiado (`standard` + `secure`) con un **origen real**, registrado vía `protocol.handle`. El handler mapea el pathname al archivo dentro de `<resources>/ui` con fallback SPA a `index.html` (cubre reload de rutas dinámicas como `/empresas/<RFC>/`) y guarda anti path-traversal.
  - **Causa del white-screen**: `next/link` emite `href` absolutos (`/empresas`, `/comprobantes`, …). Sobre `file://`, el prefetch y la navegación resolvían a `file:///C:/empresas` → `ERR_FILE_NOT_FOUND` → pantalla blanca. Con origen `app://` resuelven contra la raíz del bundle.
  - **Causa de imágenes rotas**: `next/image src="/icon.png"` (login) → `file:///C:/icon.png`. Igual: con `app://` resuelve correctamente.

- **`next.config.ts`**: se **elimina** `assetPrefix: './'` (era frágil: `./_next` se rompía al navegar a subrutas como `/comprobantes/cfdi/`; con `app://` los paths absolutos ya son correctos en toda ruta) y se añade **`trailingSlash: true`** (cada ruta exporta como `<ruta>/index.html`, uniforme y fácil de mapear por el handler).

- **Íconos 100% offline** (`ui/src/lib/icons.ts`): se registran los 39 íconos Phosphor que faltaban en el registro `addIcon`. Sin esto, Iconify caía a su API remota (`api.iconify.design/ph.json`), que falla en el bundle empacado, y los íconos (`star-fill`, `bell-light`, `files-light`, `rocket-light`, …) no aparecían.

### Nota sobre CORS (v1.0.3)

Sigue vigente: con `allow_origins=["*"]` el cambio de origen `file://` → `app://` no afecta el acceso del renderer al agente local.

---

## [1.0.4] - 2026-06-05

**ROOT CAUSE REAL** del *"Cargando…" infinito en Windows*. Diagnóstico definitivo desde DevTools del renderer empacado.

### Bug fix

- **`assetPrefix: './'` en `next.config.ts`** para builds de producción. Por default, Next.js emite paths absolutos (`/_next/static/chunks/abc.js`) que el browser, al servirse desde `file://...resources/ui/index.html`, resuelve como `file:///C:/_next/...` — raíz del disco. **Ningún chunk de JS/CSS cargaba** (17 × `ERR_FILE_NOT_FOUND`). React jamás arrancaba; lo que el usuario veía como *"TodoConta / Cargando…"* era el HTML pre-renderizado del SSG inicial, sin hidratación nunca.

  Cómo nos despistó: el `/health 200` que vimos en logs del agente venía del `waitForHealth()` del proceso main de Electron (Node, no browser), no del renderer. Por eso parecía que el renderer estaba conectado cuando en realidad ni siquiera había ejecutado un solo byte de JavaScript.

  Fix: `assetPrefix: process.env.NODE_ENV === 'production' ? './' : undefined` — paths relativos en `pnpm build`, sin afectar `pnpm dev` (donde el HMR de Next requiere paths absolutos).

  Validado: tras el build, `out/index.html` ahora referencia `./_next/static/chunks/...` (paths relativos).

### Nota sobre v1.0.3 (CORS)

El fix de CORS sigue vigente y es necesario — cuando v1.0.4 finalmente arranque React en el bundle empacado, los `fetch()` desde `file://` enviarán `Origin: null` y necesitan estar permitidos. No remover.

---

## [1.0.3] - 2026-06-05

Fix RAÍZ del bug *"Cargando…" infinito en Windows*. Diagnóstico confirmado por logs reales del agente en producción (v1.0.2 instalada).

### Bug fix

- **CORS bloqueaba al renderer en producción**: la `allow_origins` del agente FastAPI incluía `localhost:3000/3001` (dev) y `app.todoconta.com` (cloud) pero **NO** `null`/`file://`, que es el origin que envía el navegador cuando Electron sirve el bundle empacado desde `file://...resources/ui/index.html`. Resultado:
  - El renderer hacía `GET /health` → llegaba al agente → uvicorn respondía 200.
  - **El navegador descartaba el response por CORS** antes de entregarlo al JS.
  - `useServerHealth` se quedaba con `isConnected=false`.
  - `AuthProvider` jamás invocaba `/auth/license` (espera `isConnected===true`).
  - `loading` quedaba `true` → splash infinito.
  - Logs del agente confirman: una sola línea `GET /health 200` por arranque, cero llamadas a `/auth/license`.

  Fix: `allow_origins=["*"]` + `allow_credentials=False`. Es seguro porque el agente bindea SOLO a `127.0.0.1` (sin exposición a red externa) y el renderer no envía cookies ni credenciales (el Bearer token de Supabase vive solo en el agente Python).

  El bug no salió en dev porque el renderer se sirve desde `http://localhost:3001` (en la allow-list); solo aparecía en el bundle empacado.

---

## [1.0.2] - 2026-06-05

Fix raíz del bug *"Cargando…" infinito* reportado por dos testers en Windows tras v1.0.1.

### Bug fix

- **Lifespan no-bloqueante**: el agente ya no carga la FIEL al arranque dentro del `lifespan` de FastAPI. La llamada a `keyring.get_password()` que hacía el autoload colgaba indefinidamente en Windows con binario sin firma (Credential Manager espera un prompt UI que nunca llega en proceso non-interactive), impidiendo que uvicorn aceptara conexiones → `/health` jamás respondía → renderer atrapado en "Cargando…". Ahora `lifespan` completa de inmediato, uvicorn arranca, `/health` responde en <100ms.

- **Endpoint `/auth/autocargar-fiel`**: nuevo endpoint POST que reemplaza al autoload del lifespan. El renderer lo invoca en background después del login exitoso. Si falla (FIEL faltante, keyring inaccesible), la app sigue funcional — el usuario carga la FIEL a mano desde Empresas como ya hacía hoy.

- **Bootstrap log temprano**: `__main__.py` ahora loguea PID, argv, cwd y `sys.executable` como **primera línea** del agente. Si un usuario reporta que la app no arranca, podemos pedirle `%LOCALAPPDATA%\TodoConta\logs\agent.log` y saber EXACTAMENTE en qué etapa murió.

- **Hiddenimports defensivos en PyInstaller**: agregados `keyring.backends.{Windows,macOS,SecretService,fail}`, `lxml.html`, `email.mime.application`. Sin los keyring backends, `keyring` caía a un backend null que silenciosamente retornaba None — fuente potencial de bugs en distintos perfiles de Windows.

---

## [1.0.1] - 2026-06-04

Bug fixes detectados en QA del primer release público.

### Cambios

- **UI**: el título de la ventana y el titlebar ahora dicen *"TodoConta"* (antes mostraba *"SAT Descarga Masiva"*, sobra de antes del rebrand).
- **Agente**: el `.exe` ya no abre una ventana de consola DOS negra paralela al iniciar (`console=False` en el spec de PyInstaller). Los logs se persisten a `%LOCALAPPDATA%\TodoConta\logs\agent.log` para diagnóstico.
- **Startup más tolerante**: el shell Electron ahora espera hasta 60s a que el agente responda `/health` (antes 30s), por si Windows Defender está escaneando los DLLs del PyInstaller en el primer arranque.
- **Splash informativo**: la pantalla "Cargando…" muestra ahora un mensaje útil después de 15s indicando que el primer arranque puede tardar mientras AV escanea los archivos, y a los 60s ofrece un botón "Reintentar" en lugar de quedarse en blanco para siempre.

---

## [1.0.0] - 2026-06-03

Primer release público del producto **TodoConta Desktop** — instalador Windows distribuible, login obligatorio integrado con `todoconta-apps`, ventana de **Fundadores** (licencia de por vida) para los primeros usuarios.

### Empaquetado y distribución

- Versionado unificado de los 3 subproyectos (`pyproject.toml`, `ui/package.json`, `desktop/package.json`) a `1.0.0`. A partir de aquí, los 3 archivos se sincronizan en cada release.
- Convención SemVer documentada en `docs/versionado.md`.

### Cambios incompatibles

- **Re-base de numeración**: el paquete Python interno venía en `1.2.0`; el producto distribuible arranca su numeración en `1.0.0`. No hay cambios funcionales — solo el número.

---

## v1.2.0 (2026-05-25)

Reorganización del proyecto **por canal de acceso** y **CLI unificado**.

### Cambios

- **Estructura por subpaquetes** en `sat_descarga/`: `core/` (config, fiel, http_client),
  `webservice/` (auth, solicitud, verificacion, descarga, client), `portal/`
  (login, cfdi, constancia), `utils/` (xml_reader, metadata, organizador, validacion),
  `api/` (server, hosted). El paquete `cli/` se movió dentro de `sat_descarga/cli/`.
- **Login SSO extraído** a `portal/login.py` (`iniciar_sesion_ciec` / `iniciar_sesion_fiel`),
  compartido por todos los scrapers del portal.
- **CLI unificado**: las descargas son subcomandos del grupo `descargar`:
  `sat-dm descargar cfdi` (Web Service), `sat-dm descargar ciec` (portal CFDIs) y
  `sat-dm descargar constancia --metodo ciec|fiel`. Se eliminaron los scripts
  `prueba_*.py` de la raíz (eran los runners reales, no tests).
- **API pública estable** re-exportada en `sat_descarga/__init__.py`:
  `descargar_cfdi`, `FIEL`, `descargar_cfdi_ciec`, `descargar_constancia_ciec/fiel`, etc.
- **Tests**: actualizados a las nuevas rutas + nuevos tests de portal (lógica pura) y CLI.

### Cambios incompatibles

- `sat-dm descargar` ahora es un **grupo**: usar `sat-dm descargar cfdi` para el flujo
  anterior de Web Service.
- Los imports por submódulo cambian (p. ej. `sat_descarga.ciec` → `sat_descarga.portal.cfdi`,
  `sat_descarga.validacion` → `sat_descarga.utils.validacion`). La API por la raíz
  (`from sat_descarga import ...`) se mantiene.

---

## v1.1.0 (2026-05-25)

Descarga de la **Constancia de Situación Fiscal (CSF)** vía el portal del SAT, con
login CIEC o e.firma.

### Nuevas funcionalidades

- **Constancia de Situación Fiscal**: descarga el PDF de la constancia mediante
  scraping del portal (sin Web Service), con dos métodos de login:
  - **CIEC** (RFC + contraseña; el usuario resuelve el captcha).
  - **e.firma / FIEL** (`.cer` + `.key` + contraseña): **100% automático, sin
    captcha** — ideal para automatización/desatendido.
  - API: `descargar_constancia_ciec(rfc, ciec)` y `descargar_constancia_fiel(cer, key, password)`.
  - Endpoint `POST /constancia/descargar`; runners `prueba_constancia.py` y `prueba_constancia_fiel.py`.
- **Login SSO reutilizable**: `iniciar_sesion_ciec()` e `iniciar_sesion_fiel()` en
  `sat_descarga/ciec.py`, compartidos por los scrapers (CFDI, constancia y futuros).
  El flujo CFDI delega en el helper sin cambiar su comportamiento.

### Notas técnicas

- El botón "Generar Constancia" es JSF/PrimeFaces dentro de un iframe (`rfcampc.siat`);
  el PDF abre en un popup (`IdcGeneraConstancia.jsf`). e.firma entra por el lanzador
  (`tipoLogeo=c`) + botón `#buttonFiel`.
- El servidor del SAT usa TLS con clave DH muy pequeña que Node rechaza; el PDF se
  captura desde el navegador (Chromium) en vez de una petición HTTP separada.

### Archivos nuevos

- `sat_descarga/constancia.py` — cliente de la CSF (CIEC + e.firma)
- `prueba_constancia.py` / `prueba_constancia_fiel.py` — runners

---

## v1.0.0 (2026-05-24)

Interfaz web (UI + API), descarga vía CIEC sin e-firma, y madurez del proyecto.

### Nuevas funcionalidades

- **Descarga vía CIEC (portal web, sin e-firma)**: para contribuyentes que no cuentan con FIEL
  - `sat_descarga/ciec.py` — cliente Playwright headful (el usuario resuelve el captcha)
  - Recibidos (día por día) y Emitidos (rango); modo "ambos" con un solo captcha
  - Descarga item por item vía `RecuperaCfdi.aspx?Datos=`; subcarpetas `recibidos/` y `emitidos/`
  - Detección de cuota diaria del portal (se detiene tras 3 fallos seguidos)
  - Runner de ejemplo: `prueba_ciec.py RFC CIEC desde hasta [R|E|RE]`
- **Servidor FastAPI** (`localhost:8787`): expone SATDescarga vía HTTP sin que la e-firma salga de la máquina (compatible con apps web como todoconta)
  - Auth (e-firma en memoria), solicitar/verificar/descargar, folio, metadata, validación, descarga-completa, descarga-inteligente y `/ciec/descargar`
- **UI web (Next.js)**: interfaz para descarga, validación y organización de CFDIs

### Archivos nuevos

- `sat_descarga/ciec.py` — descarga vía portal CIEC (Playwright)
- `sat_descarga/server.py` — servidor FastAPI
- `ui/` — aplicación web Next.js
- `docs/protocolo-sat.md` — detalle del protocolo SOAP del Web Service y de la mecánica del portal CIEC

---

## v0.2.0 (2026-04-01)

Validación, metadata, descarga por UUID, y herramientas de organización de XMLs.

### Nuevas funcionalidades

- **Validación de CFDI ante el SAT**: verifica estatus (Vigente/Cancelado/No Encontrado) sin FIEL
  - `sat-dm validar ./xmls/` con export a CSV
  - Validación masiva con ThreadPoolExecutor (10 hilos en paralelo)
  - Endpoint `POST /validar` en FastAPI (compatible con todoconta-apps)
- **Descarga de metadata**: resumen rápido de CFDIs sin descargar XMLs
  - Hasta 1,000,000 registros por solicitud, procesados en segundos
  - Parser automático del CSV del SAT (separador `~`, encoding auto-detect)
  - `sat-dm metadata --desde --hasta --csv-export reporte.csv`
  - Flag `--local` para re-parsear metadata ya descargada
  - Deduplicación automática por UUID
- **Descarga por UUID**: `SolicitaDescargaFolio` para descargar CFDIs específicos
  - `descargar_por_uuid()` en la API Python
  - Endpoint `POST /solicitar-folio` en FastAPI
- **Organizador de XMLs**: herramientas para ordenar archivos descargados
  - `sat-dm organizar carpetas` — 9 estructuras de carpetas (RFC/año/mes, tipo/año/mes, etc.)
  - `sat-dm organizar renombrar` — 5 patrones de renombrado por contenido del XML
  - `sat-dm organizar deduplicar` — elimina duplicados por UUID (con dry-run)
  - Agrupador por versión CFDI y tipo de comprobante
- **Parser ligero de XML CFDI**: extrae headers (emisor, receptor, fecha, UUID, total) sin parseo completo, namespace-agnostic

### Correcciones

- **RFC de personas morales**: el certificado FIEL contiene `RFC_EMPRESA / RFC_REPRESENTANTE` en UniqueIdentifier; ahora toma correctamente el primero (antes tomaba el del representante legal)
- **Auto-detección de FIEL**: excluye directorios `tests/`, `.venv/` y archivos CSD del globbing

### Archivos nuevos

- `sat_descarga/validacion.py` — validación de estatus CFDI contra SAT
- `sat_descarga/metadata.py` — parser de metadata CSV del SAT
- `sat_descarga/xml_reader.py` — parser ligero de CFDI XML
- `sat_descarga/organizador.py` — organizar, renombrar, deduplicar XMLs
- `cli/validar.py` — CLI de validación masiva
- `cli/metadata_cmd.py` — CLI de descarga de metadata
- `cli/organizar.py` — CLI de organización de archivos

---

## v0.1.0 (2026-03-30)

Primera versión funcional. Descarga masiva de CFDIs del SAT vía Web Service oficial (API v1.5).

### Funcionalidades

- **Descarga masiva vía e-firma (FIEL)**: flujo completo solicitar -> verificar -> descargar
- **CLI multi-empresa**: registrar múltiples FIELs, seleccionar interactivamente o por argumentos
- **Gestión de empresas**: `empresas add`, `list`, `remove`, `default`
- **Auto-detección de FIEL**: busca archivos `.cer`, `.key` y `password.txt` automáticamente
- **Organización por RFC**: archivos FIEL en `./efirma/{RFC}/`, descargas en `./descargas/{RFC}/`
- **Fecha de vencimiento**: visible en el listado de empresas con indicador de color
- **Retomar solicitudes**: `retomar <RequestID>` para descargas interrumpidas
- **Emitidos y recibidos**: descarga individual o ambos en una sola ejecución
- **Polling automático**: backoff exponencial (30s a 5min) durante el procesamiento del SAT
- **Reintentos HTTP**: 6 reintentos con backoff para la inestabilidad SSL del SAT
- **Renovación de token**: automática antes de cada descarga (token dura ~5 min)

### Detalles técnicos

- API v1.5 del SAT (mayo 2025): firma xmldsig enveloped con C14N inclusiva
- `EstadoComprobante`: `"Vigente"`, `"Cancelado"`, `"Todos"`
- Recibidos requiere `RfcReceptor` explícito
- SOAPAction de descarga: `IDescargaMasivaTercerosService/Descargar`
- Probado con descarga real de ~950 CFDIs (emitidos + recibidos)

# Tareas ↔ Google Calendar — plan de sincronización (unidireccional v1)

> **Estado**: diseñado, NO implementado. El modelo de datos de tareas ya está
> preparado (`gcal_event_id` reservado en `~/.sat-descarga/tareas.json`).
> Decisión de producto (2026-07-09): **unidireccional app → Calendar**;
> la bidireccional queda descartada para v1 (sync tokens + conflictos no
> justifican el costo para el caso de uso "ver mis pendientes en mi calendario").

## Qué hace la v1

Cada **tarea con fecha límite** se publica como evento de día completo en un
calendario dedicado **«TodoConta»** de la cuenta Google del usuario:

| En la app                        | En Google Calendar                                    |
| -------------------------------- | ----------------------------------------------------- |
| Crear tarea con fecha            | Crear evento (all-day en `fecha`)                     |
| Cambiar título/fecha/empresa     | PATCH del evento (título: `titulo — {empresa}`)       |
| Quitar la fecha                  | Borrar el evento (sin fecha no hay dónde ponerlo)     |
| Completar (estado `hecho`)       | PATCH: prefijo "✓ " en el summary (no se borra)       |
| Reabrir                          | PATCH: quita el prefijo                               |
| Eliminar tarea                   | Borrar el evento                                      |

- El vínculo se guarda en `gcal_event_id` (ya existe en el esquema).
- La descripción del evento lleva RFC/empresa + "Creado por TodoConta Desktop"
  y un deep link `todoconta://` a la tarea (el protocolo ya está registrado
  por el trabajo de OAuth).
- Los cambios hechos EN Calendar no regresan (v1): la app es la fuente de
  verdad. Si el usuario mueve/borra el evento en Calendar, la siguiente
  reconciliación lo repone.

## Arquitectura (todo en el agente Python)

La UI nunca toca Google: el agente hace OAuth y llama la API. Así el sync
también corre para tareas creadas por CLI o automatizaciones futuras.

1. **OAuth**: reutilizar el **broker PKCE del agente** (rama
   `feat/oauth-google-desktop`, ya probado: loopback + deep link
   `todoconta://auth-callback`). Se agrega el scope de Calendar como
   **consent incremental** — el login de la app NO lo pide; solo se solicita
   al activar el sync en Ajustes.
2. **Tokens**: refresh token en el **keychain del SO** (`core/secretos.py`,
   mismo trato que CIEC/e.firma — nunca JSON plano).
3. **Cliente Calendar**: `httpx` directo contra
   `https://www.googleapis.com/calendar/v3` (sin SDK de Google; mismo espíritu
   del cliente SOAP manual). Endpoints: `calendars` (crear el calendario
   dedicado una vez, guardar su id en `settings.json`), `events` (insert/
   patch/delete).
4. **Motor de sync** (`sat_descarga/tareas/gcal.py`):
   - Hook en cada mutación del store (crear/actualizar/eliminar) → encola el
     push (best-effort, en hilo daemon como los jobs; sin red no truena la
     mutación, queda pendiente).
   - **Reconciliación** al arrancar el agente y cada ~6 h: recorre tareas con
     fecha y verifica/repone eventos (cubre mutaciones hechas offline).
   - Marca `gcal_sync_error` en la tarea si Google rechaza repetidamente
     (la UI puede pintar un aviso discreto).
5. **API del agente**:
   - `GET /tareas/gcal/estado` — conectado o no, email, calendario id.
   - `POST /tareas/gcal/conectar` — arranca el flujo OAuth (job SSE como los
     de Certifica, evento `fase`).
   - `DELETE /tareas/gcal` — desconecta (borra token del keychain; opción de
     borrar el calendario «TodoConta»).
6. **UI**: toggle en **/ajustes** («Sincronizar tareas con Google Calendar»)
   + badge de estado; nada cambia en /tareas salvo un icono discreto en las
   tareas sincronizadas.

## Scopes y verificación de Google (el camino largo)

- Scope elegido: `https://www.googleapis.com/auth/calendar.app.created` —
  **el más angosto que cubre el caso**: solo calendarios creados por la app
  (perfecto para el calendario «TodoConta» dedicado). Evita pedir
  `.../auth/calendar` (acceso total, scope *restricted*).
- `calendar.app.created` es scope **sensible**: requiere pasar la
  **verificación de OAuth de Google** (app + branding). OJO: ya tenemos
  pendiente la verificación de marca del consent screen (hoy muestra el ref
  de Supabase, no "TodoConta" — ver memoria de OAuth). **Hay que resolver esa
  verificación ANTES o junto con esta**; mientras la app esté sin verificar,
  el consent muestra la pantalla de "app no verificada" (funciona para
  nosotros y early adopters, pero no para público general).
- El client de Google Cloud ya existe (proyecto compartido con todoconta-apps);
  solo se agrega el scope y se re-somete a verificación.

## Orden de trabajo sugerido (sprint siguiente)

1. `tareas/gcal.py`: cliente Calendar + motor (insert/patch/delete + reconciliación) — testeable con `respx`/mocks.
2. Broker OAuth: scope incremental + guardado en keychain.
3. Endpoints `/tareas/gcal/*` + toggle en /ajustes.
4. Someter verificación de Google (branding + scope sensible) — en paralelo desde el día 1, es lo que más tarda.
5. QA: crear/editar/completar/eliminar con red y sin red (reconciliación), revocar acceso desde Google y reconectar.

## Fuera de alcance (decidido)

- Bidireccional (leer cambios de Calendar): requeriría `syncToken` +
  webhooks/polling + resolución de conflictos. Solo si los usuarios lo piden.
- Tareas sin fecha: no se publican (no tienen representación natural en un
  calendario).
- Google Tasks en vez de Calendar: la API de Tasks no soporta hora/recordatorios
  ricos ni colores y su UI móvil es más débil; Calendar es donde el contador
  ya vive. Reevaluar solo si hay feedback.

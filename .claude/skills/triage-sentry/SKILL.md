---
name: triage-sentry
description: Revisa a mitad de semana lo que Sentry capturó (la mayoría no avisa por correo) y arma una lista priorizada para decidir qué se arregla, cuándo, y qué se ignora — con tiempo de reaccionar antes del release del viernes. Independiente de /release-semanal a propósito. Acepta un argumento opcional con el periodo (ej. "24h", "14d") o vacío para 7 días.
---

# Triage de Sentry (mitad de semana)

Revisión deliberadamente separada del corte de release — el objetivo es dar tiempo real de
trabajar, planear o descartar lo que aparezca, no enterarse el viernes cuando ya no hay
margen. Cubre TODOS los proyectos de Sentry de la organización (hoy: desktop; agregar
otros conforme se instrumenten — ver [[project-api-publica-integradores-mvp]] y el fix de
listas negras para contexto de qué más podría sumarse).

El argumento (`$ARGUMENTS`) es opcional: vacío → periodo de 7 días; si viene un valor
(`24h`, `14d`, etc.) úsalo como `period` en las búsquedas.

## 0. Precondición

El MCP de Sentry debe estar conectado (`find_organizations` no debe fallar). Si falla,
**detente y avisa**: el usuario necesita reconectarlo (`/mcp` en sesión interactiva) — a
diferencia de cuando esto corre como paso best-effort dentro de otro flujo, aquí ES el
propósito del skill, no tiene sentido continuar sin Sentry.

## 1. Descubrir organización y proyecto(s)

1. `find_organizations()` — si hay más de una, confirma con el usuario cuál (o recuerda la
   respuesta de la vez anterior si ya se estableció en la conversación).
2. `find_projects(organizationSlug)` — lista los proyectos disponibles.

## 2. Reunir issues del periodo

Por cada proyecto, corre `search_issues` con `period` según el argumento (default 7d):

1. **Nuevos**: `query: "is:new"` — todo lo que apareció por primera vez en el periodo.
2. **Regresiones**: `query: "is:regressed"` — algo que ya se había marcado resuelto y volvió.
3. **Más frecuentes/impacto**: `query: "is:unresolved"`, `sort: "freq"` y también
   `sort: "user"` — para no perder algo viejo que de repente subió de volumen o afectó
   muchos usuarios aunque no sea técnicamente "nuevo".

No uses `search_events` aquí (es para conteos/agregaciones puntuales, no para esta barrida).

## 3. Clasificar

Agrupa el resultado combinado (deduplicado por issue) en:

- 🔴 **Crítico** — nivel fatal/error CON alto volumen o muchos usuarios afectados, o
  cualquier regresión de algo que ya se había dado por resuelto.
- 🟡 **Revisar** — nuevo pero bajo volumen, o nivel warning con impacto incierto.
- 🟢 **Ruido conocido** — algo que ya se decidió ignorar en una vuelta anterior (nivel
  info, o ya está `is:ignored` en Sentry — igual repórtalo pero abajo, para no repetir la
  discusión cada semana salvo que el volumen haya cambiado mucho).

## 4. Presentar y decidir

Para cada issue en 🔴 y 🟡: título, nivel, primera/última vez visto, conteo de eventos,
usuarios afectados, link (`permalink` si el tool lo trae). Para 🔴 en particular, ofrece
profundizar con `analyze_issue_with_seer` (root cause de Sentry) o leer directo el código
del stack trace si el issue apunta a un archivo de este repo.

Con el usuario, decide por issue una de: **arreglar ahora** (pasa a trabajo normal de la
sesión), **planear para el release del viernes** (anótalo para que `/release-semanal` lo
recoja esa semana — no hace falta tocar ese skill, basta con que quede en el CHANGELOG
`[Unreleased]` cuando se resuelva), o **posponer/ignorar** (usa `update_issue` para
reflejarlo en Sentry — resolved/ignored — así la próxima corrida no lo vuelve a traer como
ruido).

## 5. Cierre

Resumen corto: cuántos 🔴/🟡/🟢, cuáles quedaron con acción tomada vs pendientes, y si algo
de esto **debe** entrar al release de esta semana antes de cortarlo el viernes.

## Recordatorios

- Este skill es de solo lectura salvo por `update_issue` cuando el usuario decide
  explícitamente resolver/ignorar algo — nunca lo hagas sin confirmar issue por issue.
- No dupliques el trabajo de `/release-semanal` — ese skill no vuelve a tocar Sentry; si
  algo de aquí requiere código, ese trabajo se hace en su propia sesión/PR como cualquier
  fix, y llega al release por el CHANGELOG normal.

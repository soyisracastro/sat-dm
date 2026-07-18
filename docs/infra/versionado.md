# Versionado — TodoConta Desktop

Seguimos [Semantic Versioning 2.0](https://semver.org/lang/es/) con tags git `vX.Y.Z`.

## Esquema

```
v MAJOR . MINOR . PATCH
```

| Componente | Cuándo bumpea | Ejemplos |
|---|---|---|
| **MAJOR** (X) | Cambio que **rompe** algo del usuario actual: formato incompatible de datos en `~/.sat-descarga/`, eliminación de una operación crítica, cambio de path de configuración. Requiere sección "Migración" en release notes. | Mover de `~/.sat-descarga/` a `%APPDATA%\TodoConta\` en Windows. |
| **MINOR** (Y) | Nueva feature visible, **backwards-compatible**. El usuario actualiza y todo lo viejo sigue funcionando + tiene cosas nuevas. | Soporte de nuevo tipo de comprobante. Nueva pantalla en el sidebar. Soporte para descargar nuevo trámite del portal SAT. |
| **PATCH** (Z) | Bug fix, refactor invisible, ajuste de copy/performance. Sin features nuevas. | Fix en el parser XML. Mensaje de error mejorado. Optimización del bundle. |

## Tabla práctica de decisión

| Cambio | Bump | Razón |
|---|---|---|
| Fix en parser XML | PATCH | Comportamiento corregido, sin nueva feature |
| Texto de error mejorado | PATCH | UX polish |
| Nueva sección en sidebar | MINOR | Feature nueva, no rompe nada |
| Soporte de nuevo tipo de comprobante (ej. CFDI 4.1) | MINOR | Feature aditiva |
| Cambio del path de datos `~/.sat-descarga/` a otro lugar | MAJOR | Rompe instalaciones previas |
| Removal de un endpoint API interno que el renderer ya no usa | MINOR | Solo afecta interno; nadie externo lo usaba |
| Cambio del modelo de auth (ej. agregar OAuth) | MINOR si es aditivo, MAJOR si rompe el login viejo |
| Cambio del `appId` en electron-builder | MAJOR | Rompe auto-update; los usuarios reciben "nueva app" |

## Regla operativa

**Los 3 archivos siempre sincronizados** en cada release:

- `pyproject.toml` → `version = "X.Y.Z"`
- `ui/package.json` → `"version": "X.Y.Z"`
- `desktop/package.json` → `"version": "X.Y.Z"`

Tras el bump de `pyproject.toml`, correr `uv lock` y commitear también **`uv.lock`** (registra
la versión del propio paquete; si no se regenera queda desincronizado — pasó en v1.1.0).

Luego: `git tag vX.Y.Z && git push origin vX.Y.Z`. El workflow `release.yml` construye el instalador y lo sube como **draft release**. El humano publica manualmente.

## Cadencia: release semanal

Releaseamos **una vez por semana** (típicamente el **viernes**). Durante la semana se mergean
branches pequeños; el bump de versión NO va en esos branches, sino en un branch de release que
los consolida.

**Durante la semana** (branches de feature/fix):

- **NO** tocar `pyproject.toml`, `ui/package.json` ni `desktop/package.json`.
- **NO** crear una sección con número de versión en el `CHANGELOG.md`.
- Las notas del cambio van bajo `## [Unreleased]` del `CHANGELOG.md`.
- Un cambio chico (p. ej. un copy) **no amerita** una versión propia.

**El viernes** (branch `release/vX.Y.Z`):

1. Decidir el bump con la tabla de arriba a partir del **agregado** de la semana (si hay al
   menos una feature → MINOR; si solo fixes/copy → PATCH; si algo rompe datos/`appId` → MAJOR).
2. **Sincronizar los 3 archivos** de versión al mismo `X.Y.Z` + `uv lock`.
3. En `CHANGELOG.md`: renombrar `## [Unreleased]` → `## [X.Y.Z] - <fecha>` y dejar un
   `## [Unreleased]` nuevo y vacío arriba.
4. PR → merge a `main`.
5. Etiquetar: `git tag vX.Y.Z && git push origin vX.Y.Z` (dispara el build/draft release).

> ~~Deuda: `pyproject.toml` quedó en `1.0.4` mientras `ui`/`desktop` van en `1.0.6`.~~
> Resuelto en v1.1.0 (2026-06-10): los 3 archivos quedaron sincronizados.

## Histórico

- Las versiones internas previas (v0.1.0–v1.2.0) corresponden al paquete pip-installable de Python y a metadatos de subproyectos desincronizados.
- **v1.0.0 (esta) inicia la numeración del producto distribuible TodoConta Desktop** (Python + Next + Electron empaquetado).
- A partir de aquí, todas las versiones referencian el producto unificado.

## Pre-releases (opcionales)

Para validar antes de publicar un release público:

- `vX.Y.Z-rc.N` — release candidate. Mismo build flow, pero el tag se elimina si surgen problemas y no se anuncia a usuarios.
- No usar `-alpha`, `-beta`, `-dev` salvo casos específicos documentados.

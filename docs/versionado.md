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

Luego: `git tag vX.Y.Z && git push origin vX.Y.Z`. El workflow `release.yml` (cuando esté implementado) construye el instalador y lo sube como **draft release**. El humano publica manualmente.

## Histórico

- Las versiones internas previas (v0.1.0–v1.2.0) corresponden al paquete pip-installable de Python y a metadatos de subproyectos desincronizados.
- **v1.0.0 (esta) inicia la numeración del producto distribuible TodoConta Desktop** (Python + Next + Electron empaquetado).
- A partir de aquí, todas las versiones referencian el producto unificado.

## Pre-releases (opcionales)

Para validar antes de publicar un release público:

- `vX.Y.Z-rc.N` — release candidate. Mismo build flow, pero el tag se elimina si surgen problemas y no se anuncia a usuarios.
- No usar `-alpha`, `-beta`, `-dev` salvo casos específicos documentados.

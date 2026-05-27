# TodoConta Desktop (Electron)

Shell de escritorio que envuelve el **agente Python** (FastAPI, `sat_descarga.api.server`)
y el **renderer** (`../ui/`, Next.js). Electron levanta el agente en un puerto efímero
local, espera a `/health`, abre la ventana y le inyecta al renderer el base URL del
agente vía el preload (`window.satAgent.baseUrl`).

```
[ Electron main ] ──spawn──> [ agente Python :puerto-efímero ]
        │                              ▲
        │ carga ui/ (Next)             │ HTTP (127.0.0.1)
        ▼                              │
[ BrowserWindow ] ── window.satAgent.baseUrl ──┘
```

## Correr en desarrollo

Requisitos: Node 18+, el repo con deps Python instaladas (`uv pip install -e ".[server,ciec]"`
y `playwright install chromium`), y `uv` disponible.

Usamos **pnpm** (no npm) en todo el repo, por seguridad: pnpm bloquea por defecto los
scripts de `postinstall` de las dependencias (vector común de ataques de cadena de
suministro). Electron necesita su `postinstall` para bajar su binario, así que está
explícitamente autorizado en `package.json` (`pnpm.onlyBuiltDependencies`).

```bash
# 1) Renderer (una terminal)
cd ui && pnpm install && pnpm dev          # Next dev en http://localhost:3001

# 2) Desktop (otra terminal)
cd desktop && pnpm install && pnpm dev      # Electron: spawnea el agente + abre la ventana
```

> Si la primera vez corriste `npm install` aquí, limpia antes de cambiar a pnpm:
> `rm -rf node_modules package-lock.json && pnpm install`.

Electron levanta el agente solo (`uv run uvicorn …` desde la raíz del repo). Si prefieres
levantarlo tú, expórtalo y Electron se conecta a ese:

```bash
SAT_AGENT_URL=http://127.0.0.1:8787 pnpm dev
```

### Overrides (env)
- `SAT_AGENT_URL` — usar un agente ya corriendo (no spawnea).
- `SAT_AGENT_CMD` — comando para levantar el agente (puerto en `SAT_AGENT_PORT`).
- `SAT_RENDERER_URL` — URL del renderer (default `http://localhost:3001`).

## Estado

MVP en construcción. Esto es un **dev build** (sin firmar). El empaquetado/instalador
firmado (PyInstaller del agente + electron-builder + notarización mac / Authenticode win)
viene después. La carpeta `design-ref/` (boceto de Claude Design) es referencia local y
no se versiona.

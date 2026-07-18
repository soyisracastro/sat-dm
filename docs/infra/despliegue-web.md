# Despliegue web — versión online espejo

La versión online lleva la misma app (mismo renderer, mismo agente) al navegador:
la UI de `ui/` se sirve desde Vercel en **app.todoconta.com** y el agente Python
corre en el VPS como **un contenedor Docker por usuario** bajo
**agente.todoconta.com**. La desktop no cambia: es el mismo codebase con otro
empaque.

> Filosofía de producto: como Notion — te logueas en la app de escritorio o en la
> web con la misma cuenta y sigues trabajando. **Desktop** si quieres que todo
> viva en tu computadora; **online** si quieres movilidad. El copy de la web debe
> transmitir que las credenciales viven cifradas en un espacio propio del usuario,
> nunca compartido — no que la web "es menos segura".

## Arquitectura

```
[navegador] ── https://app.todoconta.com  (Vercel, ui/ estático)
     │             └─ rewrites /api/*, /auth/*, /desktop/* → todoconta-apps legacy
     ├── https://agente.todoconta.com/provision/*  → provisioner (FastAPI + docker SDK)
     └── https://agente.todoconta.com/u/{slug}/*   → Traefik StripPrefix → agente-{slug}:8787
                                                       └─ volumen /data por usuario
```

- **Un contenedor por usuario** = el mismo aislamiento que hoy da la máquina del
  usuario en desktop, sin reescribir el agente a multi-tenant. La sesión FIEL en
  memoria, el catálogo JSON, los jobs y el poller funcionan tal cual.
- **Traefik** (ya corriendo en el VPS) enruta por path-prefix `/u/{slug}` con
  StripPrefix — un solo certificado Let's Encrypt para `agente.todoconta.com`,
  sin wildcard DNS.
- El **provisioner** resuelve el primer login (la auth de la UI normalmente pasa
  por el agente, pero en la web el navegador aún no conoce su agente): valida las
  credenciales contra Supabase, verifica la licencia, crea/arranca el contenedor
  del usuario y devuelve `{base_url, token, session}`. La UI guarda
  `{base_url, token}` y entrega la sesión al agente vía `POST /auth/adopt-session`.

## Modo hosted del agente (`SAT_DM_MODO=hosted`)

El agente detecta el modo por env (`core/config.py::es_modo_hosted`). Diferencias
frente al modo desktop:

| Comportamiento | Desktop | Hosted |
|---|---|---|
| Secretos (FIEL/CIEC/sesión) | Keychain del SO (`keyring`) | `secretos.enc` cifrado en el volumen |
| Carpeta de descargas | Documentos del usuario, configurable | `SAT_DM_DESCARGAS_DIR=/data/descargas` |
| `POST /abrir` | Abre carpeta/PDF en el SO | `501` — la UI usa `/descargas/*` |
| `GET /descargas/archivo\|zip` | Disponibles (sin uso en la UI) | El navegador descarga por aquí |
| `POST /auth/adopt-session` | `404` | Habilitado (sesión del provisioner) |
| CORS | `*` (solo escucha en loopback) | `SAT_DM_CORS_ORIGINS=https://app.todoconta.com` |
| Poller de solicitudes WS | Corre mientras la app está abierta | Corre 24/7 (descarga con el navegador cerrado) |

## Modelo de secretos

- En Docker no hay keychain. `core/secretos.py` despacha: si la env
  `SAT_DM_SECRETS_KEY` (32 bytes en base64) está presente, TODOS los secretos —
  contraseñas de e.firma, CIEC, CSD y la sesión de Supabase de `license_client` —
  van a `~/.sat-descarga/secretos.enc`: un JSON cifrado archivo-completo con
  **AES-256-GCM** (nonce fresco por escritura, escritura atómica con fsync).
- La clave la **deriva el provisioner por usuario** desde una master key
  (`SAT_DM_MASTER_KEY`, solo en el VPS): recrear el contenedor (p. ej. al
  actualizar la imagen) conserva el acceso a los secretos.
- ⚠️ **Rotar la master key invalida todos los `secretos.enc`**: los usuarios
  tendrían que recapturar sus contraseñas. Es una operación de último recurso.
- Tránsito: navegador → Traefik va por TLS (Let's Encrypt); Traefik → contenedor
  por la red interna de Docker del host. Mismo modelo de confianza que el
  loopback de la desktop.

### Trade-off aceptado (y cómo comunicarlo)

En la versión online la e.firma y su contraseña **sí viven en el servidor**
(cifradas, en el espacio del usuario). Es la condición de la movilidad y se
comunica así — nunca como equivalente a la promesa desktop ("tu e.firma no sale
de tu equipo"), que sigue siendo el diferenciador de la app instalada.

## Imagen del agente

`docker/agente/Dockerfile` (build y QA local: `docker/agente/README.md`):

- `python:3.12-slim` + `pip install ".[server,ciec]"`.
- Chromium horneado en `/ms-playwright` (`playwright install --with-deps chromium`);
  `portal/setup.py` respeta `PLAYWRIGHT_BROWSERS_PATH` externo y no lo toca.
- Usuario no-root (`agente`, uid 1000) con `HOME=/data` ⇒ todo el estado
  (`~/.sat-descarga`, descargas, `secretos.enc`) vive en el volumen `/data`.
- El Dockerfile de la raíz del repo es OTRA cosa (variante Railway de
  `api/hosted.py`, single-tenant con Supabase) — no confundir.

## Envs del contenedor (las inyecta el provisioner)

| Env | Qué es |
|---|---|
| `SAT_AGENT_TOKEN` | Token de auth del agente (header `X-Agent-Token` / `?token=`), derivado por usuario |
| `SAT_DM_SECRETS_KEY` | Clave AES-256 (base64) de `secretos.enc`, derivada por usuario |
| `SAT_DM_MODO` | `hosted` (ya viene en la imagen) |
| `SAT_DM_CORS_ORIGINS` | `https://app.todoconta.com` |
| `SAT_DM_DESCARGAS_DIR` | `/data/descargas` (ya viene en la imagen) |

## VPS: reglas de operación

El VPS es compartido — **también corre OpenClaw (agente de WhatsApp), FUERA de
Docker** (proceso node en loopback 18789/18791). Reglas duras:

1. Solo cambios **aditivos** (contenedores/redes/volúmenes nuevos). Nada bajo
   `/root/` ni procesos node. `/docker/traefik/` solo con respaldo previo.
2. **No rebootear** sin documentar antes cómo se supervisa OpenClaw.
3. RAM: presupuestar ~1.3 GB ya usados (OpenClaw+Traefik+SO) ⇒ ~13-16 agentes
   always-on en 8 GB. `mem_limit=1g` por contenedor.
4. Tras cada cambio: `pgrep -f openclaw` y `ss -tlnp | grep 1878` deben seguir vivos.

## Fases

El plan completo (F0 agente hosted → F1 piloto → F2 provisioner → F3 cutover de
dominio → F5 sync de catálogo → F4 limpieza), con QA por fase y riesgos, vive en
el plan de trabajo del proyecto. Este documento se irá completando con el runbook
del VPS (F2) y el procedimiento de cutover (F3).

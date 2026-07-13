# Runbook del VPS — versión online

VPS Hostinger (`root@187.77.152.160`, Ubuntu 24.04, Docker + Traefik). Arquitectura
completa: [docs/despliegue-web.md](../../docs/despliegue-web.md).

## ⚠️ Reglas del host (SIEMPRE)

En este VPS también vive **OpenClaw (agente de WhatsApp), FUERA de Docker**
(proceso node, loopback 18789/18791) y **Traefik** (compose en `/docker/traefik/`,
`network_mode: host`, resolver `letsencrypt`).

1. Cambios **solo aditivos**: contenedores/redes/volúmenes nuevos. Nada bajo
   `/root/`, ni procesos node, ni `/docker/traefik/` (salvo con respaldo previo).
2. **No rebootear** sin documentar antes cómo se supervisa OpenClaw.
3. Tras cada cambio: `pgrep -f openclaw` y `ss -tlnp | grep 1878` deben responder.
4. RAM disponible ≈ 6.5 GB para agentes (mem_limit 1g c/u) — vigilar `docker stats`.

## Piezas

| Pieza | Dónde | Qué es |
|---|---|---|
| Imagen del agente | `todoconta/agente:<tag>` | `docker/agente/Dockerfile` (repo) |
| Agente piloto (F1) | `/docker/agentes/` | `deploy/vps/docker-compose.piloto.yml` |
| Provisioner (F2) | `/docker/provisioner/` | `deploy/provisioner/` |
| Agentes por usuario | contenedores `agente-<slug>` | los crea el provisioner |

## Setup inicial (una vez)

```bash
# 1. DNS (Cloudflare): A record agente.todoconta.com → 187.77.152.160
#    ⚠️ DNS-only (nube GRIS): el proxy naranja corta el SSE de jobs largos.

# 2. Construir la imagen del agente (desde la máquina de dev):
git archive --format=tar <branch> | ssh root@187.77.152.160 \
  'docker build -f docker/agente/Dockerfile -t todoconta/agente:dev -'

# 3. Red compartida (si no existe):
docker network ls | grep agentes || docker network create agentes

# 4. Provisioner:
mkdir -p /docker/provisioner   # copiar deploy/provisioner/* aquí
cd /docker/provisioner
cat > .env <<EOF
SAT_DM_MASTER_KEY=$(python3 -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())")
AGENTE_IMAGEN=todoconta/agente:dev
# ALLOWLIST_EMAILS=correo1@x.mx,correo2@x.mx   # beta cerrada
# EXIGIR_LICENCIA=0                            # kill switch (beta)
# CORS_ORIGINS=https://app.todoconta.com,https://<preview>.vercel.app
EOF
chmod 600 .env
docker compose up -d --build
curl -s https://agente.todoconta.com/provision/health
```

## La master key (`SAT_DM_MASTER_KEY`)

De ella se derivan (HMAC por `user_id`): el slug del contenedor, el token del
agente y la clave AES de `secretos.enc` de cada usuario.

- **Respáldala** (password manager). Si se pierde el `.env`, con el respaldo
  todo se recupera.
- **NO la rotes** salvo compromiso: rotarla invalida los secretos de TODOS los
  usuarios (recapturarían contraseñas FIEL/CIEC). No hay re-cifrado automático.

## Actualizar la imagen de los agentes

```bash
# 1. Nueva imagen (tag nuevo o pisar :dev):
git archive --format=tar <branch> | ssh root@187.77.152.160 \
  'docker build -f docker/agente/Dockerfile -t todoconta/agente:dev -'

# 2. Recrear los agentes conservando volumen/env/labels:
./actualizar-agentes.sh            # (este directorio; ver --help)
```

Los volúmenes (`agente-datos-*`) y las claves derivadas no cambian, así que las
credenciales guardadas siguen legibles tras recrear el contenedor.

## Backups (ACTIVOS desde 2026-07-13)

Cron diario (`/etc/cron.d/todoconta-backups`, 09:00 UTC) ejecuta
`/docker/backups/respaldar-agentes.sh`: tar cifrado (AES-256, passphrase en
`/docker/backups/.backup-pass`) de los volúmenes `agente-datos-*` (FIELs,
descargas, secretos.enc), el registro del provisioner y los `.env` (master key
incluida) → `/backups/agentes-<fecha>.tar.gz.enc`. Retención 7 días; log y
alerta de disco ≥80 % en `/docker/backups/backups.log`.

- ⚠️ Respaldar **fuera del VPS** la passphrase (`.backup-pass`) y la master key
  (password manager): los backups viven en el mismo disco — cubren errores
  operativos, no la pérdida del disco. (Mejora futura: copia off-site/restic.)
- Restaurar: `openssl enc -d -aes-256-cbc -pbkdf2 -pass file:/docker/backups/.backup-pass < archivo.enc | tar xzf - -C /`

## Troubleshooting

- **502 en /u/{slug}**: `docker ps` — ¿el contenedor corre? `docker logs agente-<slug>`.
- **Cert no emitido**: el A record debe existir y estar en DNS-only; revisar
  logs de Traefik (`docker logs traefik-traefik-1 | grep -i acme`).
- **"Tu espacio está arrancando"** persistente: primer arranque descargando algo
  o contenedor en crash-loop → `docker logs agente-<slug>`.
- **SSE se corta en jobs largos**: revisar `respondingTimeouts` del entrypoint
  websecure de Traefik (editar su compose CON RESPALDO y `docker compose up -d`).
- **secretos.enc ilegible** ("¿cambió SAT_DM_SECRETS_KEY?"): la master key no
  corresponde — ¿se restauró un .env viejo?

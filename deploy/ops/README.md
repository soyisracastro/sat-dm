# deploy/ops — agentes operativos del ecosistema de ventas

Un solo contenedor ligero en el VPS (`/docker/ops/`) donde **supercronic** dispara
scripts Python transitorios (sin daemons; apto para las 2 CPU del VPS). Es la capa
de "departamentos" automatizados del plan de ventas jul–dic 2026:

| Agente | Estado | Qué hace |
|---|---|---|
| `agents/reporte_semanal.py` | ✅ | Lunes 07:00 CDMX: métricas de Supabase (usuarios/planes/CRM 034) + Stripe (suscripciones/ARR) + Sendy (listas) → deltas vs semana pasada → narrativa con Claude → correo SES a Israel. |
| `agents/contenido_semanal.py` | ⏳ siguiente | Borradores semanales (post de blog `draft:true`, guion de video, posts sociales, email) → PR `drafts/semana-NN` vía GitHub API. Nunca publica directo. |
| `agents/sdr_inbound.py` | ⏳ siguiente | Lee `crm_leads` etapa=lead (SOLO gente que llenó un formulario — opt-in), scoring, primer contacto por SES con BCC a Israel, límite diario + kill switch. |
| `agents/soporte.py` | ⏳ siguiente | Buzón soporte@ (Google Workspace): clasifica y redacta BORRADORES para aprobar; no auto-responde en v1. |

## Despliegue (patrón de deploy/{gateway,provisioner,sendy})

```bash
# 1. Copiar la carpeta al VPS (o git archive del branch):
scp -r deploy/ops root@187.77.152.160:/docker/ops
# 2. Crear /docker/ops/.env (chmod 600) — ver abajo.
# 3. Usuario MySQL de SOLO LECTURA en sendy-db (una vez):
docker exec -it sendy-db mariadb -uroot -p"$MARIADB_ROOT_PASSWORD" -e \
  "CREATE USER IF NOT EXISTS 'ops_ro'@'%' IDENTIFIED BY '<password>';
   GRANT SELECT ON sendy.* TO 'ops_ro'@'%'; FLUSH PRIVILEGES;"
# 4. Levantar:
cd /docker/ops && docker compose up -d --build
# 5. Probar sin mandar correo:
docker compose run --rm ops python agents/reporte_semanal.py --dry-run
```

## `.env` (chmod 600, NUNCA al repo)

```bash
# Kill switches (1 = encendido)
OPS_REPORTE_ENABLED=1

# Supabase (mismo proyecto que todoconta-apps; service role)
TODOCONTA_SUPABASE_URL=https://pyyyzvicjpffohwjsmzi.supabase.co
SUPABASE_SERVICE_KEY=

# Stripe — crear una RESTRICTED KEY de solo lectura (Developers → API keys →
# Create restricted key: Subscriptions/Customers/Charges en "Read"). NUNCA la
# secret key completa.
STRIPE_RESTRICTED_KEY=rk_live_...

# Sendy (MariaDB read-only, resuelto por la red sendy-internal)
SENDY_DB_HOST=sendy-db
SENDY_DB_USER=ops_ro
SENDY_DB_PASSWORD=
SENDY_DB_NAME=sendy

# SES (mismas credenciales que apps/web)
AWS_SES_REGION=us-east-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
REPORTE_FROM=no-reply@todoconta.com
REPORTE_TO=israel.castro@gmail.com

# Narrativa (opcional — sin key el reporte sale solo con números)
ANTHROPIC_API_KEY=
LLM_MODEL=claude-haiku-4-5-20251001
```

## Reglas del contenedor

- **Solo lectura hacia afuera**: Supabase con service key (los agentes futuros que
  escriban lo harán a `crm_*` únicamente), Stripe con restricted key RO, Sendy con
  usuario MySQL `SELECT`-only. Nada de docker.sock, nada de Traefik (sin inbound).
- **Sin daemons**: supercronic dispara procesos que terminan. `mem_limit: 256m`.
- **Cada agente con kill switch por env** y horarios escalonados en el crontab.
- **OpenClaw intocable**: este contenedor no toca nada de /root ni del host.
- El snapshot semanal (para deltas) vive en el volumen `ops-data` (`/data`).

## Verificación post-deploy

```bash
docker logs ops --tail 20              # supercronic cargó el crontab
docker compose run --rm ops python agents/reporte_semanal.py --dry-run
pgrep -f openclaw                      # checklist del host (runbook deploy/vps)
```

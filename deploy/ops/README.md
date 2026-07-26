# deploy/ops — agentes operativos del ecosistema de ventas

Un solo contenedor ligero en el VPS (`/docker/ops/`) donde **supercronic** dispara
scripts Python transitorios (sin daemons; apto para las 2 CPU del VPS). Es la capa
de "departamentos" automatizados del plan de ventas jul–dic 2026:

| Agente | Estado | Qué hace |
|---|---|---|
| `agents/reporte_semanal.py` | ✅ | Lunes 07:00 CDMX: métricas de Supabase (usuarios/planes/CRM 034) + Stripe (suscripciones/ARR) + Sendy (listas) → deltas vs semana pasada → narrativa con Claude → correo SES a Israel. |
| `agents/contenido_semanal.py` | ✅ | Lunes 06:30 CDMX: genera con Claude (Sonnet) el paquete semanal — post de blog con frontmatter listo, guion de video, 3 posts sociales, 1 email — y abre PR `drafts/semana-NN` en todoconta-apps. Los archivos viven en `drafts/`: **mergear tampoco publica**; Israel mueve el post al blog cuando lo aprueba. Fuente de temas: **el calendario editorial del repo** (`apps/landing/editorial/calendario-editorial-2026.csv`, leído en runtime — editarlo NO requiere redeploy; toma la fila más próxima con `publicado=no` y usa su brief/fuentes); backlog embebido solo como respaldo. |
| `agents/sdr_inbound.py` | ✅ | Cada hora (9:15–17:15 CDMX): lee `crm_leads` etapa=lead con fuente en `SDR_FUENTES` (SOLO gente que llenó un formulario — opt-in estricto; hoy solo `abacus`), puntúa y redacta con Claude **respondiendo a la intención real de la fuente** (abacus → ayudar a activar su prueba de WhatsApp; diagnostico → entregar el plan prometido), manda UN correo por SES como Israel (BCC a Israel), etapa→`mql` + evento `email_enviado` (candado anti-duplicado). Sin follow-ups: Israel cierra. |
| `agents/soporte.py` | ✅ | Cada hora: busca correos dirigidos a soporte@todoconta.com (que es un ALIAS dentro de la cuenta real de Israel — el agente entra por IMAP a esa cuenta pero SOLO procesa lo dirigido al alias, INBOX en readonly, banderas intactas), descarta auto-correos, clasifica y redacta BORRADOR con Claude, lo deja hilado en Borradores (sale como el alias) y avisa a Israel. Dedupe por Message-ID en `/data`. **No auto-responde a nadie** (v1). |
| `agents/sync_abacus_waitlist.py` | ⚪ | Diario 08:10 CDMX: lee la waitlist de Abacus en Notion y la registra en `crm_leads` (`fuente=abacus`, nombre, teléfono en E.164, etapa según el Estado de Notion sin retroceder). Cierra el hueco por el que 114 personas en Sendy nunca llegaron al CRM. Solo lee Notion y escribe `crm_*`: la allowlist de OpenClaw NO se toca. |

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
# 5. Probar sin efectos (ninguno manda nada en --dry-run):
docker compose run --rm ops python agents/reporte_semanal.py --dry-run
docker compose run --rm ops python agents/contenido_semanal.py --dry-run
docker compose run --rm ops python agents/sdr_inbound.py --dry-run
docker compose run --rm ops python agents/soporte.py --dry-run
```

## `.env` (chmod 600, NUNCA al repo)

```bash
# Kill switches (1 = encendido). SDR/soporte/contenido nacen APAGADOS:
# se encienden uno por uno cuando Israel valida su dry-run.
OPS_REPORTE_ENABLED=1
OPS_CONTENIDO_ENABLED=0
OPS_SDR_ENABLED=0
OPS_SOPORTE_ENABLED=0

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

# SES (mismas credenciales y nombres que apps/web)
AWS_SES_REGION=us-east-1
AWS_SES_ACCESS_KEY_ID=
AWS_SES_SECRET_ACCESS_KEY=
REPORTE_FROM=no-reply@todoconta.com
REPORTE_TO=israel.castro@gmail.com

# Claude (reporte/SDR/soporte usan LLM_MODEL; contenido usa Sonnet)
ANTHROPIC_API_KEY=
LLM_MODEL=claude-haiku-4-5-20251001
LLM_MODEL_CONTENIDO=claude-sonnet-5

# Contenido semanal — fine-grained PAT con Contents:write + Pull requests:write
# SOLO sobre el repo de contenido.
GITHUB_PAT=
CONTENIDO_REPO=soyisracastro/todoconta-apps

# heroImage automática (opcional — sin estas keys el PR sale sin imagen y la
# ficha trae el prompt para generarla a mano). Modelo económico a propósito
# (Nano Banana 2 Lite ~$0.03/imagen); TinyPNG comprime y convierte a JPG.
GEMINI_API_KEY=
GEMINI_IMAGE_MODEL=gemini-3.1-flash-lite-image
TINYPNG_API_KEY=

# SDR inbound
SDR_FROM="Israel Castro <israel@todoconta.com>"
SDR_BCC=israel.castro@gmail.com
OPS_SDR_MAX_DIA=5        # tope de correos por día
SDR_MAX_EDAD_DIAS=14     # no contactar leads más viejos que esto
# Fuentes de crm_leads que el SDR puede contactar (coma-separadas). Solo
# abacus por ahora (qualifier = campaña saldo a favor pausada, fuera del ICP;
# se retomaría en sicastro.com). Al lanzar /diagnostico: "abacus,diagnostico".
SDR_FUENTES=abacus

# Waitlist de Abacus (Notion → CRM). El token es el MISMO que usa el script de
# OpenClaw (workspace-personal/abacus/secrets/notion.env): copiarlo aquí.
OPS_WAITLIST_ENABLED=0
NOTION_API_KEY=
# NOTION_ABACUS_DB_ID=   # solo si cambia la base (default en el agente)

# Soporte (Google Workspace). soporte@todoconta.com es un ALIAS que entrega en
# la cuenta real (@sicastro.com): el login IMAP va con la CUENTA REAL y su app
# password (myaccount.google.com → Seguridad → Verificación en 2 pasos →
# Contraseñas de aplicaciones); el agente solo procesa lo dirigido al alias.
SOPORTE_IMAP_HOST=imap.gmail.com
SOPORTE_EMAIL=israel@sicastro.com        # cuenta real (login IMAP)
SOPORTE_APP_PASSWORD=                    # app password de ESA cuenta
SOPORTE_ALIAS=soporte@todoconta.com      # dirección que filtra y desde la que responde
SOPORTE_VENTANA_DIAS=2   # qué tan atrás busca (no barre correo viejo al encender)
OPS_SOPORTE_MAX=10       # mensajes por corrida
```

## Reglas del contenedor

- **Escritura mínima y acotada**: Supabase solo a tablas `crm_*` (SDR); GitHub
  solo PRs de borradores con PAT fine-grained (contenido); Gmail solo APPEND a
  la carpeta Borradores — INBOX se abre readonly y las banderas de leído son de
  Israel, no del agente (soporte). Stripe con restricted key RO, Sendy con
  usuario MySQL `SELECT`-only. Nada de docker.sock, nada de Traefik (sin inbound).
- **Nadie recibe correo sin humano o sin opt-in**: el SDR solo escribe a quien
  llenó un formulario (una sola vez, con BCC a Israel); soporte solo deja
  borradores. Los envíos masivos siguen siendo territorio de Sendy.
- **Sin daemons**: supercronic dispara procesos que terminan. `mem_limit: 256m`.
- **Cada agente con kill switch por env** (SDR/soporte/contenido nacen apagados)
  y horarios escalonados en el crontab. Todos aceptan `--dry-run`.
- **OpenClaw intocable**: este contenedor no toca nada de /root ni del host.
- El estado de cada agente (snapshots, candados diarios, procesados) vive en el
  volumen `ops-data` (`/data`).

## Verificación post-deploy

```bash
docker logs ops --tail 20              # supercronic cargó el crontab
docker compose run --rm ops python agents/reporte_semanal.py --dry-run
docker compose run --rm ops python agents/contenido_semanal.py --dry-run   # imprime el paquete, sin PR
docker compose run --rm ops python agents/sdr_inbound.py --dry-run         # imprime correos, sin mandar
docker compose run --rm ops python agents/soporte.py --dry-run             # imprime clasificación, sin tocar el buzón
pgrep -f openclaw                      # checklist del host (runbook deploy/vps)
```

Secuencia de encendido sugerida: validar cada dry-run → `OPS_CONTENIDO_ENABLED=1`
(el PR es inofensivo) → `OPS_SOPORTE_ENABLED=1` (solo borradores) →
`OPS_SDR_ENABLED=1` al final (este sí manda correo a leads; empezar con
`OPS_SDR_MAX_DIA=2` y subir cuando el tono esté validado).

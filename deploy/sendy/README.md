# Sendy en el VPS — migración desde SiteGround

Mueve el envío de correos (newsletter, autoresponders) de SiteGround (~25-29 USD/mes)
al VPS que ya pagamos, corriendo **Sendy** (licencia única que ya tienes) detrás de
Traefik y enviando por **Amazon SES** (~$0.10 por 1000 correos). Reglas del host y
recursos: [../vps/README.md](../vps/README.md).

Sendy es **software licenciado**: su código (`./app/`) NO vive en el repo — se sube por
scp desde SiteGround. Aquí van solo la infra (Dockerfile + compose) y este runbook.

## Arquitectura

```
newsletter del blog / panel Sendy
        │  https://sendy.todoconta.com
        ▼
   [Traefik] ── red `agentes` ──► [sendy: php:8.2-apache] ──► [sendy-db: mariadb]
                                          │                     (red interna)
                                          └──► Amazon SES (envío real)
   [sendy-cron] ── scheduled.php cada 60s (envíos programados, bounces)
```

## Migración — paso a paso

### A. En SiteGround (lo haces tú — yo no tengo acceso ahí)

1. **Exporta la base de datos de Sendy** (phpMyAdmin → Export → SQL, o por SSH
   `mysqldump -u USER -p BASE > sendy.sql`). Ese dump trae listas, suscriptores,
   campañas **y** las credenciales de SES guardadas.
2. **Descarga el directorio completo de Sendy** (File Manager o SFTP). Importa sobre
   todo: `includes/config.php` (credenciales + APP_PATH actuales), `uploads/`
   (imágenes de campañas) y `includes/` completo.
3. **Anota** de `config.php`: `$dbhost/$dbuser/$dbpass/$dbname` y `APP_PATH` actuales
   (para comparar y por si algo falla).
4. **NO canceles SiteGround todavía** — hasta validar el VPS (paso D).

### B. En el VPS (esto lo automatizamos)

1. **DNS** (Cloudflare): A record `sendy.todoconta.com` → `187.77.152.160`, **DNS-only
   (nube gris)**.
2. **Sube la infra y el código**:
   ```bash
   # infra (desde la máquina de dev)
   scp deploy/sendy/{Dockerfile,docker-compose.yml} root@187.77.152.160:/docker/sendy/
   # código de Sendy descargado de SiteGround
   scp -r ./sendy-de-siteground/* root@187.77.152.160:/docker/sendy/app/
   # el dump de la DB
   scp sendy.sql root@187.77.152.160:/docker/sendy/
   ```
3. **`.env`** (en `/docker/sendy/`, contraseñas nuevas de la DB — nada que ver con las
   de SiteGround):
   ```bash
   cat > /docker/sendy/.env <<EOF
   SENDY_DB_NAME=sendy
   SENDY_DB_USER=sendy
   SENDY_DB_PASSWORD=$(openssl rand -base64 24)
   SENDY_DB_ROOT_PASSWORD=$(openssl rand -base64 24)
   EOF
   chmod 600 /docker/sendy/.env
   ```
4. **Edita `/docker/sendy/app/includes/config.php`** para apuntar a la DB nueva y al
   dominio nuevo:
   ```php
   define('APP_PATH', 'https://sendy.todoconta.com');
   $dbhost = 'sendy-db';        // el nombre del servicio del compose
   $dbuser = 'sendy';           // = SENDY_DB_USER
   $dbpass = '…';               // = SENDY_DB_PASSWORD del .env
   $dbname = 'sendy';           // = SENDY_DB_NAME
   ```
5. **Arranca**:
   ```bash
   cd /docker/sendy && docker compose up -d --build
   ```
6. **Importa el dump** (cuando la DB esté healthy):
   ```bash
   docker exec -i sendy-db mariadb -u root -p"$(grep ROOT_PASSWORD .env | cut -d= -f2)" sendy < sendy.sql
   ```
7. **Verifica**: `curl -I https://sendy.todoconta.com` (cert LE emitido) → entra al panel
   con tu usuario de siempre (viajó en el dump).

### C. Verificación funcional (antes del cutover)

- **Login** al panel de Sendy en `sendy.todoconta.com`.
- **SES**: Settings → confirma que las credenciales/región de Amazon SES están
  (vinieron en el dump); manda una **campaña de prueba** a tu propio correo.
- **Cron**: `docker logs sendy-cron` sin errores; los envíos programados avanzan.
- **Suscribir/desuscribir**: prueba el flujo con un correo de prueba.

### D. Cutover

1. **Actualiza el `PUBLIC_SENDY_ACTION_URL`** en Vercel — proyecto **landing** (y web si
   aplica): apúntalo a `https://sendy.todoconta.com`. Redeploy. El widget de newsletter
   del blog (`NewsletterWidget.astro` / `NewsletterModal.astro`) usa esa env.
2. Prueba el **alta desde el blog** end-to-end (formulario → aparece en la lista de Sendy).
3. **Recién entonces** da de baja el plan de SiteGround.

## ⚠️ Puntos delicados

- **Links de correos YA enviados**: los correos que salieron desde SiteGround tienen sus
  links de tracking/unsubscribe apuntando al **dominio viejo**. Si apagas SiteGround, esos
  links se rompen (unsubscribe/opens de campañas pasadas). Mitigación: deja el dominio
  viejo redirigiendo a `sendy.todoconta.com` un tiempo, o acepta perder tracking histórico
  (los suscriptores nuevos y las campañas nuevas ya usan el dominio nuevo).
- **Licencia de Sendy**: al cambiar de dominio puede pedir re-verificar la licencia en el
  panel (Settings). Ten a mano tu clave de licencia.
- **SES sandbox / reputación**: la IP de envío es de **Amazon**, no del VPS, así que la
  reputación de la IP del VPS no aplica. Verifica que el dominio siga con **SPF + DKIM**
  configurados en SES (probablemente ya lo estaban en SiteGround; no cambian al mover Sendy).
- **Backups**: la DB de Sendy vive en el volumen `sendy-db-data`. Agrégalo al backup del
  VPS (o un `mysqldump` periódico) — ver [../vps/README.md](../vps/README.md).

## Operación

- **Logs**: `docker logs sendy` / `docker logs sendy-cron` / `docker logs sendy-db`.
- **Reiniciar**: `cd /docker/sendy && docker compose restart`.
- **Backup manual de la DB**:
  `docker exec sendy-db mariadb-dump -u root -p"$ROOT" sendy > sendy-$(date +%F).sql`
- **Recursos**: ~1 GB entre los tres contenedores; el VPS tiene ~6 GB libres (holgado).

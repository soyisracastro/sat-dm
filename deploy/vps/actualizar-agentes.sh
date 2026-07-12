#!/usr/bin/env bash
# Recrea los contenedores de agentes (agente-<slug>) con una imagen nueva,
# conservando volumen, envs y labels — las claves derivadas no cambian, así que
# secretos.enc sigue legible. Correr EN EL VPS.
#
# Uso:
#   ./actualizar-agentes.sh [imagen]     # default: todoconta/agente:dev
#
# Solo toca contenedores con el label todoconta.agente=1 (los del provisioner).
# El piloto (docker-compose.piloto.yml) se actualiza con su propio compose.
set -euo pipefail

IMAGEN="${1:-todoconta/agente:dev}"
DOMINIO="${DOMINIO:-agente.todoconta.com}"
RED="${RED:-agentes}"

contenedores=$(docker ps -a --filter "label=todoconta.agente=1" --format '{{.Names}}')
if [ -z "$contenedores" ]; then
  echo "No hay agentes que actualizar (label todoconta.agente=1)."
  exit 0
fi

for c in $contenedores; do
  slug="${c#agente-}"
  echo "→ $c (slug $slug)"

  env_de() { docker inspect "$c" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep "^$1=" | cut -d= -f2- || true; }
  TOKEN=$(env_de SAT_AGENT_TOKEN)
  KEY=$(env_de SAT_DM_SECRETS_KEY)
  CORS=$(env_de SAT_DM_CORS_ORIGINS)

  if [ -z "$TOKEN" ] || [ -z "$KEY" ]; then
    echo "  ✗ sin envs esperadas; lo salto (revisar a mano)"
    continue
  fi

  docker rm -f "$c" >/dev/null

  docker run -d --name "$c" \
    --network "$RED" \
    --restart unless-stopped \
    --memory 1g \
    --log-opt max-size=10m --log-opt max-file=3 \
    -v "agente-datos-$slug:/data" \
    -e "SAT_AGENT_TOKEN=$TOKEN" \
    -e "SAT_DM_SECRETS_KEY=$KEY" \
    -e "SAT_DM_CORS_ORIGINS=$CORS" \
    -l "traefik.enable=true" \
    -l "traefik.http.routers.$c.rule=Host(\`$DOMINIO\`) && PathPrefix(\`/u/$slug\`)" \
    -l "traefik.http.routers.$c.entrypoints=websecure" \
    -l "traefik.http.routers.$c.tls.certresolver=letsencrypt" \
    -l "traefik.http.middlewares.$c-strip.stripprefix.prefixes=/u/$slug" \
    -l "traefik.http.routers.$c.middlewares=$c-strip" \
    -l "traefik.http.services.$c.loadbalancer.server.port=8787" \
    -l "traefik.docker.network=$RED" \
    -l "todoconta.agente=1" \
    "$IMAGEN" >/dev/null

  echo "  ✓ recreado con $IMAGEN"
done

echo
echo "Verificación post-cambio del host:"
pgrep -f openclaw >/dev/null && echo "  openclaw: OK" || echo "  openclaw: ⚠️ NO CORRE"
docker ps --filter "label=todoconta.agente=1" --format '  {{.Names}}: {{.Status}}'

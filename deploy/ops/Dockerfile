# Contenedor de operaciones (agentes programados del ecosistema de ventas).
# Un solo contenedor ligero: supercronic dispara scripts Python transitorios
# (sin daemons — apto para el VPS de 2 CPU). Ver README.md de esta carpeta.

FROM python:3.12-slim

# supercronic: cron para contenedores (corre como no-root, loguea a stdout).
ARG SUPERCRONIC_VERSION=v0.2.34
ADD https://github.com/aptible/supercronic/releases/download/${SUPERCRONIC_VERSION}/supercronic-linux-amd64 /usr/local/bin/supercronic
RUN chmod +x /usr/local/bin/supercronic

RUN pip install --no-cache-dir requests pymysql boto3 anthropic

WORKDIR /app
COPY crontab ./crontab
COPY lib ./lib
COPY agents ./agents

# Los snapshots semanales (para deltas) viven en el volumen /data.
RUN mkdir -p /data

ENV PYTHONPATH=/app PYTHONUNBUFFERED=1

CMD ["supercronic", "-passthrough-logs", "/app/crontab"]

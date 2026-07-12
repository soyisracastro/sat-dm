# Provisioner de la versión online (agente.todoconta.com/provision/*).
# Corre como root porque necesita el socket de Docker para crear los
# contenedores de los agentes. Ver deploy/vps/README.md.
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0" "requests>=2.31.0" "docker>=7.0.0"

COPY main.py .

EXPOSE 8790
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8790/provision/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8790"]

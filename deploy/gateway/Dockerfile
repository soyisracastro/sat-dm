# Gateway de la API pública + servidor MCP. Corre como root (necesita el
# socket de Docker para encender agentes). Ver deploy/vps/README.md.
FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir \
    "fastapi>=0.104.0" "uvicorn[standard]>=0.24.0" "requests>=2.31.0" \
    "docker>=7.0.0" "mcp>=1.2.0"

COPY main.py .

EXPOSE 8795
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8795/v1/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8795"]

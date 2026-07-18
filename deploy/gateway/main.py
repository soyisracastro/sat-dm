"""
Gateway de la API pública y el servidor MCP (api.todoconta.com / agente.todoconta.com).

Da los servicios de TodoConta a integradores (REST v1) y a LLMs (MCP,
Streamable HTTP) SIN pasar por la UI: valida la API key contra Supabase
(solo el hash vive ahí), deriva el agente personal del usuario (misma master
key que el provisioner), lo enciende si hace falta y le rutea las operaciones.
Los documentos salen del espacio privado del usuario; la base de datos
compartida solo conoce hashes de keys y metadata.

Diseño completo: docs/infra/api-publica.md. Emisión de keys: emitir-key.py.
"""

from __future__ import annotations

import base64
import contextvars
from contextlib import asynccontextmanager
import hashlib
import hmac
import logging
import os
import threading
import time
from typing import Optional

import requests
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("gateway")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

SUPABASE_URL = os.environ.get("TODOCONTA_SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", "")
AGENTE_IMAGEN = os.environ.get("AGENTE_IMAGEN", "todoconta/agente:dev")
PUBLIC_BASE = os.environ.get("PUBLIC_BASE", "https://agente.todoconta.com").rstrip("/")
DOMINIO = PUBLIC_BASE.split("://", 1)[-1]
RED_AGENTES = os.environ.get("RED_AGENTES", "agentes")
CORS_WEB = os.environ.get("CORS_ORIGINS", "https://app.todoconta.com")

_TIMEOUT = 30
_TIMEOUT_DOCUMENTO = 240  # portal del SAT: la CSF/32-D puede tardar ~1-2 min


def _master_key() -> bytes:
    raw = os.environ.get("SAT_DM_MASTER_KEY", "")
    if not raw:
        raise RuntimeError("SAT_DM_MASTER_KEY no está configurada")
    return base64.b64decode(raw)


# ---------------------------------------------------------------------------
# API keys (Supabase; solo hashes) + rate limit
# ---------------------------------------------------------------------------

# Cache corto de validación: {hash: (expira, user_id, scopes)}
_keys_cache: dict = {}
_cache_lock = threading.Lock()
_CACHE_S = 60

# Rate limit por key: {hash: [timestamps]}
_rate: dict = {}
_RATE_MAX = 120
_RATE_VENTANA_S = 300

# Contexto del request autenticado (lo usan las tools MCP).
ctx_user: contextvars.ContextVar[Optional[dict]] = contextvars.ContextVar(
    "ctx_user", default=None
)


def _validar_key(api_key: str) -> dict:
    """Devuelve {user_id, scopes} o lanza HTTPException 401/429."""
    if not api_key or not api_key.startswith("tc_"):
        raise HTTPException(status_code=401, detail="API key inválida o ausente.")
    h = hashlib.sha256(api_key.encode()).hexdigest()

    ahora = time.monotonic()
    with _cache_lock:
        marcas = [t for t in _rate.get(h, []) if ahora - t < _RATE_VENTANA_S]
        if len(marcas) >= _RATE_MAX:
            raise HTTPException(status_code=429, detail="Límite de peticiones alcanzado. Espera unos minutos.")
        marcas.append(ahora)
        _rate[h] = marcas

        cacheada = _keys_cache.get(h)
        if cacheada and cacheada[0] > ahora:
            return {"user_id": cacheada[1], "scopes": cacheada[2]}

    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/api_keys",
            params={
                "key_hash": f"eq.{h}",
                "revocada_en": "is.null",
                "select": "user_id,scopes",
            },
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="No se pudo validar la API key. Intenta más tarde.")
    filas = resp.json() if resp.status_code == 200 else []
    if not filas:
        raise HTTPException(status_code=401, detail="API key inválida o revocada.")
    user = {"user_id": filas[0]["user_id"], "scopes": filas[0].get("scopes") or []}
    with _cache_lock:
        _keys_cache[h] = (ahora + _CACHE_S, user["user_id"], user["scopes"])
    # Marca de uso (best-effort, sin bloquear).
    threading.Thread(
        target=lambda: requests.patch(
            f"{SUPABASE_URL}/rest/v1/api_keys",
            params={"key_hash": f"eq.{h}"},
            json={"ultima_vez_usada": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            timeout=10,
        ),
        daemon=True,
    ).start()
    return user


def _exigir_scope(user: dict, scope: str) -> None:
    if scope not in user["scopes"]:
        raise HTTPException(status_code=403, detail=f"Tu API key no tiene el permiso `{scope}`.")


# ---------------------------------------------------------------------------
# Agente del usuario (espejo de deploy/provisioner/main.py — misma derivación)
# ---------------------------------------------------------------------------

_docker_lock = threading.Lock()


def _derivar(user_id: str) -> dict:
    master = _master_key()

    def _h(etiqueta: str) -> bytes:
        return hmac.new(master, f"{etiqueta}:{user_id}".encode(), hashlib.sha256).digest()

    return {
        "slug": _h("slug").hex()[:12],
        "token": _h("token").hex(),
        "secrets_key": base64.b64encode(_h("secretos")).decode(),
    }


def _asegurar_agente(user_id: str) -> tuple[str, dict]:
    """Devuelve (base_url_interna, headers) del agente del usuario, encendiéndolo si hace falta."""
    import docker as docker_sdk

    d = _derivar(user_id)
    slug = d["slug"]
    nombre = f"agente-{slug}"

    with _docker_lock:
        cli = docker_sdk.from_env()
        try:
            cli.networks.get(RED_AGENTES)
        except docker_sdk.errors.NotFound:
            cli.networks.create(RED_AGENTES, driver="bridge")
        try:
            cli.volumes.get(f"agente-datos-{slug}")
        except docker_sdk.errors.NotFound:
            cli.volumes.create(f"agente-datos-{slug}")
        try:
            cont = cli.containers.get(nombre)
            if cont.status != "running":
                cont.start()
        except docker_sdk.errors.NotFound:
            r = f"agente-{slug}"
            cli.containers.run(
                AGENTE_IMAGEN,
                name=nombre,
                detach=True,
                network=RED_AGENTES,
                mem_limit="1g",
                restart_policy={"Name": "unless-stopped"},
                volumes={f"agente-datos-{slug}": {"bind": "/data", "mode": "rw"}},
                environment={
                    "SAT_AGENT_TOKEN": d["token"],
                    "SAT_DM_SECRETS_KEY": d["secrets_key"],
                    "SAT_DM_CORS_ORIGINS": CORS_WEB,
                },
                labels={
                    "traefik.enable": "true",
                    f"traefik.http.routers.{r}.rule": f"Host(`{DOMINIO}`) && PathPrefix(`/u/{slug}`)",
                    f"traefik.http.routers.{r}.entrypoints": "websecure",
                    f"traefik.http.routers.{r}.tls.certresolver": "letsencrypt",
                    f"traefik.http.middlewares.{r}-strip.stripprefix.prefixes": f"/u/{slug}",
                    f"traefik.http.routers.{r}.middlewares": f"{r}-strip",
                    f"traefik.http.services.{r}.loadbalancer.server.port": "8787",
                    "traefik.docker.network": RED_AGENTES,
                    "todoconta.agente": "1",
                },
                log_config={"type": "json-file", "config": {"max-size": "10m", "max-file": "3"}},
            )
            logger.info("contenedor %s creado", nombre)

    base = f"http://{nombre}:8787"
    headers = {"X-Agent-Token": d["token"]}
    limite = time.monotonic() + 45
    while time.monotonic() < limite:
        try:
            if requests.get(f"{base}/health", headers=headers, timeout=3).status_code == 200:
                return base, headers
        except requests.RequestException:
            pass
        time.sleep(1.5)
    raise HTTPException(status_code=503, detail="El espacio del usuario está arrancando; reintenta en unos segundos.")


def _agente_de(user: dict) -> tuple[str, dict]:
    return _asegurar_agente(user["user_id"])


def _activar_empresa(base: str, headers: dict, rfc: str) -> dict:
    r = requests.post(f"{base}/empresas/{rfc}/activar", headers=headers, timeout=60)
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail=f"La empresa {rfc} no existe en el espacio del usuario.")
    if r.status_code != 200:
        detalle = _detalle(r)
        raise HTTPException(status_code=409, detail=detalle or f"No se pudo activar la empresa {rfc}.")
    try:
        return r.json()  # {ok, rfc, metodos, efirma_lista}
    except ValueError:
        return {}


def _csf_archivada(base: str, headers: dict, rfc: str) -> tuple[Optional[str], Optional[str]]:
    """Última CSF en archivo según el catálogo del agente → (ruta, fecha) o (None, None)."""
    try:
        r = requests.get(f"{base}/empresas", headers=headers, timeout=_TIMEOUT)
        if r.status_code != 200:
            return None, None
        for e in r.json().get("empresas", []):
            if e.get("rfc") == rfc:
                return e.get("csf_path") or None, e.get("csf_descargada_en") or None
    except requests.RequestException:
        pass
    return None, None


def _detalle(r: requests.Response) -> Optional[str]:
    try:
        return r.json().get("detail")
    except ValueError:
        return None


def _descargar_de_agente(base: str, headers: dict, ruta: str, zip_: bool) -> Response:
    endpoint = "zip" if zip_ else "archivo"
    r = requests.get(
        f"{base}/descargas/{endpoint}",
        params={"ruta": ruta},
        headers=headers,
        timeout=_TIMEOUT_DOCUMENTO,
        stream=True,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=_detalle(r) or "No se pudo obtener el archivo.")
    media = r.headers.get("content-type", "application/octet-stream")
    disp = r.headers.get("content-disposition", "attachment")
    return StreamingResponse(r.iter_content(chunk_size=65536), media_type=media, headers={"Content-Disposition": disp})


# ---------------------------------------------------------------------------
# App REST v1
# ---------------------------------------------------------------------------

app = FastAPI(title="TodoConta — API pública", docs_url=None, redoc_url=None)


def _auth(x_api_key: Optional[str], authorization: Optional[str]) -> dict:
    key = x_api_key or ""
    if not key and authorization and authorization.lower().startswith("bearer "):
        key = authorization[7:].strip()
    user = _validar_key(key)
    ctx_user.set(user)
    return user


class SolicitudCfdiRequest(BaseModel):
    rfc: str
    fecha_inicio: str
    fecha_fin: str
    tipo_comprobante: str = "E"  # E emitidos | R recibidos
    tipo_solicitud: str = "CFDI"  # CFDI | Metadata


class RfcRequest(BaseModel):
    rfc: str


@app.get("/v1/health")
def health():
    return {"status": "ok", "servicio": "gateway"}


@app.get("/v1/empresas")
def v1_empresas(x_api_key: str = Header(None), authorization: str = Header(None)):
    """Catálogo del espacio del usuario (metadata; nunca credenciales ni rutas)."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "documentos:leer")
    base, headers = _agente_de(user)
    r = requests.get(f"{base}/empresas", headers=headers, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="No se pudo leer el catálogo.")
    empresas = [
        {k: e.get(k) for k in ("rfc", "nombre", "metodos", "vencimiento", "archived_at")}
        for e in r.json().get("empresas", [])
    ]
    return {"empresas": empresas}


def _documento(user: dict, rfc: str, endpoint: str, nombre_doc: str, fallback_archivo: bool = False) -> Response:
    _exigir_scope(user, "documentos:leer")
    rfc = rfc.strip().upper()
    base, headers = _agente_de(user)

    def _entregar_archivada(motivo: str) -> Optional[Response]:
        ruta, fecha = _csf_archivada(base, headers, rfc)
        if not ruta:
            return None
        try:
            resp = _descargar_de_agente(base, headers, ruta, zip_=False)
        except HTTPException:
            return None  # archivo ilegible/fuera de lista blanca → seguir al error claro
        resp.headers["X-Documento-Origen"] = "archivo"
        resp.headers["X-Documento-Motivo"] = motivo
        if fecha:
            resp.headers["X-Documento-Fecha"] = fecha
        return resp

    try:
        activacion = _activar_empresa(base, headers, rfc)
    except HTTPException as exc:
        # e.firma cargada pero inutilizable (contraseña/vigencia/cert): con
        # fallback intenta la copia en archivo; 404 (empresa no existe) sí pasa.
        if fallback_archivo and exc.status_code == 409:
            resp = _entregar_archivada("efirma-invalida")
            if resp is not None:
                return resp
        raise

    # La generación al momento requiere e.firma; la opinión 32-D NO tiene
    # fallback a archivo (es una foto de cumplimiento puntual — una vieja engaña).
    sin_fiel = "fiel" not in (activacion.get("metodos") or []) or not activacion.get("efirma_lista")

    if sin_fiel:
        if fallback_archivo:
            resp = _entregar_archivada("sin-efirma")
            if resp is not None:
                return resp
        raise HTTPException(
            status_code=409,
            detail=(
                f"La empresa {rfc} no tiene e.firma cargada en TodoConta, así que la {nombre_doc} "
                "no se puede generar al momento. Carga su e.firma (TodoConta Desktop → Empresas) "
                "y vuelve a intentarlo."
            ),
        )

    r = requests.post(f"{base}/{endpoint}", headers=headers, json={}, timeout=_TIMEOUT_DOCUMENTO)
    if r.status_code != 200:
        if fallback_archivo:
            resp = _entregar_archivada("sat-fallo")
            if resp is not None:
                return resp
        raise HTTPException(status_code=502, detail=_detalle(r) or f"No se pudo descargar la {nombre_doc}.")
    ruta = r.json().get("path") or r.json().get("ruta")
    if not ruta:
        raise HTTPException(status_code=502, detail=f"El agente no reportó la ruta de la {nombre_doc}.")
    return _descargar_de_agente(base, headers, ruta, zip_=False)


@app.post("/v1/csf")
def v1_csf(req: RfcRequest, x_api_key: str = Header(None), authorization: str = Header(None)):
    """
    Descarga la Constancia de Situación Fiscal (PDF) de la empresa.

    Sin e.firma cargada (o con el SAT caído) entrega la última CSF en archivo del
    catálogo, marcada con X-Documento-Origen: archivo + X-Documento-Fecha.
    """
    return _documento(_auth(x_api_key, authorization), req.rfc, "constancia/fiel", "constancia", fallback_archivo=True)


@app.post("/v1/opinion")
def v1_opinion(req: RfcRequest, x_api_key: str = Header(None), authorization: str = Header(None)):
    """Descarga la Opinión de Cumplimiento 32-D (PDF) de la empresa."""
    return _documento(_auth(x_api_key, authorization), req.rfc, "opinion/fiel", "opinión 32-D")


@app.post("/v1/cfdi/solicitudes")
def v1_solicitar(req: SolicitudCfdiRequest, x_api_key: str = Header(None), authorization: str = Header(None)):
    """Crea una solicitud de descarga masiva WS. El poller del espacio la resuelve solo."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "cfdi:solicitar")
    rfc = req.rfc.strip().upper()
    base, headers = _agente_de(user)
    _activar_empresa(base, headers, rfc)
    r = requests.post(
        f"{base}/solicitar",
        headers=headers,
        json={
            "fecha_inicio": req.fecha_inicio,
            "fecha_fin": req.fecha_fin,
            "tipo_comprobante": req.tipo_comprobante,
            "tipo_solicitud": req.tipo_solicitud,
        },
        timeout=120,
    )
    if r.status_code == 503:
        raise HTTPException(status_code=503, detail=_detalle(r) or "El SAT no está disponible; reintenta.")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=_detalle(r) or "El SAT rechazó la solicitud.")
    return {"rfc": rfc, **r.json()}


@app.get("/v1/cfdi/solicitudes/{rfc}/{id_solicitud}")
def v1_estado_solicitud(rfc: str, id_solicitud: str, x_api_key: str = Header(None), authorization: str = Header(None)):
    """Estado de una solicitud (el poller del espacio descarga solo al estar lista)."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "cfdi:solicitar")
    rfc = rfc.strip().upper()
    base, headers = _agente_de(user)
    r = requests.get(f"{base}/empresas/{rfc}/solicitudes", headers=headers, timeout=_TIMEOUT)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="No se pudieron leer las solicitudes.")
    for s in r.json().get("solicitudes", []):
        if s.get("id_solicitud") == id_solicitud:
            return s
    raise HTTPException(status_code=404, detail="Solicitud no encontrada.")


@app.get("/v1/cfdi/solicitudes/{rfc}/{id_solicitud}/zip")
def v1_zip_solicitud(rfc: str, id_solicitud: str, x_api_key: str = Header(None), authorization: str = Header(None)):
    """ZIP con los XML de una solicitud ya descargada por el espacio."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "cfdi:solicitar")
    rfc = rfc.strip().upper()
    base, headers = _agente_de(user)
    r = requests.get(f"{base}/empresas/{rfc}/solicitudes", headers=headers, timeout=_TIMEOUT)
    ruta = None
    for s in (r.json().get("solicitudes", []) if r.status_code == 200 else []):
        if s.get("id_solicitud") == id_solicitud:
            ruta = s.get("ruta_descarga") or s.get("ruta")
            estado = s
            break
    else:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada.")
    if not ruta:
        raise HTTPException(
            status_code=409,
            detail="La solicitud aún no está descargada; consulta su estado y reintenta.",
        )
    return _descargar_de_agente(base, headers, ruta, zip_=True)


class ProcesarRequest(BaseModel):
    rfc: str
    desde: Optional[str] = None   # YYYY-MM-DD
    hasta: Optional[str] = None
    tipo: Optional[str] = None    # E emitidos | R recibidos | None ambos


def _params_filtros(rfc: str, desde, hasta, direccion) -> dict:
    params = {"rfc": rfc.strip().upper()}
    if desde:
        params["desde"] = desde
    if hasta:
        params["hasta"] = hasta
    if direccion:
        params["direccion"] = direccion
    return params


@app.post("/v1/cfdi/procesar")
def v1_procesar(req: ProcesarRequest, x_api_key: str = Header(None), authorization: str = Header(None)):
    """Carga al procesador los XML YA descargados de la empresa (por período).

    Flujo completo: POST /v1/cfdi/solicitudes → (el espacio descarga solo) →
    este endpoint → /v1/cfdi/resumen | /v1/cfdi/excel.
    """
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "cfdi:solicitar")
    base, headers = _agente_de(user)
    r = requests.post(
        f"{base}/procesador/cfdi/cargar-desde-empresa",
        headers=headers,
        json={"rfc": req.rfc.strip().upper(), "desde": req.desde, "hasta": req.hasta, "tipo": req.tipo},
        timeout=300,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=_detalle(r) or "No se pudieron procesar los CFDIs.")
    return r.json()


@app.get("/v1/cfdi/resumen")
def v1_resumen(
    rfc: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    direccion: Optional[str] = None,
    x_api_key: str = Header(None),
    authorization: str = Header(None),
):
    """KPIs del período (totales, IVA/ISR, conteos) — para que la IA analice."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "documentos:leer")
    base, headers = _agente_de(user)
    r = requests.get(
        f"{base}/procesador/cfdi/stats",
        headers=headers,
        params=_params_filtros(rfc, desde, hasta, direccion),
        timeout=120,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=_detalle(r) or "No se pudo obtener el resumen.")
    return r.json()


@app.get("/v1/cfdi/reporte/{nombre}")
def v1_reporte(
    nombre: str,
    rfc: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    direccion: Optional[str] = None,
    x_api_key: str = Header(None),
    authorization: str = Header(None),
):
    """Reportes JSON: totales-mes · top-contrapartes · integridad."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "documentos:leer")
    base, headers = _agente_de(user)
    r = requests.get(
        f"{base}/procesador/cfdi/reporte/{nombre}",
        headers=headers,
        params=_params_filtros(rfc, desde, hasta, direccion),
        timeout=120,
    )
    if r.status_code == 404:
        raise HTTPException(status_code=404, detail=_detalle(r) or "Reporte desconocido.")
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=_detalle(r) or "No se pudo generar el reporte.")
    return r.json()


@app.get("/v1/cfdi/excel")
def v1_excel(
    rfc: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    direccion: Optional[str] = None,
    formato: str = "xlsx",
    x_api_key: str = Header(None),
    authorization: str = Header(None),
):
    """El Excel (o CSV) del período con el detalle de impuestos, en streaming."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "documentos:leer")
    base, headers = _agente_de(user)
    params = _params_filtros(rfc, desde, hasta, direccion)
    params["formato"] = formato
    r = requests.get(
        f"{base}/procesador/cfdi/exportar",
        headers=headers,
        params=params,
        timeout=300,
        stream=True,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail=_detalle(r) or "No se pudo exportar.")
    return StreamingResponse(
        r.iter_content(chunk_size=65536),
        media_type=r.headers.get("content-type", "application/octet-stream"),
        headers={"Content-Disposition": r.headers.get("content-disposition", "attachment")},
    )


@app.post("/v1/calculadoras/{tipo}")
def v1_calculadora(tipo: str, body: dict, x_api_key: str = Header(None), authorization: str = Header(None)):
    """Calculadoras fiscales/laborales (sbc, isr, aguinaldo, finiquito,
    liquidacion, carga-patronal, ptu). El agente valida y responde en español
    (p. ej. salario por debajo del mínimo) — los 400/422 se propagan tal cual."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "documentos:leer")
    base, headers = _agente_de(user)
    r = requests.post(f"{base}/calculadoras/{tipo}", headers=headers, json=body, timeout=60)
    if r.status_code in (200, 400, 404, 422):
        return Response(content=r.content, status_code=r.status_code, media_type="application/json")
    raise HTTPException(status_code=502, detail=_detalle(r) or "No se pudo calcular.")


@app.post("/v1/listas-negras")
def v1_listas_negras(body: dict, x_api_key: str = Header(None), authorization: str = Header(None)):
    """Consulta RFCs contra las listas 69/69-B (vía RPC de Supabase, sin agente)."""
    user = _auth(x_api_key, authorization)
    _exigir_scope(user, "listas-negras:consultar")
    rfcs = body.get("rfcs") or []
    if not isinstance(rfcs, list) or not rfcs or len(rfcs) > 200:
        raise HTTPException(status_code=400, detail="Manda `rfcs` (lista de 1 a 200).")
    r = requests.post(
        f"{SUPABASE_URL}/rest/v1/rpc/check_rfcs_listas_negras",
        json={"p_rfcs": [str(x).strip().upper() for x in rfcs]},
        headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
        timeout=_TIMEOUT,
    )
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="No se pudieron consultar las listas.")
    return {"resultados": r.json()}


# ---------------------------------------------------------------------------
# Interno: vínculos del asistente (Abacus) — WhatsApp → API key cifrada
# ---------------------------------------------------------------------------

# El plugin abacus-todoconta (OpenClaw, mismo VPS) resuelve aquí el remitente
# de WhatsApp a la key cifrada del usuario, en vez de hablar con Supabase
# directamente: así el proceso del bot no necesita el service key. La key
# viaja cifrada (AES-256-GCM, ASISTENTE_VINCULOS_KEY); el gateway nunca la ve
# en claro. DDL: migración 031_asistente_vinculos.sql (todoconta-apps) ·
# diseño: docs/infra/api-publica.md.
VINCULOS_INTERNAL_TOKEN = os.environ.get("VINCULOS_INTERNAL_TOKEN", "")


@app.get("/internal/vinculos/{whatsapp}")
def internal_vinculo(whatsapp: str, x_interno_token: str = Header(None)):
    """Vínculo activo de un número E.164 (solo para el plugin de Abacus)."""
    if not VINCULOS_INTERNAL_TOKEN or not hmac.compare_digest(
        x_interno_token or "", VINCULOS_INTERNAL_TOKEN
    ):
        raise HTTPException(status_code=401, detail="Token interno inválido.")
    try:
        r = requests.get(
            f"{SUPABASE_URL}/rest/v1/asistente_vinculos",
            params={
                "whatsapp_e164": f"eq.{whatsapp}",
                "estado": "eq.activo",
                "select": "user_id,api_key_cifrada",
            },
            headers={
                "apikey": SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            },
            timeout=_TIMEOUT,
        )
    except requests.RequestException:
        raise HTTPException(status_code=502, detail="No se pudo consultar el vínculo.")
    filas = r.json() if r.status_code == 200 else []
    if not filas:
        raise HTTPException(status_code=404, detail="Número sin vínculo activo.")
    return {"user_id": filas[0]["user_id"], "api_key_cifrada": filas[0]["api_key_cifrada"]}


# ---------------------------------------------------------------------------
# Servidor MCP (Streamable HTTP) — mismas operaciones como tools
# ---------------------------------------------------------------------------

try:
    from mcp.server.fastmcp import FastMCP
    from mcp.server.transport_security import TransportSecuritySettings

    mcp_srv = FastMCP(
        "TodoConta",
        instructions=(
            "Servicios fiscales del SAT (México) del usuario autenticado: catálogo "
            "de empresas, Constancia de Situación Fiscal, Opinión 32-D, descarga "
            "masiva de CFDIs y listas negras 69/69-B."
        ),
        stateless_http=True,
        streamable_http_path="/mcp",
        # Anti DNS-rebinding del SDK: sin esto solo acepta Host localhost.
        transport_security=TransportSecuritySettings(
            allowed_hosts=[DOMINIO, f"{DOMINIO}:443", "localhost", "127.0.0.1:8795"],
            allowed_origins=[f"https://{DOMINIO}", "https://app.todoconta.com"],
        ),
    )

    def _mcp_user() -> dict:
        user = ctx_user.get()
        if user is None:
            raise RuntimeError("Sesión MCP sin API key válida.")
        return user

    @mcp_srv.tool()
    def listar_empresas() -> str:
        """Lista las empresas (RFC, nombre, métodos) del espacio del usuario."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        r = requests.get(f"{base}/empresas", headers=headers, timeout=_TIMEOUT)
        filas = [
            f"- {e['rfc']} · {e['nombre']} · métodos: {', '.join(e.get('metodos') or []) or 'sin credenciales'}"
            for e in r.json().get("empresas", [])
            if not e.get("archived_at")
        ]
        return "\n".join(filas) or "No hay empresas registradas."

    @mcp_srv.tool()
    def descargar_csf(rfc: str) -> str:
        """Descarga la Constancia de Situación Fiscal de la empresa al espacio del usuario."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        rfc = rfc.strip().upper()
        activacion = _activar_empresa(base, headers, rfc)
        if "fiel" not in (activacion.get("metodos") or []) or not activacion.get("efirma_lista"):
            return (
                f"La empresa {rfc} no tiene e.firma cargada; no se puede generar una constancia "
                f"al momento. POST /v1/csf entrega la última EN ARCHIVO si existe (respuesta "
                f"marcada con X-Documento-Origen: archivo). Para una recién generada, carga la "
                f"e.firma de la empresa en TodoConta."
            )
        r = requests.post(f"{base}/constancia/fiel", headers=headers, json={}, timeout=_TIMEOUT_DOCUMENTO)
        if r.status_code != 200:
            return f"No se pudo: {_detalle(r) or 'error del portal del SAT'}"
        return (
            f"Constancia de {rfc} descargada en el espacio del usuario. "
            f"El PDF se obtiene con: POST {PUBLIC_BASE.replace('agente.', 'api.')}/v1/csf "
            f'{{"rfc": "{rfc}"}} (misma API key).'
        )

    @mcp_srv.tool()
    def descargar_opinion(rfc: str) -> str:
        """Descarga la Opinión de Cumplimiento 32-D de la empresa al espacio del usuario."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        rfc = rfc.strip().upper()
        _activar_empresa(base, headers, rfc)
        r = requests.post(f"{base}/opinion/fiel", headers=headers, json={}, timeout=_TIMEOUT_DOCUMENTO)
        if r.status_code != 200:
            return f"No se pudo: {_detalle(r) or 'error del portal del SAT'}"
        return f"Opinión 32-D de {rfc} descargada. PDF vía POST /v1/opinion (misma API key)."

    @mcp_srv.tool()
    def solicitar_cfdis(rfc: str, fecha_inicio: str, fecha_fin: str, tipo: str = "E") -> str:
        """Crea una solicitud de descarga masiva de CFDIs (tipo: E emitidos, R recibidos). Fechas YYYY-MM-DD."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        rfc = rfc.strip().upper()
        _activar_empresa(base, headers, rfc)
        r = requests.post(
            f"{base}/solicitar",
            headers=headers,
            json={"fecha_inicio": fecha_inicio, "fecha_fin": fecha_fin, "tipo_comprobante": tipo},
            timeout=120,
        )
        if r.status_code != 200:
            return f"No se pudo: {_detalle(r) or 'el SAT rechazó la solicitud'}"
        sid = r.json().get("id_solicitud")
        return (
            f"Solicitud {sid} creada para {rfc}. El espacio del usuario la descarga "
            f"solo cuando el SAT la libere (horas); consulta con estado_solicitud."
        )

    @mcp_srv.tool()
    def estado_solicitud(rfc: str, id_solicitud: str) -> str:
        """Estado de una solicitud de descarga masiva."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        r = requests.get(
            f"{base}/empresas/{rfc.strip().upper()}/solicitudes", headers=headers, timeout=_TIMEOUT
        )
        for s in r.json().get("solicitudes", []):
            if s.get("id_solicitud") == id_solicitud:
                return str(s)
        return "Solicitud no encontrada."

    @mcp_srv.tool()
    def consultar_listas_negras(rfcs: list[str]) -> str:
        """Consulta hasta 200 RFCs contra las listas negras del SAT (Art. 69 y 69-B)."""
        _mcp_user()
        r = requests.post(
            f"{SUPABASE_URL}/rest/v1/rpc/check_rfcs_listas_negras",
            json={"p_rfcs": [x.strip().upper() for x in rfcs[:200]]},
            headers={"apikey": SUPABASE_SERVICE_KEY, "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}"},
            timeout=_TIMEOUT,
        )
        return str(r.json()) if r.status_code == 200 else "No se pudieron consultar las listas."

    @mcp_srv.tool()
    def procesar_cfdis(rfc: str, desde: str = "", hasta: str = "", tipo: str = "") -> str:
        """Carga al procesador los XML ya descargados de la empresa (fechas YYYY-MM-DD; tipo E/R o vacío para ambos). Correr después de que una solicitud esté descargada."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        r = requests.post(
            f"{base}/procesador/cfdi/cargar-desde-empresa",
            headers=headers,
            json={"rfc": rfc.strip().upper(), "desde": desde or None, "hasta": hasta or None, "tipo": tipo or None},
            timeout=300,
        )
        if r.status_code != 200:
            return f"No se pudo procesar: {_detalle(r) or r.status_code}"
        d = r.json()
        return (
            f"Procesados: {d.get('agregados', 0)} nuevos, {d.get('duplicados', 0)} ya estaban, "
            f"{d.get('archivos_encontrados', 0)} archivos encontrados, {len(d.get('errores', []))} con error."
        )

    @mcp_srv.tool()
    def resumen_cfdis(rfc: str, desde: str = "", hasta: str = "", direccion: str = "") -> str:
        """KPIs del período procesado (totales, IVA/ISR retenidos y trasladados, conteos). direccion: E emitidos, R recibidos, vacío ambos."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        r = requests.get(
            f"{base}/procesador/cfdi/stats",
            headers=headers,
            params=_params_filtros(rfc, desde or None, hasta or None, direccion or None),
            timeout=120,
        )
        return str(r.json()) if r.status_code == 200 else f"No se pudo: {_detalle(r) or r.status_code}"

    @mcp_srv.tool()
    def reporte_cfdis(rfc: str, nombre: str, desde: str = "", hasta: str = "") -> str:
        """Reporte JSON del período: totales-mes | top-contrapartes | integridad."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        r = requests.get(
            f"{base}/procesador/cfdi/reporte/{nombre}",
            headers=headers,
            params=_params_filtros(rfc, desde or None, hasta or None, None),
            timeout=120,
        )
        return str(r.json()) if r.status_code == 200 else f"No se pudo: {_detalle(r) or r.status_code}"

    @mcp_srv.tool()
    def link_excel_cfdis(rfc: str, desde: str = "", hasta: str = "", direccion: str = "") -> str:
        """Link de descarga del Excel con el detalle de los CFDIs procesados (el usuario lo baja con su misma API key)."""
        _mcp_user()
        from urllib.parse import urlencode

        params = _params_filtros(rfc, desde or None, hasta or None, direccion or None)
        api = PUBLIC_BASE.replace("agente.", "api.")
        return (
            f"GET {api}/v1/cfdi/excel?{urlencode(params)} — con el header X-Api-Key de tu key. "
            "Ejemplo: curl -H 'X-Api-Key: tc_live_…' -o cfdis.xlsx '" + f"{api}/v1/cfdi/excel?{urlencode(params)}'"
        )

    def _calc(tipo: str, payload: dict) -> str:
        """Llama una calculadora del agente; los errores de validación (en
        español: p. ej. «salario por debajo del mínimo») se devuelven como
        texto para que la IA pida los datos correctos o explique el límite."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        payload = {k: v for k, v in payload.items() if v is not None}
        r = requests.post(f"{base}/calculadoras/{tipo}", headers=headers, json=payload, timeout=60)
        if r.status_code == 200:
            return str(r.json())
        if r.status_code == 422:
            try:
                faltas = "; ".join(
                    f"{'.'.join(str(x) for x in e.get('loc', []))}: {e.get('msg')}"
                    for e in r.json().get("detail", [])
                )
            except Exception:  # noqa: BLE001
                faltas = r.text[:300]
            return f"Datos inválidos o incompletos — {faltas}"
        return f"No se pudo calcular: {_detalle(r) or r.status_code}"

    @mcp_srv.tool()
    def calcular_sbc(
        salario: float,
        tipo_salario: str = "mensual",
        antiguedad_anios: int = 0,
        dias_aguinaldo: int = 15,
        prima_vacacional: float = 0.25,
        es_zona_fronteriza: bool = False,
        anio: int = 2026,
    ) -> str:
        """Salario Base de Cotización IMSS. tipo_salario: diario|mensual. Valida contra el salario mínimo vigente."""
        return _calc("sbc", {
            "salario": salario, "tipo_salario": tipo_salario, "antiguedad_anios": antiguedad_anios,
            "dias_aguinaldo": dias_aguinaldo, "prima_vacacional": prima_vacacional,
            "es_zona_fronteriza": es_zona_fronteriza, "anio": anio,
        })

    @mcp_srv.tool()
    def calcular_isr_salarios(
        ingreso_gravado: float,
        periodicidad: str = "mensual",
        mes: int = 2,
        es_asimilado: bool = False,
        es_zona_fronteriza: bool = False,
        anio: int = 2026,
    ) -> str:
        """ISR de salarios (tarifas SAT vigentes + subsidio). periodicidad: diario|semanal|decenal|quincenal|mensual."""
        return _calc("isr", {
            "ingreso_gravado": ingreso_gravado, "periodicidad": periodicidad, "mes": mes,
            "es_asimilado": es_asimilado, "es_zona_fronteriza": es_zona_fronteriza, "anio": anio,
        })

    @mcp_srv.tool()
    def calcular_aguinaldo(
        salario: float,
        tipo_salario: str,
        fecha_ingreso: str,
        dias_aguinaldo: int = 15,
        anio: int = 2026,
    ) -> str:
        """Aguinaldo proporcional con su ISR. fecha_ingreso: YYYY-MM-DD."""
        return _calc("aguinaldo", {
            "salario": salario, "tipo_salario": tipo_salario, "fecha_ingreso": fecha_ingreso,
            "dias_aguinaldo": dias_aguinaldo, "anio": anio,
        })

    @mcp_srv.tool()
    def calcular_finiquito(
        salario: float,
        tipo_salario: str,
        fecha_ingreso: str,
        fecha_baja: str,
        anio: int = 2026,
    ) -> str:
        """Finiquito (renuncia): proporcionales de aguinaldo, vacaciones y prima. Fechas YYYY-MM-DD."""
        return _calc("finiquito", {
            "salario": salario, "tipo_salario": tipo_salario, "fecha_ingreso": fecha_ingreso,
            "fecha_baja": fecha_baja, "anio": anio,
        })

    @mcp_srv.tool()
    def calcular_carga_patronal(
        salario: float,
        tipo_salario: str = "mensual",
        antiguedad_anios: int = 0,
        clase_riesgo: str = "I",
        codigo_estado: str = "CDMX",
        anio: int = 2026,
    ) -> str:
        """Costo patronal total (IMSS, Infonavit, impuesto estatal) de un sueldo."""
        return _calc("carga-patronal", {
            "salario": salario, "tipo_salario": tipo_salario, "antiguedad_anios": antiguedad_anios,
            "clase_riesgo": clase_riesgo, "codigo_estado": codigo_estado, "anio": anio,
        })

    @mcp_srv.tool()
    def indicadores_fiscales(anio: int = 2026) -> str:
        """Indicadores vigentes del año: UMA, salarios mínimos (general y ZLFN), etc."""
        user = _mcp_user()
        base, headers = _agente_de(user)
        r = requests.get(f"{base}/calculadoras/indicadores/{anio}", headers=headers, timeout=30)
        return str(r.json()) if r.status_code == 200 else f"No disponible: {r.status_code}"

    _mcp_app = mcp_srv.streamable_http_app()

    # El session manager del SDK exige correr dentro de un lifespan; al montar
    # el sub-app, FastAPI NO ejecuta el suyo — se engancha al del app padre.
    @asynccontextmanager
    async def _lifespan(_app):
        async with mcp_srv.session_manager.run():
            yield

    app.router.lifespan_context = _lifespan

    @app.middleware("http")
    async def _mcp_auth(request: Request, call_next):
        # /v1 se autentica por endpoint; /mcp aquí (las tools leen ctx_user).
        if request.url.path.startswith("/mcp"):
            try:
                user = _validar_key(
                    request.headers.get("x-api-key")
                    or (request.headers.get("authorization") or "").removeprefix("Bearer ").strip()
                )
                _exigir_scope(user, "mcp")
            except HTTPException as e:
                from fastapi.responses import JSONResponse

                return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
            ctx_user.set(user)
        return await call_next(request)

    # Mount en raíz con path interno /mcp: sirve /mcp EXACTO (sin el 307 a
    # /mcp/ que rompe a los clientes). Las rutas /v1 se registran antes y ganan.
    app.mount("/", _mcp_app)
    logger.info("servidor MCP montado en /mcp")
except ImportError:  # pragma: no cover — sin SDK, la REST sigue funcionando
    logger.warning("SDK de MCP no disponible; /mcp deshabilitado")

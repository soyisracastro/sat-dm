"""
FastAPI server para exponer el cliente SAT Descarga Masiva via HTTP local.

Corre en localhost:8787. La app web (todoconta-apps) se conecta a este endpoint
para iniciar descargas sin que la e-firma salga de la máquina del usuario.

Arquitectura:
    [app.todoconta.com] ──── fetch(localhost:8787) ────→ [Python local]
                                                                 │
                                                         [SAT Web Service]
                                                         [e-firma local]

Uso:
    uvicorn sat_descarga.api.server:app --port 8787 --host 127.0.0.1

    O desde código:
        from sat_descarga.server import start
        start()
"""

import logging
import os
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FastAPI y dependencias (lazy-import para no romper el módulo base si no
# están instalados)
# ---------------------------------------------------------------------------

try:
    from fastapi import FastAPI, HTTPException, UploadFile, File, Form
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "fastapi no está instalado. Ejecuta:\n"
        "  pip install fastapi uvicorn[standard]"
    )

from . import jobs

from ..core.fiel import FIEL
from ..webservice.auth import obtener_token
from ..webservice.solicitud import solicitar_descarga
from ..webservice.verificacion import verificar_solicitud
from ..utils.validacion import validar_masivo, EstadoCFDI
from ..core.config import TIPO_CFDI, TIPO_METADATA, TIPO_EMITIDO, TIPO_RECIBIDO

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: "FastAPI"):
    # IMPORTANTE: NO autocargar la e.firma aquí. Antes hacíamos
    # `_autocargar_empresa_default()` en el lifespan para sincronizar "empresa
    # activa" con "e.firma en sesión", pero esa función llama a
    # `keyring.get_password()` y en Windows con el binario PyInstaller sin
    # firma, el Credential Manager bloquea esperando un prompt UI que nunca
    # llega (proceso non-interactive). Resultado: el lifespan jamás
    # completaba, uvicorn nunca aceptaba conexiones y `/health` no respondía
    # → el shell Electron quedaba en "Cargando…" infinito.
    #
    # Solución: carga lazy. El renderer invoca POST /auth/autocargar
    # explícitamente después del login (no bloquea startup), o cada endpoint
    # que necesite FIEL la carga on-demand. Ver memoria
    # `feedback-keyring-macos-unsigned-hang`.
    yield


app = FastAPI(
    title="SAT Descarga Masiva — Agente Local",
    description=(
        "Servidor local para descargar CFDIs del SAT sin exponer la e-firma. "
        "La e-firma nunca sale de tu máquina."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# CORS: el agente bindea a 127.0.0.1 y NUNCA expone puerto a la red externa,
# así que aceptar cualquier origin es seguro (no hay superficie de ataque
# cross-site real). En Electron empacado el renderer corre desde
# `file://...resources/ui/index.html` y el browser envía `Origin: null` o
# `file://`, NO incluidos en la antigua allow-list — eso bloqueaba todas las
# requests del renderer en producción y dejaba la app stuck en "Cargando…"
# (el agente recibía y respondía 200, pero el browser tiraba el response
# por CORS antes de entregárselo al JS).
#
# `allow_credentials=False` + `allow_origins=["*"]` es la combinación válida
# por especificación CORS — no se pueden combinar `*` con `True`. Es OK
# para nosotros: el renderer NO manda cookies ni credenciales (el Bearer
# token de Supabase vive solo en el agente Python, nunca llega al renderer).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Estado de sesión (en memoria — un usuario a la vez en el agente local)
# ---------------------------------------------------------------------------

_session: dict = {
    "fiel": None,        # Objeto FIEL cargado
    "rfc": None,         # RFC extraído del certificado
    "cer_path": None,    # Path al .cer
    "key_path": None,    # Path al .key
    "password": None,    # Contraseña de la llave (en memoria, no en disco)
    "es_temp": False,    # True si cer/key son temporales (borrar al limpiar);
                         # False si apuntan a una empresa guardada (NO borrar).
}


def _get_fiel() -> FIEL:
    if _session["fiel"] is None:
        raise HTTPException(
            status_code=401,
            detail=(
                "No hay e-firma cargada. "
                "Llama primero a POST /auth/cargar-fiel con tu .cer y .key"
            ),
        )
    return _session["fiel"]


def _renovar_token() -> str:
    """Obtiene un token fresco del SAT."""
    fiel = _get_fiel()
    token = obtener_token(fiel)
    return token


# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------

class SolicitudRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    tipo_solicitud: str = TIPO_CFDI       # "CFDI" o "Metadata"
    tipo_comprobante: str = TIPO_EMITIDO  # "E" o "R"
    rfc_emisor: Optional[str] = None
    rfc_receptor: Optional[str] = None


class VerificarRequest(BaseModel):
    id_solicitud: str
    poll: bool = False  # True = bloquea hasta que termine


class DescargaCompletaRequest(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    tipo_comprobante: str = TIPO_EMITIDO
    directorio_salida: str = "./cfdi/"
    extraer: bool = True


class SolicitudFolioRequest(BaseModel):
    uuids: List[str]
    tipo_solicitud: str = TIPO_CFDI
    directorio_salida: str = "./cfdi/"
    extraer: bool = True


class CfdiValidarInput(BaseModel):
    uuid: str
    emisor_rfc: str
    receptor_rfc: str
    total: float


class ValidarRequest(BaseModel):
    cfdis: List[CfdiValidarInput]
    concurrency: int = 10


class CIECDescargaRequest(BaseModel):
    rfc: str
    ciec: Optional[str] = None  # si falta, se toma del catálogo (keychain)
    fecha_inicio: date
    fecha_fin: date
    tipo_comprobante: str = TIPO_RECIBIDO
    directorio_salida: str = "./cfdi/"
    max_registros: int = 500


class FIELCfdiRequest(BaseModel):
    # Las credenciales (cer/key/password) vienen de la sesión (`_get_fiel`),
    # cargadas por /auth/cargar-fiel o por el lifespan al activar empresa.
    fecha_inicio: date
    fecha_fin: date
    tipo_comprobante: str = TIPO_RECIBIDO
    max_registros: int = 500


class ConstanciaRequest(BaseModel):
    rfc: str
    ciec: Optional[str] = None  # si falta, se toma del catálogo (keychain)
    directorio_salida: str = "./constancia/"


class OpinionRequest(BaseModel):
    rfc: str
    ciec: Optional[str] = None  # si falta, se toma del catálogo (keychain)


class CaptchaSolution(BaseModel):
    # solution=None significa que el usuario canceló (cierra el modal del captcha).
    solution: Optional[str] = None


class EmpresaCiecRequest(BaseModel):
    rfc: str
    nombre: str
    ciec: str


class RegimenFiscalItem(BaseModel):
    clave: str
    descripcion: str


class ActividadEconomicaItem(BaseModel):
    descripcion: str
    principal: Optional[bool] = None


class EmpresaUpdateRequest(BaseModel):
    regimenes_fiscales: Optional[list[RegimenFiscalItem]] = None
    actividades_economicas: Optional[list[ActividadEconomicaItem]] = None


class DescargasDirRequest(BaseModel):
    dir: str


class AbrirRequest(BaseModel):
    ruta: str
    modo: str = "carpeta"  # "carpeta" (abre el folder) | "archivo" (abre el PDF/archivo)


class DescargaInteligente(BaseModel):
    fecha_inicio: date
    fecha_fin: date
    tipo_comprobante: str = TIPO_EMITIDO
    directorio_salida: str = "./cfdi/"
    ciec: Optional[str] = None  # Si se provee, se puede usar para vol. pequeños
    umbral_ciec: int = 500      # Usar CIEC si el conteo es menor a esto


# ---------------------------------------------------------------------------
# Endpoints: estado del servidor
# ---------------------------------------------------------------------------

@app.get("/health")
def health():
    """Verifica que el servidor está corriendo y si hay e-firma cargada.

    Incluye la vigencia de la e-firma en sesión (`efirma_vencimiento` ISO y
    `efirma_vigente`) para que la UI muestre el semáforo de vencimiento.
    """
    fiel = _session["fiel"]
    return {
        "status": "ok",
        "rfc_cargado": _session["rfc"],
        "efirma_lista": fiel is not None,
        "efirma_vencimiento": fiel.not_valid_after.date().isoformat() if fiel else None,
        "efirma_vigente": fiel.vigente if fiel else None,
    }


# ---------------------------------------------------------------------------
# Endpoints: e-firma
# ---------------------------------------------------------------------------

@app.post("/auth/cargar-fiel")
async def cargar_fiel(
    cer_file: UploadFile = File(..., description="Certificado .cer de la e-firma"),
    key_file: UploadFile = File(..., description="Llave privada .key de la e-firma"),
    password: str = Form(..., description="Contraseña de la llave privada"),
):
    """
    Carga la e-firma en memoria del agente local.

    Los archivos se leen en memoria para validar el par certificado/llave.
    Internamente se escriben a archivos temporales del OS (necesario para
    las operaciones criptográficas), pero NUNCA se envían a ningún servidor.

    La e-firma queda disponible para las operaciones de descarga hasta que
    el agente se reinicia o se llama a DELETE /auth/fiel.
    """
    # Leer contenido en memoria
    cer_data = await cer_file.read()
    key_data = await key_file.read()

    # Escribir a temporales para que FIEL pueda cargarlos
    cer_tmp = tempfile.NamedTemporaryFile(suffix=".cer", delete=False)
    key_tmp = tempfile.NamedTemporaryFile(suffix=".key", delete=False)

    try:
        cer_tmp.write(cer_data)
        cer_tmp.flush()
        key_tmp.write(key_data)
        key_tmp.flush()
        cer_tmp.close()
        key_tmp.close()

        fiel = FIEL(cer_tmp.name, key_tmp.name, password)

        # Limpiar sesión anterior si existía
        _limpiar_session()

        _session["fiel"] = fiel
        _session["rfc"] = fiel.rfc
        _session["cer_path"] = cer_tmp.name
        _session["key_path"] = key_tmp.name
        _session["password"] = password
        _session["es_temp"] = True  # archivos temporales → se borran al limpiar

        return {
            "ok": True,
            "rfc": fiel.rfc,
            "numero_serie": fiel.numero_serie,
        }

    except Exception as e:
        # Limpiar temporales si falla la carga
        for path in (cer_tmp.name, key_tmp.name):
            try:
                os.unlink(path)
            except Exception:
                pass
        raise HTTPException(status_code=400, detail=f"Error al cargar e-firma: {e}")


@app.delete("/auth/fiel")
def descargar_fiel():
    """Descarga la e-firma de memoria y elimina los temporales."""
    _limpiar_session()
    return {"ok": True, "mensaje": "E-firma descargada de memoria."}


@app.post("/auth/autocargar-fiel")
def autocargar_fiel_default():
    """
    Carga la FIEL de la empresa activa (si existe) en sesión.

    Reemplazo del autoload que antes corría en el lifespan del agente — ahora
    se invoca explícitamente desde el renderer (post-login) para no bloquear
    el arranque del agente con un `keyring.get_password()` que en Windows
    sin firma puede colgarse esperando un prompt UI.

    Idempotente: si ya hay FIEL en sesión, no hace nada. Si la empresa no
    tiene FIEL o falla la carga, devuelve `ok=false` con detalle — el caller
    NO debe tratar esto como fatal (la app sigue funcional, el usuario solo
    tendrá que cargar la FIEL a mano desde Empresas).
    """
    try:
        _autocargar_empresa_default()
        rfc = _session.get("rfc")
        return {
            "ok": True,
            "cargada": rfc is not None,
            "rfc": rfc,
        }
    except Exception as e:  # noqa: BLE001
        logger.warning("autocargar-fiel falló: %s", e)
        return {"ok": False, "cargada": False, "rfc": None, "error": str(e)}


def _limpiar_session():
    """Limpia el estado de sesión. Solo borra los .cer/.key si eran temporales
    (no toca los de una empresa guardada en ./efirma/)."""
    if _session.get("es_temp"):
        for path_key in ("cer_path", "key_path"):
            path = _session.get(path_key)
            if path:
                try:
                    os.unlink(path)
                except Exception:
                    pass
    _session.update({
        "fiel": None,
        "rfc": None,
        "cer_path": None,
        "key_path": None,
        "password": None,
        "es_temp": False,
    })


def _cargar_fiel_empresa(empresa: dict) -> bool:
    """
    Carga la e.firma de una empresa del catálogo en `_session`.

    `empresa` es el dict de `config_store.get_empresa` (con cer_path/key_path/password).
    Devuelve True si cargó la e.firma; False si la empresa no tiene método FIEL.
    Lanza ValueError si la e.firma está incompleta o no se pudo abrir (cert/llave/contraseña).
    """
    if "fiel" not in empresa.get("metodos", []):
        return False
    cer, key, pwd = empresa.get("cer_path"), empresa.get("key_path"), empresa.get("password")
    if not (cer and key and pwd):
        raise ValueError("La empresa no tiene e.firma completa.")
    fiel = FIEL(cer, key, pwd)  # nota: carga aunque el cert esté vencido (la UI avisa)
    _limpiar_session()
    _session.update({
        "fiel": fiel, "rfc": fiel.rfc, "cer_path": cer,
        "key_path": key, "password": pwd, "es_temp": False,
    })
    return True


def _autocargar_empresa_default() -> None:
    """Carga al arranque la e.firma de la empresa predeterminada (si tiene FIEL).

    Se llama desde el lifespan del agente. Tolerante a fallos: si la empresa no
    tiene e.firma, o el cert/llave no se pueden abrir, solo se registra y se sigue
    (la UI permite cargarla a mano)."""
    if _session["fiel"] is not None:
        return
    try:
        from ..cli import config_store
        rfc = config_store.get_default()
        if not rfc:
            return
        if _cargar_fiel_empresa(config_store.get_empresa(rfc)):
            logger.info("e.firma de la empresa activa (%s) cargada al arranque.", rfc)
    except Exception as e:  # noqa: BLE001
        logger.warning("No se pudo autocargar la e.firma de la empresa activa: %s", e)


# ---------------------------------------------------------------------------
# Endpoints: Web Service oficial (e-firma)
# ---------------------------------------------------------------------------

@app.post("/solicitar")
def solicitar(req: SolicitudRequest):
    """
    Solicita una descarga masiva al SAT. Devuelve el RequestID.

    El SAT procesa de forma asíncrona:
    - Metadata: responde en segundos/minutos.
    - CFDIs completos: puede tardar 24-72 horas.

    Usa /verificar para consultar el estado y /descargar cuando esté lista.
    """
    fiel = _get_fiel()
    token = _renovar_token()

    try:
        id_solicitud = solicitar_descarga(
            fiel=fiel,
            token=token,
            rfc_solicitante=fiel.rfc,
            fecha_inicio=req.fecha_inicio,
            fecha_fin=req.fecha_fin,
            tipo_solicitud=req.tipo_solicitud,
            tipo_comprobante=req.tipo_comprobante,
            rfc_emisor=req.rfc_emisor,
            rfc_receptor=req.rfc_receptor,
            # El SAT rechaza la solicitud (CodEstatus=301 "XML Mal Formado") si no
            # se envía EstadoComprobante — no permite descargar cancelados por WS.
            # Lo forzamos a "Vigente" siempre (E y R por igual): no es una opción
            # del usuario, es un requisito del SAT.
            estado_comprobante="Vigente",
        )
        _guardar_solicitud_ws(fiel.rfc, id_solicitud, req)
        return {"ok": True, "id_solicitud": id_solicitud}
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/verificar")
def verificar(req: VerificarRequest):
    """
    Consulta el estado de una solicitud de descarga.

    Estados posibles:
    - 1: En cola
    - 2: Procesando
    - 3: Lista (package_ids disponibles para descargar)
    - 4: Error del SAT
    - 5: Rechazada

    Si poll=True, bloquea hasta que la solicitud termine (puede tardar horas).
    Para uso interactivo, usar poll=False y hacer polling periódico desde el cliente.
    """
    fiel = _get_fiel()
    token = _renovar_token()

    try:
        estado = verificar_solicitud(
            token=token,
            rfc_solicitante=fiel.rfc,
            id_solicitud=req.id_solicitud,
            fiel=fiel,
            poll=req.poll,
        )
        _actualizar_solicitud_ws(
            fiel.rfc, req.id_solicitud, estado.cod_estado,
            package_ids=estado.package_ids if estado.package_ids else None,
            mensaje=estado.mensaje,
            numero_cfdis=estado.numero_cfdis,
        )
        return {
            "cod_estado": estado.cod_estado,
            "mensaje": estado.mensaje,
            "numero_cfdis": estado.numero_cfdis,
            "package_ids": estado.package_ids,
            "terminada": estado.terminada,
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/descargar")
def descargar(
    id_solicitud: str,
    directorio_salida: Optional[str] = None,
    extraer: bool = True,
):
    """
    Descarga los paquetes de una solicitud ya terminada (cod_estado=3).

    Llama primero a /verificar para confirmar que la solicitud está lista.
    Si no se pasa `directorio_salida`, se usa la convención por empresa
    (`<descargas>/cfdi/{RFC}/{emitidos|recibidos}/{desde}_a_{hasta}/`), igual que
    las descargas vía CIEC. La carpeta se compone con los datos persistidos al
    crearse la solicitud (`config_store.get_solicitud`); si no hay registro (p. ej.
    flujo legacy), cae al directorio base por RFC.
    """
    from ..webservice.descarga import descargar_todos

    fiel = _get_fiel()
    token = _renovar_token()

    salida = directorio_salida or _salida_descarga_ws(fiel.rfc, id_solicitud)

    # Verificar estado actual — la petición DEBE ir firmada (xmldsig) con la FIEL,
    # si no, el SAT devuelve un EstadoSolicitud vacío y se ve como "no está lista".
    try:
        estado = verificar_solicitud(
            token=token,
            rfc_solicitante=fiel.rfc,
            id_solicitud=id_solicitud,
            fiel=fiel,
            poll=False,
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not estado.terminada:
        raise HTTPException(
            status_code=409,
            detail=(
                f"La solicitud no está lista (cod_estado={estado.cod_estado}). "
                "Espera a que el SAT termine de procesarla."
            ),
        )

    if not estado.package_ids:
        return {"ok": True, "archivos": [], "total": 0, "mensaje": "Sin CFDIs para el periodo."}

    # Renovar token antes de descargar (puede haber expirado durante el polling)
    token = _renovar_token()

    try:
        zips = descargar_todos(
            token=token,
            rfc_solicitante=fiel.rfc,
            package_ids=estado.package_ids,
            directorio_salida=salida,
            fiel=fiel,
            extraer=extraer,
        )
        _registrar_descarga(
            fiel.rfc, "ws", "cfdi",
            descripcion=f"Descarga WS · solicitud {id_solicitud[:8]}…",
            ruta=salida, total=estado.numero_cfdis,
        )
        _actualizar_solicitud_ws(
            fiel.rfc, id_solicitud, "descargada", package_ids=estado.package_ids,
        )
        return {
            "ok": True,
            "archivos": [str(z) for z in zips],
            "total": len(zips),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/descarga-completa")
def descarga_completa(req: DescargaCompletaRequest):
    """
    Flujo completo en un solo endpoint: solicitar → polling → descargar.

    ADVERTENCIA: Bloquea hasta completar. Para CFDIs completos esto puede
    tardar horas (el SAT tarda 24-72 hrs en procesar). Usar solo para
    Metadata o para scripts no interactivos.

    Para uso interactivo en la UI, usar /solicitar + /verificar + /descargar
    de forma separada.
    """
    from ..webservice.client import descargar_cfdi

    try:
        zips = descargar_cfdi(
            cer_path=_session["cer_path"],
            key_path=_session["key_path"],
            password=_session["password"],
            fecha_inicio=req.fecha_inicio,
            fecha_fin=req.fecha_fin,
            directorio_salida=req.directorio_salida,
            tipo_solicitud=TIPO_CFDI,
            tipo_comprobante=req.tipo_comprobante,
            extraer=req.extraer,
        )
        _registrar_descarga(
            _session["rfc"], "ws", "cfdi",
            descripcion=f"Descarga WS completa · {req.fecha_inicio} a {req.fecha_fin}",
            ruta=req.directorio_salida,
        )
        return {
            "ok": True,
            "archivos": [str(z) for z in zips],
            "total": len(zips),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Descarga por UUID (SolicitaDescargaFolio)
# ---------------------------------------------------------------------------

@app.post("/solicitar-folio")
def solicitar_folio(req: SolicitudFolioRequest):
    """
    Solicita descarga de CFDIs específicos por UUID.

    Útil para auditorías de folios específicos. Flujo asíncrono igual
    que /solicitar: retorna RequestID → /verificar → /descargar.
    """
    from ..webservice.client import descargar_por_uuid

    _get_fiel()

    try:
        zips = descargar_por_uuid(
            cer_path=_session["cer_path"],
            key_path=_session["key_path"],
            password=_session["password"],
            uuids=req.uuids,
            directorio_salida=req.directorio_salida,
            tipo_solicitud=req.tipo_solicitud,
            extraer=req.extraer,
        )
        return {
            "ok": True,
            "archivos": [str(z) for z in zips],
            "total": len(zips),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Metadata
# ---------------------------------------------------------------------------

@app.post("/metadata")
def descargar_metadata_endpoint(req: SolicitudRequest):
    """
    Descarga metadata de CFDIs del SAT y retorna el CSV parseado.

    La metadata es un resumen rápido (UUID, RFC, monto, estatus) procesado
    en segundos/minutos (vs 24-72 hrs para CFDIs completos).
    """
    from ..webservice.client import descargar_metadata
    from ..utils.metadata import metadata_to_dicts

    fiel = _get_fiel()

    try:
        records = descargar_metadata(
            cer_path=_session["cer_path"],
            key_path=_session["key_path"],
            password=_session["password"],
            fecha_inicio=req.fecha_inicio,
            fecha_fin=req.fecha_fin,
            tipo_comprobante=req.tipo_comprobante,
            rfc_emisor=req.rfc_emisor,
            rfc_receptor=req.rfc_receptor,
        )
        return {
            "ok": True,
            "total": len(records),
            "records": metadata_to_dicts(records),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Validación CFDI (NO requiere FIEL — servicio público del SAT)
# ---------------------------------------------------------------------------

@app.post("/validar")
def validar_cfdis(req: ValidarRequest):
    """
    Valida el estatus de CFDIs ante el SAT (Vigente/Cancelado/No Encontrado).

    NO requiere e-firma. Usa el endpoint público del SAT en
    consultaqr.facturaelectronica.sat.gob.mx.

    Interfaz compatible con todoconta-apps — puede reemplazar la API route
    /api/sat/verify de Next.js, delegando la validación al agente Python local
    (más rápido, sin workarounds de DNS de Next.js/undici).

    Body: { cfdis: [{ uuid, emisor_rfc, receptor_rfc, total }], concurrency: 10 }
    Response: { results: [{ uuid, estado, es_cancelable, estatus_cancelacion, error }] }
    """
    cfdis = [
        {
            "uuid": c.uuid,
            "emisor_rfc": c.emisor_rfc,
            "receptor_rfc": c.receptor_rfc,
            "total": c.total,
        }
        for c in req.cfdis
    ]

    try:
        resultados = validar_masivo(cfdis, concurrency=req.concurrency)
        return {
            "results": [
                {
                    "uuid": r.uuid,
                    "estado": r.estado,
                    "es_cancelable": r.es_cancelable,
                    "estatus_cancelacion": r.estatus_cancelacion,
                    "validacion_efos": r.validacion_efos,
                    "error": r.error,
                }
                for r in resultados
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Organizador de XMLs (NO requiere FIEL)
# ---------------------------------------------------------------------------

class OrganizarRequest(BaseModel):
    origen: str
    destino: str
    estructura: str = "rfc_emisor/anio/mes"
    copiar: bool = False


class RenombrarRequest(BaseModel):
    directorio: str
    patron: str = "emisor_fecha_total"


class DeduplicarRequest(BaseModel):
    directorio: str
    dry_run: bool = False


@app.post("/organizar")
def organizar_endpoint(req: OrganizarRequest):
    """Organiza archivos XML en carpetas basándose en su contenido."""
    from ..utils.organizador import organizar

    try:
        result = organizar(req.origen, req.destino, req.estructura, req.copiar)
        return {
            "archivos_procesados": result.archivos_procesados,
            "archivos_movidos": result.archivos_movidos,
            "archivos_omitidos": result.archivos_omitidos,
            "errores": result.errores,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/renombrar")
def renombrar_endpoint(req: RenombrarRequest):
    """Renombra masivamente archivos XML basándose en su contenido."""
    from ..utils.organizador import renombrar

    try:
        result = renombrar(req.directorio, req.patron)
        return {
            "archivos_procesados": result.archivos_procesados,
            "archivos_movidos": result.archivos_movidos,
            "archivos_omitidos": result.archivos_omitidos,
            "errores": result.errores,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/deduplicar")
def deduplicar_endpoint(req: DeduplicarRequest):
    """Elimina archivos XML duplicados basándose en el UUID."""
    from ..utils.organizador import eliminar_duplicados

    try:
        result = eliminar_duplicados(req.directorio, dry_run=req.dry_run)
        return {
            "archivos_analizados": result.archivos_analizados,
            "duplicados_encontrados": result.duplicados_encontrados,
            "duplicados_eliminados": result.duplicados_eliminados,
            "errores": result.errores,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Routing inteligente (CIEC vs Web Service)
# ---------------------------------------------------------------------------

@app.post("/descarga-inteligente")
def descarga_inteligente(req: DescargaInteligente):
    """
    Routing automático según el volumen de CFDIs:

    1. Consulta Metadata del periodo (rápido, <1 min, requiere e-firma).
    2. Si el conteo < umbral_ciec Y se provee ciec → descarga via portal CIEC
       (inmediata, ~2 min).
    3. Si el conteo >= umbral_ciec O no hay ciec → inicia solicitud via Web
       Service (asíncrono, 24-72 hrs).

    Returns:
        {
          "metodo": "ciec" | "web_service",
          "numero_cfdis": int,
          ... (resultado del método elegido)
        }
    """
    from ..webservice.client import descargar_cfdi_inteligente

    _get_fiel()  # Verificar que hay e-firma

    try:
        resultado = descargar_cfdi_inteligente(
            cer_path=_session["cer_path"],
            key_path=_session["key_path"],
            password=_session["password"],
            fecha_inicio=req.fecha_inicio,
            fecha_fin=req.fecha_fin,
            tipo_comprobante=req.tipo_comprobante,
            directorio_salida=req.directorio_salida,
            ciec=req.ciec,
            umbral_ciec=req.umbral_ciec,
        )
        return resultado
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: Portal CIEC (scraping)
# ---------------------------------------------------------------------------

@app.post("/ciec/descargar")
def descargar_ciec(req: CIECDescargaRequest):
    """
    Descarga CFDIs via el portal web del SAT (autenticación CIEC).

    Apropiado para volúmenes pequeños (< 500 XMLs). Abre una ventana de
    browser para que el usuario resuelva el captcha.

    Requiere: pip install playwright && playwright install chromium
    """
    from ..portal.cfdi import descargar_cfdi_ciec

    try:
        archivos = descargar_cfdi_ciec(
            rfc=req.rfc,
            ciec=req.ciec,
            fecha_inicio=req.fecha_inicio,
            fecha_fin=req.fecha_fin,
            tipo_comprobante=req.tipo_comprobante,
            directorio_salida=req.directorio_salida,
            max_registros=req.max_registros,
        )
        return {
            "ok": True,
            "metodo": "ciec",
            "archivos": [str(a) for a in archivos],
            "total": len(archivos),
        }
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"playwright no instalado: {e}\n"
                "Ejecuta: pip install playwright && playwright install chromium"
            ),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/constancia/descargar")
def descargar_constancia(req: ConstanciaRequest):
    """
    Descarga la Constancia de Situación Fiscal (CSF) via el portal del SAT (CIEC).

    Abre una ventana de browser para que el usuario resuelva el captcha; luego da
    clic en «Generar Constancia» y captura el PDF de la ventana que abre el SAT.

    Requiere: pip install playwright && playwright install chromium
    """
    from ..portal.constancia import descargar_constancia_ciec

    try:
        pdf = descargar_constancia_ciec(
            rfc=req.rfc,
            ciec=req.ciec,
            directorio_salida=req.directorio_salida,
        )
        if not pdf:
            raise HTTPException(
                status_code=502,
                detail="No se pudo generar/descargar la constancia.",
            )
        return {"ok": True, "archivo": str(pdf)}
    except ImportError as e:
        raise HTTPException(
            status_code=503,
            detail=(
                f"playwright no instalado: {e}\n"
                "Ejecuta: pip install playwright && playwright install chromium"
            ),
        )
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ---------------------------------------------------------------------------
# Endpoints: jobs CIEC con captcha in-app (para el desktop)
# ---------------------------------------------------------------------------
#
# A diferencia de /ciec/descargar y /constancia/descargar (síncronos, que abren
# la ventana tkinter local), estos endpoints corren el scrape en un worker thread
# y resuelven el captcha por HTTP: el front escucha GET /events/{job_id} (SSE), ve
# la imagen del captcha y responde con POST /jobs/{job_id}/captcha. Así el browser
# corre headless y el captcha se muestra dentro de la UI (Electron). Ver api/jobs.py.


def _descargas_base() -> str:
    """Carpeta base de descargas configurada (default ~/Documents/TodoConta)."""
    from ..cli import config_store
    return config_store.get_descargas_dir()


def _resolver_ciec(rfc: str, ciec: Optional[str]) -> str:
    """Usa la CIEC dada o, si falta, la guardada en el catálogo (keychain del SO)."""
    if ciec:
        return ciec
    from ..cli import config_store
    try:
        guardada = config_store.get_empresa(rfc).get("ciec")
    except KeyError:
        guardada = None
    if not guardada:
        raise HTTPException(
            status_code=400,
            detail="No hay contraseña CIEC para este RFC. Regístrala en Empresas.",
        )
    return guardada


def _registrar_descarga(rfc, canal, tipo, descripcion="", ruta="", total=None):
    """Registra una descarga completada en el historial. Best-effort: nunca lanza."""
    try:
        from ..cli import config_store
        config_store.registrar_descarga(
            rfc, canal, tipo, descripcion=descripcion, ruta=ruta, total=total,
        )
    except Exception:  # noqa: BLE001 - el historial no debe romper una descarga
        logger.warning("No se pudo registrar la descarga en el historial", exc_info=True)


def _guardar_solicitud_ws(rfc: str, id_solicitud: str, req: "SolicitudRequest") -> None:
    """Guarda la solicitud WS recién creada en el catálogo por empresa. Best-effort.

    Persiste `tipo_comprobante` (E/R) además del tipo humano: lo necesita /descargar
    para ubicar la salida en `{RFC}/{emitidos|recibidos}/{rango}/`.
    """
    try:
        from ..cli import config_store
        cuales = {"E": "emitidos", "R": "recibidos"}.get(req.tipo_comprobante, "")
        tipo_humano = f"{req.tipo_solicitud} · {cuales}".rstrip(" ·")
        config_store.save_solicitud(
            rfc, id_solicitud,
            str(req.fecha_inicio), str(req.fecha_fin),
            tipo=tipo_humano,
            tipo_comprobante=req.tipo_comprobante,
        )
    except Exception:  # noqa: BLE001
        logger.warning("No se pudo guardar la solicitud en el historial", exc_info=True)


def _actualizar_solicitud_ws(
    rfc: str,
    id_solicitud: str,
    estado: str,
    package_ids=None,
    *,
    mensaje: Optional[str] = None,
    numero_cfdis: Optional[int] = None,
) -> None:
    """Actualiza el estado de una solicitud WS guardada. Best-effort.

    También persiste `mensaje` y `numero_cfdis` cuando vienen (los devuelve el SAT
    en /verificar) para mostrarlos en la fila expandida de la UI."""
    try:
        from ..cli import config_store
        config_store.update_solicitud(
            rfc, id_solicitud, estado, package_ids=package_ids,
            mensaje=mensaje, numero_cfdis=numero_cfdis,
        )
    except Exception:  # noqa: BLE001
        logger.warning("No se pudo actualizar la solicitud en el historial", exc_info=True)


def _salida_descarga_ws(rfc: str, id_solicitud: str) -> str:
    """Calcula la carpeta de salida para `/descargar` siguiendo la convención CIEC
    (`{base}/cfdi/{RFC}/{emitidos|recibidos}/{desde}_a_{hasta}/`), recuperando del
    catálogo lo que el usuario solicitó. Si el registro no existe o le falta info,
    cae al directorio base por RFC (compatible hacia atrás)."""
    from ..cli import config_store
    from ..core import paths
    from datetime import date as _date

    base = _descargas_base()
    try:
        sol = config_store.get_solicitud(rfc, id_solicitud) or {}
    except Exception:  # noqa: BLE001
        sol = {}
    tipo = sol.get("tipo_comprobante")
    fi, ff = sol.get("fecha_inicio"), sol.get("fecha_fin")
    if tipo in ("E", "R") and fi and ff:
        try:
            return str(paths.dir_cfdi(rfc, tipo, _date.fromisoformat(fi),
                                      _date.fromisoformat(ff), salida_base=base))
        except ValueError:
            pass  # fechas malformadas → fallback
    return str(paths.dir_cfdi_base(rfc, salida_base=base))


def _lanzar_job_portal(fn_factory, al_completar=None):
    """
    Crea un job de scraping del portal (CIEC o FIEL), inyecta el callback de captcha
    del bridge y lo corre en un worker thread. `fn_factory(pedir_captcha)` devuelve
    el callable del scrape; las factories FIEL simplemente ignoran `pedir_captcha`
    porque el login con e.firma no pide captcha.
    `al_completar(resultado)` (opcional) se ejecuta al terminar bien (p. ej. registrar
    en el historial). Solo un job a la vez (la sesión del agente es de un usuario).
    """
    if jobs.registry.hay_activo():
        raise HTTPException(
            status_code=409,
            detail="Ya hay una operación en curso. Espera a que termine o cancélala.",
        )
    job = jobs.registry.crear()
    pedir_captcha = jobs.registry.pedir_captcha_callback(job)
    jobs.registry.ejecutar(job, fn_factory(pedir_captcha), al_completar=al_completar)
    return {"job_id": job.id}


@app.post("/ciec/cfdi")
def ciec_cfdi(req: CIECDescargaRequest):
    """Descarga CFDIs vía CIEC como job (captcha in-app por SSE). → {job_id}."""
    from ..portal.cfdi import descargar_cfdi_ciec
    from ..core import paths

    ciec = _resolver_ciec(req.rfc, req.ciec)
    salida = str(paths.dir_cfdi_base(req.rfc, salida_base=_descargas_base()))

    def factory(pedir_captcha):
        def run():
            archivos = descargar_cfdi_ciec(
                rfc=req.rfc, ciec=ciec,
                fecha_inicio=req.fecha_inicio, fecha_fin=req.fecha_fin,
                tipo_comprobante=req.tipo_comprobante,
                directorio_salida=salida, max_registros=req.max_registros,
                pedir_captcha=pedir_captcha,
            )
            return {"metodo": "ciec", "total": len(archivos),
                    "archivos": [str(a) for a in archivos]}
        return run

    cuales = {"E": "emitidos", "R": "recibidos"}.get(req.tipo_comprobante, "")
    desc = f"CFDIs {cuales} · {req.fecha_inicio} a {req.fecha_fin}".replace("  ", " ")

    def al_completar(resultado):
        _registrar_descarga(req.rfc, "ciec", "cfdi", descripcion=desc,
                            ruta=salida, total=(resultado or {}).get("total"))

    return _lanzar_job_portal(factory, al_completar=al_completar)


@app.post("/ciec/constancia")
def ciec_constancia(req: ConstanciaRequest):
    """Descarga la Constancia de Situación Fiscal vía CIEC como job. → {job_id}."""
    from ..portal.constancia import descargar_constancia_ciec
    from ..core import paths

    ciec = _resolver_ciec(req.rfc, req.ciec)
    salida = str(paths.dir_documento(paths.TIPO_CONSTANCIA, req.rfc, salida_base=_descargas_base()))

    def factory(pedir_captcha):
        def run():
            pdf = descargar_constancia_ciec(
                rfc=req.rfc, ciec=ciec,
                directorio_salida=salida, pedir_captcha=pedir_captcha,
            )
            if not pdf:
                raise RuntimeError("No se pudo generar/descargar la constancia.")
            return {"archivo": str(pdf)}
        return run

    def al_completar(resultado):
        archivo = (resultado or {}).get("archivo", "")
        _registrar_descarga(req.rfc, "ciec", "constancia",
                            descripcion="Constancia de Situación Fiscal",
                            ruta=archivo)
        if archivo:
            from ..cli import config_store
            config_store.set_csf_descargada(req.rfc, archivo)

    return _lanzar_job_portal(factory, al_completar=al_completar)


@app.post("/ciec/opinion")
def ciec_opinion(req: OpinionRequest):
    """Descarga la Opinión de Cumplimiento 32-D vía CIEC como job. → {job_id}."""
    from ..portal.opinion import descargar_opinion_ciec
    from ..core import paths

    ciec = _resolver_ciec(req.rfc, req.ciec)
    salida = str(paths.dir_documento(paths.TIPO_OPINION, req.rfc, salida_base=_descargas_base()))

    def factory(pedir_captcha):
        def run():
            pdf = descargar_opinion_ciec(
                rfc=req.rfc, ciec=ciec,
                directorio_salida=salida, pedir_captcha=pedir_captcha,
            )
            if not pdf:
                raise RuntimeError("No se pudo generar/descargar la opinión 32-D.")
            return {"archivo": str(pdf)}
        return run

    def al_completar(resultado):
        archivo = (resultado or {}).get("archivo", "")
        _registrar_descarga(req.rfc, "ciec", "opinion",
                            descripcion="Opinión de Cumplimiento 32-D",
                            ruta=archivo)
        if archivo:
            from ..cli import config_store
            config_store.set_opinion_descargada(req.rfc, archivo)

    return _lanzar_job_portal(factory, al_completar=al_completar)


@app.post("/jobs/{job_id}/captcha")
def responder_captcha_job(job_id: str, body: CaptchaSolution):
    """Entrega la solución del captcha (o solution=null para cancelar el job)."""
    job = jobs.registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")
    jobs.registry.responder_captcha(job, body.solution)
    return {"ok": True}


@app.get("/jobs/{job_id}")
def estado_job(job_id: str):
    """Estado actual del job (estado, resultado, error)."""
    job = jobs.registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return {
        "id": job.id,
        "estado": job.estado,
        "resultado": jobs._serializable(job.resultado),
        "error": job.error,
    }


@app.get("/events/{job_id}")
def eventos_job(job_id: str):
    """Stream SSE del progreso del job (incluye `captcha_required`)."""
    job = jobs.registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return StreamingResponse(jobs.registry.stream(job), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Endpoints: documentos vía e.firma (FIEL en sesión; sin captcha)
# ---------------------------------------------------------------------------

@app.post("/constancia/fiel")
def constancia_fiel_endpoint():
    """Constancia de Situación Fiscal con la e.firma cargada en sesión."""
    from ..portal.constancia import descargar_constancia_fiel
    from ..core import paths

    _get_fiel()
    salida = str(paths.dir_documento(paths.TIPO_CONSTANCIA, _session["rfc"] or "", salida_base=_descargas_base()))
    try:
        pdf = descargar_constancia_fiel(
            cer_path=_session["cer_path"], key_path=_session["key_path"],
            password=_session["password"], directorio_salida=salida,
        )
        if not pdf:
            raise HTTPException(status_code=502, detail="No se pudo descargar la constancia.")
        _registrar_descarga(_session["rfc"] or "", "fiel", "constancia",
                            descripcion="Constancia de Situación Fiscal", ruta=str(pdf))
        if _session["rfc"]:
            from ..cli import config_store
            config_store.set_csf_descargada(_session["rfc"], str(pdf))
        return {"ok": True, "archivo": str(pdf)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/opinion/fiel")
def opinion_fiel_endpoint():
    """Opinión de Cumplimiento 32-D con la e.firma cargada en sesión."""
    from ..portal.opinion import descargar_opinion_fiel
    from ..core import paths

    _get_fiel()
    salida = str(paths.dir_documento(paths.TIPO_OPINION, _session["rfc"] or "", salida_base=_descargas_base()))
    try:
        pdf = descargar_opinion_fiel(
            cer_path=_session["cer_path"], key_path=_session["key_path"],
            password=_session["password"], directorio_salida=salida,
        )
        if not pdf:
            raise HTTPException(status_code=502, detail="No se pudo descargar la opinión 32-D.")
        _registrar_descarga(_session["rfc"] or "", "fiel", "opinion",
                            descripcion="Opinión de Cumplimiento 32-D", ruta=str(pdf))
        if _session["rfc"]:
            from ..cli import config_store
            config_store.set_opinion_descargada(_session["rfc"], str(pdf))
        return {"ok": True, "archivo": str(pdf)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/cfdi/fiel")
def cfdi_fiel(req: FIELCfdiRequest):
    """
    Descarga CFDIs vía portal con la e.firma en sesión como job (sin captcha).
    Mismo patrón que /ciec/cfdi pero el login es e.firma → no se emite
    `captcha_required` en el SSE. → {job_id}.
    """
    from ..portal.cfdi import descargar_cfdi_fiel
    from ..core import paths

    _get_fiel()
    rfc = _session["rfc"] or ""
    salida = str(paths.dir_cfdi_base(rfc, salida_base=_descargas_base()))

    def factory(pedir_captcha):  # pedir_captcha se ignora (FIEL no usa captcha)
        def run():
            archivos = descargar_cfdi_fiel(
                cer_path=_session["cer_path"], key_path=_session["key_path"],
                password=_session["password"],
                fecha_inicio=req.fecha_inicio, fecha_fin=req.fecha_fin,
                tipo_comprobante=req.tipo_comprobante,
                directorio_salida=salida, max_registros=req.max_registros,
            )
            return {"metodo": "fiel", "total": len(archivos),
                    "archivos": [str(a) for a in archivos]}
        return run

    cuales = {"E": "emitidos", "R": "recibidos"}.get(req.tipo_comprobante, "")
    desc = f"CFDIs {cuales} · {req.fecha_inicio} a {req.fecha_fin}".replace("  ", " ")

    def al_completar(resultado):
        _registrar_descarga(rfc, "fiel", "cfdi", descripcion=desc,
                            ruta=salida, total=(resultado or {}).get("total"))

    return _lanzar_job_portal(factory, al_completar=al_completar)


# ---------------------------------------------------------------------------
# Endpoints: catálogo de empresas (persistente; credenciales en keychain del SO)
# ---------------------------------------------------------------------------
#
# Reusa cli.config_store (capa de datos sin I/O de terminal): catálogo en
# ~/.sat-descarga/empresas.json + contraseñas en el keychain del SO (core.secretos).
# Así el usuario registra su e.firma/CIEC una vez y no las reingresa cada descarga.

@app.get("/empresas")
def empresas_list():
    """Lista las empresas registradas (sin credenciales)."""
    from ..cli import config_store
    return {"empresas": config_store.list_empresas()}


@app.post("/empresas/fiel")
async def empresas_add_fiel(
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    nombre: str = Form(...),
    rfc_esperado: Optional[str] = Form(None),
):
    """
    Registra una empresa por e.firma. La contraseña se guarda en el keychain.
    Si se manda `rfc_esperado` (al agregar e.firma a una empresa existente), se valida
    que el RFC del certificado coincida y se rechaza si es de otro contribuyente.
    """
    from ..cli import config_store

    cer_data = await cer_file.read()
    key_data = await key_file.read()
    cer_tmp = tempfile.NamedTemporaryFile(suffix=".cer", delete=False)
    key_tmp = tempfile.NamedTemporaryFile(suffix=".key", delete=False)
    try:
        cer_tmp.write(cer_data); cer_tmp.flush(); cer_tmp.close()
        key_tmp.write(key_data); key_tmp.flush(); key_tmp.close()
        rfc = config_store.add_empresa(
            nombre, cer_tmp.name, key_tmp.name, password, rfc_esperado=rfc_esperado,
        )
        return {"ok": True, "rfc": rfc}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"No se pudo registrar la empresa: {e}")
    finally:
        for p in (cer_tmp.name, key_tmp.name):
            try:
                os.unlink(p)
            except Exception:
                pass


@app.post("/empresas/ciec")
def empresas_add_ciec(req: EmpresaCiecRequest):
    """Registra una empresa por CIEC. La contraseña CIEC se guarda en el keychain."""
    from ..cli import config_store
    rfc = config_store.add_empresa_ciec(req.rfc, req.nombre, req.ciec)
    return {"ok": True, "rfc": rfc}


@app.delete("/empresas/{rfc}")
def empresas_remove(rfc: str):
    """Elimina la empresa del catálogo y borra sus credenciales del keychain."""
    from ..cli import config_store
    config_store.remove_empresa(rfc)
    return {"ok": True}


@app.post("/empresas/{rfc}/activar")
def empresas_activar(rfc: str):
    """
    Activa una empresa para la sesión. Para FIEL, carga la e.firma guardada en memoria
    (como /auth/cargar-fiel, pero desde el catálogo). Para CIEC no carga e.firma.
    """
    from ..cli import config_store
    try:
        empresa = config_store.get_empresa(rfc)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")

    metodos = empresa.get("metodos", [])
    try:
        cargada = _cargar_fiel_empresa(empresa)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:  # noqa: BLE001 — cert/llave/contraseña ilegibles
        raise HTTPException(status_code=400, detail=f"No se pudo cargar la e.firma: {e}")
    return {"ok": True, "rfc": rfc, "metodos": metodos, "efirma_lista": cargada}


@app.post("/empresas/{rfc}/default")
def empresas_default(rfc: str):
    """Marca la empresa como predeterminada (activa) del catálogo."""
    from ..cli import config_store
    try:
        config_store.set_default(rfc)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    return {"ok": True, "rfc": rfc}


@app.post("/empresas/{rfc}/archive")
def empresas_archive(rfc: str):
    """Soft-delete: archiva la empresa (la oculta de la lista principal)."""
    from ..cli import config_store
    try:
        config_store.archive_empresa(rfc)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    return {"ok": True, "rfc": rfc}


@app.post("/empresas/{rfc}/unarchive")
def empresas_unarchive(rfc: str):
    """Desarchiva la empresa (la regresa a la lista principal)."""
    from ..cli import config_store
    try:
        config_store.unarchive_empresa(rfc)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    return {"ok": True, "rfc": rfc}


@app.patch("/empresas/{rfc}")
def empresas_update(rfc: str, req: EmpresaUpdateRequest):
    """
    Actualiza campos editables de la empresa (regimenes_fiscales, actividades_economicas).
    Body parcial: solo los campos presentes (no nulos) se aplican.
    """
    from ..cli import config_store
    patch = req.model_dump(exclude_none=True)
    try:
        config_store.update_empresa(rfc, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "rfc": rfc}


@app.get("/empresas/{rfc}/solicitudes")
def empresas_solicitudes(rfc: str):
    """Historial de solicitudes de descarga de la empresa (más recientes primero)."""
    from ..cli import config_store
    return {"solicitudes": config_store.list_solicitudes(rfc)}


@app.delete("/empresas/{rfc}/solicitudes/{id_solicitud}")
def empresas_solicitudes_delete(rfc: str, id_solicitud: str):
    """Borra una solicitud del catálogo (solo limpia el registro local, no afecta al SAT)."""
    from ..cli import config_store
    borrada = config_store.delete_solicitud(rfc, id_solicitud)
    if not borrada:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"ok": True}


@app.get("/empresas/{rfc}/historial")
def empresas_historial(rfc: str):
    """Historial de descargas completadas de la empresa (más recientes primero)."""
    from ..cli import config_store
    return {"descargas": config_store.list_descargas(rfc)}


@app.get("/historial")
def historial():
    """Historial de descargas de TODAS las empresas (con rfc + nombre), recientes primero."""
    from ..cli import config_store
    return {"descargas": config_store.list_todas_descargas()}


def _abrir_en_so(path: str) -> None:
    """Abre `path` (archivo o carpeta) con el manejador por defecto del SO."""
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])
    elif sys.platform.startswith("win"):
        os.startfile(path)  # type: ignore[attr-defined]  # solo existe en Windows
    else:
        subprocess.Popen(["xdg-open", path])


@app.post("/abrir")
def abrir(req: AbrirRequest):
    """
    Abre en el SO una descarga del historial: su carpeta (`modo=carpeta`) o el
    archivo (`modo=archivo`, p. ej. el PDF de constancia/opinión).

    Seguridad: solo se permiten rutas que estén registradas en el historial
    (no se puede abrir una ruta arbitraria del disco).
    """
    from ..cli import config_store

    # Comparar rutas CANONICALIZADAS (resolve() normaliza ".." y sigue symlinks):
    # así un symlink o una variante de la misma ruta no brinca la lista blanca.
    rutas = set()
    for d in config_store.list_todas_descargas():
        if not d.get("ruta"):
            continue
        try:
            rutas.add(Path(d["ruta"]).resolve())
        except OSError:
            continue

    try:
        objetivo = Path(req.ruta).resolve()
    except OSError:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    if objetivo not in rutas:
        raise HTTPException(status_code=403, detail="Ruta no permitida (no está en el historial).")

    if req.modo == "carpeta" and objetivo.is_file():
        objetivo = objetivo.parent
    if not objetivo.exists():
        raise HTTPException(status_code=404, detail="La ruta ya no existe (¿se movió o borró?).")

    try:
        _abrir_en_so(str(objetivo))
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"No se pudo abrir: {e}")
    return {"ok": True, "ruta": str(objetivo)}


# ---------------------------------------------------------------------------
# Endpoints: ajustes (carpeta de descargas)
# ---------------------------------------------------------------------------

@app.get("/config/descargas-dir")
def get_descargas_dir_endpoint():
    """Carpeta base donde se guardan las descargas (se crea si no existe)."""
    from ..cli import config_store
    return {"dir": config_store.asegurar_descargas_dir()}


@app.put("/config/descargas-dir")
def set_descargas_dir_endpoint(req: DescargasDirRequest):
    """Cambia la carpeta base de descargas."""
    from ..cli import config_store
    return {"dir": config_store.set_descargas_dir(req.dir)}


# ---------------------------------------------------------------------------
# Procesador de comprobantes — CFDI
# ---------------------------------------------------------------------------
#
# Buffer persistente en SQLite (~/.sat-descarga/procesador.db). El usuario
# carga XMLs explícitamente (drag&drop / examinar carpeta / desde empresa);
# no se autoescanea el filesystem. Lo cargado se queda hasta que el usuario
# pulse "Borrar". Filtros también persisten para que la sesión se recupere
# al reabrir la app. Ver el plan en /Users/isca/.claude/plans para detalle.


class CargarDesdeEmpresaRequest(BaseModel):
    rfc: str
    desde: Optional[str] = None  # YYYY-MM-DD (inclusive)
    hasta: Optional[str] = None  # YYYY-MM-DD (inclusive)
    # 'E' (emitidos) o 'R' (recibidos). Cuando se omite, escanea ambos —
    # reservado para uso programático futuro (p. ej. una calculadora de IVA
    # que necesite cruzar el total emitido vs recibido del periodo).
    tipo: Optional[str] = None


class ValidarSatRequest(BaseModel):
    # Si se omite, valida solo los CFDIs del buffer sin estado_sat asignado.
    uuids: Optional[List[str]] = None


class ProcesadorFiltrosRequest(BaseModel):
    desde: Optional[str] = None
    hasta: Optional[str] = None
    tipo: Optional[str] = None
    direccion: Optional[str] = None  # 'E' | 'R' | None
    busqueda: Optional[str] = None
    solo_con_errores: Optional[bool] = False
    monto_min: Optional[float] = None
    monto_max: Optional[float] = None


def _filtros_de_query(
    desde: Optional[str],
    hasta: Optional[str],
    tipo: Optional[str],
    busqueda: Optional[str],
    solo_con_errores: bool,
    monto_min: Optional[float],
    monto_max: Optional[float],
    direccion: Optional[str] = None,
    emisor_lista_negra: Optional[str] = None,
) -> dict:
    """Construye el dict de filtros para `procesador.db`."""
    return {
        "desde": desde,
        "hasta": hasta,
        "tipo": tipo,
        "direccion": direccion,
        "busqueda": busqueda,
        "solo_con_errores": bool(solo_con_errores),
        "monto_min": monto_min,
        "monto_max": monto_max,
        "emisor_lista_negra": emisor_lista_negra,
    }


def _rfc_activo() -> Optional[str]:
    """Devuelve el RFC de la empresa activa (sesión FIEL o catálogo)."""
    rfc = _session.get("rfc") if isinstance(_session, dict) else None
    if rfc:
        return rfc
    try:
        from ..cli import config_store
        return config_store.get_default()
    except Exception:
        return None


@app.post("/procesador/cfdi/cargar")
async def procesador_cargar(files: List[UploadFile] = File(...)):
    """
    Recibe `.xml` por multipart y los agrega al buffer del procesador.
    Hasta `MAX_BATCH_SIZE` archivos por request.
    """
    from ..procesador import abrir_db, parse_cfdi, MAX_BATCH_SIZE
    from ..procesador.cfdi_parser import CfdiParseError
    from ..procesador.validaciones import validar_y_anotar

    if len(files) > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"Demasiados archivos en un batch (máx {MAX_BATCH_SIZE})",
        )

    db = abrir_db()
    parseados = []
    errores: list[dict] = []

    for f in files:
        try:
            contenido = await f.read()
            cfdi = parse_cfdi(contenido, file_name=f.filename or "")
            validar_y_anotar(cfdi)
            parseados.append(cfdi)
        except CfdiParseError as e:
            errores.append({"filename": f.filename, "mensaje": str(e)})
        except Exception as e:  # noqa: BLE001
            logger.exception("[procesador] error parseando %s", f.filename)
            errores.append({"filename": f.filename, "mensaje": str(e)})

    # Drag&drop: la dirección se infiere comparando con el RFC activo.
    resultado = db.agregar(parseados, mi_rfc=_rfc_activo())
    return {
        "agregados": resultado["agregados"],
        "duplicados": resultado["duplicados"],
        "errores": errores,
    }


@app.post("/procesador/cfdi/cargar-desde-empresa")
def procesador_cargar_desde_empresa(req: CargarDesdeEmpresaRequest):
    """
    Escanea `descargas/cfdi/<RFC>/.../*.xml` filtrando por fecha (opcional)
    y agrega los CFDIs encontrados al buffer.
    """
    from ..procesador import abrir_db, parse_cfdi
    from ..procesador.cfdi_parser import CfdiParseError
    from ..procesador.validaciones import validar_y_anotar
    from ..core import paths

    base = paths.dir_cfdi_base(req.rfc, salida_base=_descargas_base())
    if not base.exists():
        return {"agregados": 0, "duplicados": 0, "errores": [], "archivos_encontrados": 0}

    # Filtrar por subcarpeta según el tipo solicitado. Si el caller omite
    # `tipo`, escanea ambos (uso programático futuro).
    if req.tipo == "E":
        scan_dirs = [base / "emitidos"]
    elif req.tipo == "R":
        scan_dirs = [base / "recibidos"]
    else:
        scan_dirs = [base]

    xmls: list = []
    for d in scan_dirs:
        if d.exists():
            xmls.extend(d.rglob("*.xml"))

    db = abrir_db()
    parseados = []
    errores: list[dict] = []

    desde = req.desde or ""
    hasta = req.hasta + "T23:59:59" if req.hasta else ""

    for xml_path in xmls:
        try:
            contenido = xml_path.read_bytes()
            cfdi = parse_cfdi(contenido, file_name=xml_path.name)
            # Filtro de fecha post-parseo (la fecha real vive en el XML)
            if desde and cfdi.fecha_emision and cfdi.fecha_emision < desde:
                continue
            if hasta and cfdi.fecha_emision and cfdi.fecha_emision > hasta:
                continue
            validar_y_anotar(cfdi)
            parseados.append(cfdi)
        except CfdiParseError as e:
            errores.append({"filename": xml_path.name, "mensaje": str(e)})
        except Exception as e:  # noqa: BLE001
            logger.exception("[procesador] error parseando %s", xml_path.name)
            errores.append({"filename": xml_path.name, "mensaje": str(e)})

    # En "cargar-desde-empresa" la dirección está implícita por el `tipo`
    # solicitado (E/R) — se la pasamos directa y de paso usamos `mi_rfc` como
    # respaldo si `tipo` viene en None.
    resultado = db.agregar(
        parseados,
        mi_rfc=req.rfc,
        direccion_fija=req.tipo if req.tipo in ("E", "R") else None,
    )
    return {
        "agregados": resultado["agregados"],
        "duplicados": resultado["duplicados"],
        "errores": errores,
        "archivos_encontrados": len(xmls),
    }


@app.post("/procesador/cfdi/validar-sat")
def procesador_validar_sat(req: ValidarSatRequest):
    """
    Valida contra el endpoint público del SAT los CFDIs indicados (o todos los
    que no tengan `estado_sat` aún). Actualiza la columna correspondiente y
    devuelve un summary por estado.
    """
    from ..procesador import abrir_db
    from ..utils.validacion import validar_masivo

    db = abrir_db()

    if req.uuids:
        uuids = req.uuids
    else:
        uuids = db.uuids_sin_validar()

    if not uuids:
        return {"validados": 0, "vigentes": 0, "cancelados": 0,
                "no_encontrados": 0, "errores": 0}

    # Construye payloads para validar_masivo
    payloads = []
    with db.cursor() as cur:
        placeholders = ",".join("?" for _ in uuids)
        cur.execute(
            f"""
            SELECT uuid, emisor_rfc, receptor_rfc, total
            FROM cfdis WHERE uuid IN ({placeholders})
            """,
            uuids,
        )
        for r in cur.fetchall():
            payloads.append({
                "uuid": r["uuid"],
                "emisor_rfc": r["emisor_rfc"] or "",
                "receptor_rfc": r["receptor_rfc"] or "",
                "total": r["total"] or 0.0,
            })

    resultados = validar_masivo(payloads, concurrency=10)

    contadores = {"vigentes": 0, "cancelados": 0, "no_encontrados": 0, "errores": 0}
    for est in resultados:
        estado = (est.estado or "").strip()
        if estado.lower().startswith("vigente"):
            contadores["vigentes"] += 1
            db.actualizar_estado_sat(est.uuid, "Vigente")
        elif estado.lower().startswith("cancel"):
            contadores["cancelados"] += 1
            db.actualizar_estado_sat(est.uuid, "Cancelado")
        elif estado.lower().startswith("no encontrado") or estado.lower().startswith("not"):
            contadores["no_encontrados"] += 1
            db.actualizar_estado_sat(est.uuid, "No encontrado")
        else:
            contadores["errores"] += 1

    return {"validados": len(resultados), **contadores}


@app.get("/procesador/cfdi")
def procesador_listar(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    direccion: Optional[str] = None,
    busqueda: Optional[str] = None,
    solo_con_errores: bool = False,
    monto_min: Optional[float] = None,
    monto_max: Optional[float] = None,
    emisor_lista_negra: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """Lista paginada del buffer del procesador con filtros."""
    from ..procesador import abrir_db
    filtros = _filtros_de_query(
        desde, hasta, tipo, busqueda, solo_con_errores, monto_min, monto_max,
        direccion, emisor_lista_negra,
    )
    db = abrir_db()
    return db.listar(filtros, page=page, page_size=page_size)


@app.get("/procesador/cfdi/stats")
def procesador_stats(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    direccion: Optional[str] = None,
    busqueda: Optional[str] = None,
    solo_con_errores: bool = False,
    monto_min: Optional[float] = None,
    monto_max: Optional[float] = None,
):
    """KPIs agregados (stats cards)."""
    from ..procesador import abrir_db
    from ..procesador.reportes_cfdi import stats_generales
    filtros = _filtros_de_query(
        desde, hasta, tipo, busqueda, solo_con_errores, monto_min, monto_max, direccion,
    )
    return stats_generales(abrir_db(), filtros)


@app.get("/procesador/cfdi/reporte/{nombre}")
def procesador_reporte(
    nombre: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    direccion: Optional[str] = None,
    busqueda: Optional[str] = None,
    solo_con_errores: bool = False,
    monto_min: Optional[float] = None,
    monto_max: Optional[float] = None,
):
    """Reportes específicos: `totales-mes`, `top-contrapartes`, `integridad`."""
    from ..procesador import abrir_db
    from ..procesador import reportes_cfdi as rep

    filtros = _filtros_de_query(
        desde, hasta, tipo, busqueda, solo_con_errores, monto_min, monto_max, direccion,
    )
    db = abrir_db()
    if nombre == "totales-mes":
        return {"reporte": "totales-mes", "items": rep.totales_por_mes(db, filtros)}
    if nombre == "top-contrapartes":
        return {"reporte": "top-contrapartes", **rep.top_contrapartes(db, filtros)}
    if nombre == "integridad":
        return {"reporte": "integridad", "items": rep.integridad(db, filtros)}
    raise HTTPException(status_code=404, detail=f"Reporte desconocido: {nombre}")


@app.get("/procesador/cfdi/filtros")
def procesador_filtros_get():
    from ..procesador import abrir_db
    return abrir_db().filtros_get()


@app.put("/procesador/cfdi/filtros")
def procesador_filtros_set(req: ProcesadorFiltrosRequest):
    from ..procesador import abrir_db
    db = abrir_db()
    db.filtros_set(req.dict())
    return {"ok": True}


@app.delete("/procesador/cfdi")
def procesador_borrar():
    """Vacía el buffer completo (CFDIs + filtros)."""
    from ..procesador import abrir_db
    abrir_db().borrar()
    return {"ok": True}


@app.get("/procesador/cfdi/exportar")
def procesador_exportar(
    formato: str = "xlsx",
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    direccion: Optional[str] = None,
    busqueda: Optional[str] = None,
    solo_con_errores: bool = False,
    monto_min: Optional[float] = None,
    monto_max: Optional[float] = None,
):
    """Descarga el buffer filtrado como XLSX o CSV."""
    from ..procesador import abrir_db
    from ..procesador.exportar import to_csv, to_xlsx

    filtros = _filtros_de_query(
        desde, hasta, tipo, busqueda, solo_con_errores, monto_min, monto_max, direccion,
    )
    db = abrir_db()

    if formato == "xlsx":
        data = to_xlsx(db, filtros)
        return StreamingResponse(
            iter([data]),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": 'attachment; filename="cfdis.xlsx"'},
        )
    if formato == "csv":
        data = to_csv(db, filtros)
        return StreamingResponse(
            iter([data]),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": 'attachment; filename="cfdis.csv"'},
        )
    raise HTTPException(status_code=400, detail=f"Formato no soportado: {formato}")


# ---------------------------------------------------------------------------
# Listas negras del SAT (Art. 69 y 69-B)
# ---------------------------------------------------------------------------
#
# Consume la API de todoconta-apps (Vercel cron mensual → Supabase). La fuente
# de verdad vive en un solo lugar; aquí solo consultamos y persistimos el
# último resultado por RFC en el buffer del procesador para filtrar/ordenar.
#
# Requiere sesión iniciada (Bearer en keyring). Sin sesión → 401.


class ListasNegrasConsultarRequest(BaseModel):
    rfcs: List[str]


class ValidarListasNegrasRequest(BaseModel):
    # Si se omite, valida todos los RFCs del buffer cuya última validación
    # esté fuera del TTL (30 días). `force_refresh=true` ignora el TTL.
    uuids: Optional[List[str]] = None
    force_refresh: bool = False


def _match_to_payload(m) -> dict:
    """Serializa un MatchListaNegra al shape que consume la UI."""
    return {
        "rfc": m.rfc,
        "en_lista_69b": m.en_lista_69b,
        "situacion_69b": m.situacion_69b,
        "fecha_publicacion_69b": m.fecha_publicacion_69b,
        "en_lista_69": m.en_lista_69,
        "supuestos_69": m.supuestos_69,
        "risk_level": m.risk_level,
        "error": m.error,
    }


def _metadata_to_payload(meta) -> dict:
    return {
        "lista_69b_updated_at": meta.lista_69b_updated_at,
        "lista_69_updated_at": meta.lista_69_updated_at,
        "record_count_69b": meta.record_count_69b,
        "record_count_69": meta.record_count_69,
    }


@app.post("/listas-negras/consultar")
def listas_negras_consultar(req: ListasNegrasConsultarRequest):
    """Consulta ad-hoc de RFCs contra las listas negras. No toca SQLite.

    Útil para la pestaña "Validar RFCs" de la UI: el usuario pega/sube
    una lista y obtiene el veredicto sin tener XMLs cargados.
    """
    from ..utils.listas_negras import consultar_rfcs

    if not req.rfcs:
        raise HTTPException(status_code=400, detail="La lista de RFCs está vacía.")
    try:
        matches, metadata = consultar_rfcs(req.rfcs)
    except RuntimeError as e:
        # Sin sesión / sesión expirada / error de red
        msg = str(e)
        status = 401 if "Sesión" in msg or "sesión" in msg else 502
        raise HTTPException(status_code=status, detail=msg)
    return {
        "matches": [_match_to_payload(m) for m in matches],
        "metadata": _metadata_to_payload(metadata),
    }


@app.get("/listas-negras/metadata")
def listas_negras_metadata():
    """Cuándo se actualizaron por última vez las listas en el origen.

    La UI lo muestra como chip "Listas al 2026-06-05" y enseña una advertencia
    si pasaron > 35 días sin refresh (el cron normal es mensual).
    """
    from ..utils.listas_negras import consultar_metadata

    try:
        metadata = consultar_metadata()
    except RuntimeError as e:
        msg = str(e)
        status = 401 if "Sesión" in msg or "sesión" in msg else 502
        raise HTTPException(status_code=status, detail=msg)
    return _metadata_to_payload(metadata)


@app.post("/procesador/cfdi/validar-listas-negras")
def procesador_validar_listas_negras(req: ValidarListasNegrasRequest):
    """Valida los RFCs del buffer contra listas negras y persiste por fila.

    Si `req.uuids` viene, restringe a los RFCs (emisor + receptor) de esos
    CFDIs; si no, usa el universo del buffer respetando TTL (30 días) salvo
    `force_refresh=true`.
    """
    from ..utils.listas_negras import consultar_rfcs, clasificar, match_to_json_dict
    from ..procesador import abrir_db
    import json as _json

    db = abrir_db()

    if req.uuids:
        # RFCs únicos de los CFDIs solicitados (ambos lados).
        with db.cursor() as cur:
            placeholders = ",".join("?" for _ in req.uuids)
            cur.execute(
                f"""
                SELECT DISTINCT rfc FROM (
                  SELECT emisor_rfc AS rfc FROM cfdis WHERE uuid IN ({placeholders})
                  UNION
                  SELECT receptor_rfc AS rfc FROM cfdis WHERE uuid IN ({placeholders})
                ) WHERE rfc IS NOT NULL AND rfc != ''
                """,
                (*req.uuids, *req.uuids),
            )
            rfcs = [r[0] for r in cur.fetchall()]
    else:
        rfcs = db.rfcs_sin_validar_listas(force_refresh=req.force_refresh)

    if not rfcs:
        return {
            "validados": 0, "efos": 0, "aclarados": 0, "lista_69": 0, "limpios": 0,
            "metadata": {
                "lista_69b_updated_at": None, "lista_69_updated_at": None,
                "record_count_69b": None, "record_count_69": None,
            },
        }

    try:
        matches, metadata = consultar_rfcs(rfcs)
    except RuntimeError as e:
        msg = str(e)
        status = 401 if "Sesión" in msg or "sesión" in msg else 502
        raise HTTPException(status_code=status, detail=msg)

    contadores = {"efos": 0, "aclarados": 0, "lista_69": 0, "limpios": 0}
    for m in matches:
        etiqueta = clasificar(m)
        db.actualizar_lista_negra_rfc(
            m.rfc, etiqueta, _json.dumps(match_to_json_dict(m), ensure_ascii=False),
        )
        if etiqueta == "EFOS":
            contadores["efos"] += 1
        elif etiqueta == "Aclarado":
            contadores["aclarados"] += 1
        elif etiqueta == "69":
            contadores["lista_69"] += 1
        else:
            contadores["limpios"] += 1

    return {
        "validados": len(matches),
        **contadores,
        "metadata": _metadata_to_payload(metadata),
    }


@app.get("/procesador/cfdi/listas-negras/stats")
def procesador_listas_negras_stats(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    direccion: Optional[str] = None,
    busqueda: Optional[str] = None,
    solo_con_errores: bool = False,
    monto_min: Optional[float] = None,
    monto_max: Optional[float] = None,
):
    """KPIs (EFOS / EDOS / aclarados / 69 / limpios / sin validar) sobre el
    buffer filtrado. Usa los mismos filtros del procesador CFDI."""
    from ..procesador import abrir_db

    filtros = _filtros_de_query(
        desde, hasta, tipo, busqueda, solo_con_errores, monto_min, monto_max, direccion,
    )
    return abrir_db().stats_listas_negras(filtros)


@app.get("/procesador/cfdi/listas-negras/por-emisor")
def procesador_listas_negras_por_emisor(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    tipo: Optional[str] = None,
    direccion: Optional[str] = None,
    busqueda: Optional[str] = None,
    solo_con_errores: bool = False,
    monto_min: Optional[float] = None,
    monto_max: Optional[float] = None,
    emisor_lista_negra: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
):
    """Lista paginada agregada por `emisor_rfc` con total acumulado y conteo
    de CFDIs. Para la vista de listas negras donde lo accionable es por
    proveedor, no por comprobante individual."""
    from ..procesador import abrir_db

    filtros = _filtros_de_query(
        desde, hasta, tipo, busqueda, solo_con_errores, monto_min, monto_max,
        direccion, emisor_lista_negra,
    )
    return abrir_db().listar_emisores_listas_negras(filtros, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Procesador de comprobantes — Pagos
# ---------------------------------------------------------------------------
#
# Vista especializada sobre el buffer compartido `cfdis` + tabla
# `pagos_relaciones` (migración 004). Relaciona PPD ↔ complemento, detecta
# huérfanos, extemporáneos e incidencias PUE+complemento. NO tiene endpoints
# de cargar/borrar — los XMLs entran por `/procesador/cfdi/cargar`.


class PagosFiltrosRequest(BaseModel):
    desde: Optional[str] = None
    hasta: Optional[str] = None
    busqueda: Optional[str] = None
    status: Optional[List[str]] = None  # ['sin_complemento', 'pago_parcial', ...]
    solo_extemporaneos: Optional[bool] = False


def _filtros_pagos_de_query(
    desde: Optional[str],
    hasta: Optional[str],
    busqueda: Optional[str],
) -> dict:
    return {"desde": desde, "hasta": hasta, "busqueda": busqueda}


@app.get("/procesador/pagos")
def procesador_pagos_listar(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
    status: Optional[str] = None,  # CSV: "sin_complemento,pago_parcial"
    page: int = 1,
    page_size: int = 50,
):
    """Facturas PPD paginadas con status calculado."""
    from ..procesador import abrir_db
    from ..procesador import reportes_pagos as rep

    filtros = _filtros_pagos_de_query(desde, hasta, busqueda)
    status_list = [s for s in (status or "").split(",") if s] or None
    return rep.facturas_ppd(
        abrir_db(), filtros, status_in=status_list, page=page, page_size=page_size,
    )


@app.get("/procesador/pagos/stats")
def procesador_pagos_stats(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
):
    from ..procesador import abrir_db
    from ..procesador.reportes_pagos import stats_pagos
    filtros = _filtros_pagos_de_query(desde, hasta, busqueda)
    return stats_pagos(abrir_db(), filtros)


@app.get("/procesador/pagos/factura/{uuid}/pagos")
def procesador_pagos_detalle_factura(uuid: str):
    """Drilldown: pagos asociados a una factura PPD específica."""
    from ..procesador import abrir_db
    from ..procesador.reportes_pagos import detalle_pagos_de_ppd
    return {"uuid": uuid, "items": detalle_pagos_de_ppd(abrir_db(), uuid)}


@app.get("/procesador/pagos/reporte/{nombre}")
def procesador_pagos_reporte(
    nombre: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
):
    """Reportes: `analisis-fechas`, `huerfanos`, `incidencias-pue`."""
    from ..procesador import abrir_db
    from ..procesador import reportes_pagos as rep

    filtros = _filtros_pagos_de_query(desde, hasta, busqueda)
    db = abrir_db()
    if nombre == "analisis-fechas":
        return {"reporte": "analisis-fechas", "items": rep.analisis_fechas(db, filtros)}
    if nombre == "huerfanos":
        return {"reporte": "huerfanos", "items": rep.pagos_huerfanos(db, filtros)}
    if nombre == "incidencias-pue":
        return {"reporte": "incidencias-pue", "items": rep.incidencias_pue(db, filtros)}
    raise HTTPException(status_code=404, detail=f"Reporte desconocido: {nombre}")


@app.get("/procesador/pagos/filtros")
def procesador_pagos_filtros_get():
    from ..procesador import abrir_db
    f = abrir_db().filtros_get(key="pagos_actuales")
    # Default explicito si nunca se han guardado.
    return f or {
        "desde": None, "hasta": None, "busqueda": None,
        "status": None, "solo_extemporaneos": False,
    }


@app.put("/procesador/pagos/filtros")
def procesador_pagos_filtros_set(req: PagosFiltrosRequest):
    from ..procesador import abrir_db
    abrir_db().filtros_set(req.dict(), key="pagos_actuales")
    return {"ok": True}


@app.get("/procesador/pagos/exportar")
def procesador_pagos_exportar(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
):
    """XLSX multi-sheet del procesador de Pagos."""
    from ..procesador import abrir_db
    from ..procesador.exportar_pagos import to_xlsx
    filtros = _filtros_pagos_de_query(desde, hasta, busqueda)
    data = to_xlsx(abrir_db(), filtros)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="pagos.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Procesador de comprobantes — Nómina
# ---------------------------------------------------------------------------
#
# Vista especializada sobre el buffer compartido `cfdis` + tablas
# `nomina_recibos` y `nomina_conceptos` (migración 005). 3 reportes:
# Deductibilidad fiscal, Conciliación IMSS, Periodo vs Periodo.
# NO tiene endpoints de cargar/borrar — los XMLs entran por `/procesador/cfdi/cargar`
# y el borrado por `/procesador/cfdi/borrar`.


class NominaFiltrosRequest(BaseModel):
    desde: Optional[str] = None
    hasta: Optional[str] = None
    busqueda: Optional[str] = None
    tipo_nomina: Optional[str] = None        # 'O' | 'E'
    periodicidad: Optional[str] = None
    solo_con_errores: Optional[bool] = False


def _filtros_nomina_de_query(
    desde: Optional[str],
    hasta: Optional[str],
    busqueda: Optional[str],
    tipo_nomina: Optional[str],
    periodicidad: Optional[str],
    solo_con_errores: bool,
) -> dict:
    return {
        "desde": desde,
        "hasta": hasta,
        "busqueda": busqueda,
        "tipo_nomina": tipo_nomina,
        "periodicidad": periodicidad,
        "solo_con_errores": solo_con_errores,
    }


@app.get("/procesador/nomina")
def procesador_nomina_listar(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
    tipo_nomina: Optional[str] = None,
    periodicidad: Optional[str] = None,
    solo_con_errores: bool = False,
    page: int = 1,
    page_size: int = 50,
):
    """Recibos paginados (1 fila por CFDI tipo N)."""
    from ..procesador import abrir_db
    from ..procesador.reportes_nomina import listar_recibos

    filtros = _filtros_nomina_de_query(
        desde, hasta, busqueda, tipo_nomina, periodicidad, solo_con_errores,
    )
    return listar_recibos(abrir_db(), filtros, page=page, page_size=page_size)


@app.get("/procesador/nomina/stats")
def procesador_nomina_stats(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
    tipo_nomina: Optional[str] = None,
    periodicidad: Optional[str] = None,
    solo_con_errores: bool = False,
):
    from ..procesador import abrir_db
    from ..procesador.reportes_nomina import stats_nomina

    filtros = _filtros_nomina_de_query(
        desde, hasta, busqueda, tipo_nomina, periodicidad, solo_con_errores,
    )
    return stats_nomina(abrir_db(), filtros)


@app.get("/procesador/nomina/recibo/{uuid}/conceptos")
def procesador_nomina_conceptos_de_recibo(uuid: str):
    """Drilldown: conceptos de un recibo de nómina ordenados por clase."""
    from ..procesador import abrir_db
    from ..procesador.reportes_nomina import conceptos_de_recibo
    return {"uuid": uuid, "items": conceptos_de_recibo(abrir_db(), uuid)}


@app.get("/procesador/nomina/reporte/{nombre}")
def procesador_nomina_reporte(
    nombre: str,
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
    tipo_nomina: Optional[str] = None,
    periodicidad: Optional[str] = None,
    solo_con_errores: bool = False,
):
    """Reportes: 'deducibilidad' | 'imss' | 'periodo-vs-periodo'."""
    from ..procesador import abrir_db
    from ..procesador import reportes_nomina as rep

    filtros = _filtros_nomina_de_query(
        desde, hasta, busqueda, tipo_nomina, periodicidad, solo_con_errores,
    )
    db = abrir_db()
    if nombre == "deducibilidad":
        return rep.reporte_deducibilidad(db, filtros)
    if nombre == "imss":
        return rep.reporte_imss(db, filtros)
    if nombre == "periodo-vs-periodo":
        return rep.reporte_periodo_vs_periodo(db, filtros)
    raise HTTPException(status_code=404, detail=f"Reporte desconocido: {nombre}")


@app.get("/procesador/nomina/filtros")
def procesador_nomina_filtros_get():
    from ..procesador import abrir_db
    f = abrir_db().filtros_get(key="nomina_actuales")
    return f or {
        "desde": None, "hasta": None, "busqueda": None,
        "tipo_nomina": None, "periodicidad": None, "solo_con_errores": False,
    }


@app.put("/procesador/nomina/filtros")
def procesador_nomina_filtros_set(req: NominaFiltrosRequest):
    from ..procesador import abrir_db
    abrir_db().filtros_set(req.dict(), key="nomina_actuales")
    return {"ok": True}


@app.get("/procesador/nomina/exportar")
def procesador_nomina_exportar(
    desde: Optional[str] = None,
    hasta: Optional[str] = None,
    busqueda: Optional[str] = None,
    tipo_nomina: Optional[str] = None,
    periodicidad: Optional[str] = None,
    solo_con_errores: bool = False,
):
    """XLSX multi-sheet del procesador de Nómina (con disclaimer fiscal)."""
    from ..procesador import abrir_db
    from ..procesador.exportar_nomina import to_xlsx

    filtros = _filtros_nomina_de_query(
        desde, hasta, busqueda, tipo_nomina, periodicidad, solo_con_errores,
    )
    data = to_xlsx(abrir_db(), filtros)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="nomina.xlsx"'},
    )


# ---------------------------------------------------------------------------
# Auth desktop — proxy + cache hacia todoconta-apps (/api/desktop/*)
# ---------------------------------------------------------------------------
#
# La desktop guarda el Bearer token de Supabase en el keyring del SO (vía
# `license_client`) y expone helpers al renderer para login, license check
# y upgrade a Fundador. El Bearer NUNCA se inyecta al renderer — vive solo
# en el proceso Python; el renderer solo conoce el estado derivado (autenticado,
# is_founder, etc.). Esto reduce la superficie de un XSS en el renderer.


class AuthPollRequest(BaseModel):
    device_code: str


@app.post("/auth/init")
def auth_init():
    """
    Genera un device_code y lo registra en el backend de todoconta-apps.
    Devuelve el code + el URL público que el usuario tiene que abrir.
    """
    from . import license_client as lc

    code = lc.generate_device_code()
    try:
        result = lc.init_device_code(code)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return {
        "device_code": code,
        "expires_at": result.get("expires_at"),
        "activate_url": f"{lc.API_BASE_URL}/desktop/activate?code={code}",
    }


@app.post("/auth/poll")
def auth_poll(req: AuthPollRequest):
    """
    Polling del device_code. Devuelve `{status, ...}` con:
      - status=pending → el usuario aún no completó.
      - status=ok      → activado, sesión guardada en keyring.
      - status=expired → device_code expirado.
      - status=not_found → device_code desconocido.
    """
    from . import license_client as lc

    try:
        result, session = lc.poll_device_code(req.device_code)
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))

    if result == "ok" and session is not None:
        lc.save_session(session)
        # Invalidamos el cache de license para que la próxima lectura
        # refleje al usuario recién logueado.
        lc.clear_license_cache()
        return {"status": "ok", "user": {"id": session.user_id, "email": session.email}}

    return {"status": result}


@app.get("/auth/license")
def auth_license(refresh: bool = False):
    """
    Estado de licencia/fundador del usuario actual. Si no hay sesión:
    `{authenticated: false}`. Si hay y la cache es fresh, la devuelve sin
    pegarle al backend.
    """
    from . import license_client as lc

    return lc.get_license_status(force_refresh=refresh)


@app.post("/auth/upgrade")
def auth_upgrade():
    """
    Crea una sesión de Stripe Checkout para que el usuario se vuelva Fundador.
    Devuelve `{url}`; el renderer abre el URL en el navegador del SO.
    """
    from . import license_client as lc

    session = lc.load_session()
    if session is None:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        result = lc.init_checkout(session)
    except PermissionError:
        # Sesión expirada: limpiamos y obligamos a re-login.
        lc.clear_session()
        raise HTTPException(status_code=401, detail="Sesión expirada, vuelve a iniciar sesión")
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))
    return result


@app.post("/auth/logout")
def auth_logout():
    """Borra la sesión local (keyring + cache). Idempotente."""
    from . import license_client as lc

    lc.clear_session()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def start(port: int = 8787, host: str = "127.0.0.1"):
    """
    Inicia el servidor FastAPI local.

    Llamado automáticamente cuando el app de escritorio (Electron) levanta
    el proceso Python. La app web se conecta a http://localhost:8787.
    """
    try:
        import uvicorn
    except ImportError:
        raise ImportError(
            "uvicorn no está instalado. Ejecuta:\n"
            "  pip install uvicorn[standard]"
        )

    logger.info("Iniciando SAT Descarga Masiva en http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    start()

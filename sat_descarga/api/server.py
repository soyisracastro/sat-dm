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
    # Al arrancar el agente, carga la e.firma de la empresa activa para que
    # "empresa activa" y "e.firma en sesión" estén sincronizadas desde el inicio
    # (si no, la cabecera/Dashboard muestran "Sin e-firma" hasta cargarla a mano).
    _autocargar_empresa_default()
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

# Orígenes permitidos: la app web en producción y en desarrollo local
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://app.todoconta.com",
        "https://todoconta.com",
    ],
    allow_credentials=True,
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


class DescargasDirRequest(BaseModel):
    dir: str


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
        )
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
    directorio_salida: str = "./cfdi/",
    extraer: bool = True,
):
    """
    Descarga los paquetes de una solicitud ya terminada (cod_estado=3).

    Llama primero a /verificar para confirmar que la solicitud está lista.
    """
    from ..webservice.descarga import descargar_todos

    fiel = _get_fiel()
    token = _renovar_token()

    # Verificar estado actual
    try:
        estado = verificar_solicitud(
            token=token,
            rfc_solicitante=fiel.rfc,
            id_solicitud=id_solicitud,
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
            directorio_salida=directorio_salida,
            extraer=extraer,
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


def _lanzar_ciec(fn_factory):
    """
    Crea un job CIEC, inyecta el callback de captcha del bridge y lo corre en un
    worker thread. `fn_factory(pedir_captcha)` devuelve el callable del scrape.
    Solo un job CIEC a la vez (la sesión del agente es de un usuario).
    """
    if jobs.registry.hay_activo():
        raise HTTPException(
            status_code=409,
            detail="Ya hay una operación en curso. Espera a que termine o cancélala.",
        )
    job = jobs.registry.crear()
    pedir_captcha = jobs.registry.pedir_captcha_callback(job)
    jobs.registry.ejecutar(job, fn_factory(pedir_captcha))
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

    return _lanzar_ciec(factory)


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

    return _lanzar_ciec(factory)


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

    return _lanzar_ciec(factory)


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
        return {"ok": True, "archivo": str(pdf)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


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


@app.get("/empresas/{rfc}/solicitudes")
def empresas_solicitudes(rfc: str):
    """Historial de solicitudes de descarga de la empresa (más recientes primero)."""
    from ..cli import config_store
    return {"solicitudes": config_store.list_solicitudes(rfc)}


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

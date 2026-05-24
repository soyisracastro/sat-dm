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
    uvicorn sat_descarga.server:app --port 8787 --host 127.0.0.1

    O desde código:
        from sat_descarga.server import start
        start()
"""

import logging
import os
import tempfile
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
    from pydantic import BaseModel
except ImportError:
    raise ImportError(
        "fastapi no está instalado. Ejecuta:\n"
        "  pip install fastapi uvicorn[standard]"
    )

from .fiel import FIEL
from .auth import obtener_token
from .solicitud import solicitar_descarga
from .verificacion import verificar_solicitud
from .validacion import validar_masivo, EstadoCFDI
from .config import TIPO_CFDI, TIPO_METADATA, TIPO_EMITIDO, TIPO_RECIBIDO

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="SAT Descarga Masiva — Agente Local",
    description=(
        "Servidor local para descargar CFDIs del SAT sin exponer la e-firma. "
        "La e-firma nunca sale de tu máquina."
    ),
    version="1.0.0",
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
    "cer_path": None,    # Path al .cer temporal
    "key_path": None,    # Path al .key temporal
    "password": None,    # Contraseña de la llave (en memoria, no en disco)
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
    ciec: str
    fecha_inicio: date
    fecha_fin: date
    tipo_comprobante: str = TIPO_RECIBIDO
    directorio_salida: str = "./cfdi/"
    max_registros: int = 500


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
    """Verifica que el servidor está corriendo y si hay e-firma cargada."""
    return {
        "status": "ok",
        "rfc_cargado": _session["rfc"],
        "efirma_lista": _session["fiel"] is not None,
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
    """Limpia el estado de sesión y borra archivos temporales."""
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
    })


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
    from .descarga import descargar_todos

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
    from .client import descargar_cfdi

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
    from .client import descargar_por_uuid

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
    from .client import descargar_metadata
    from .metadata import metadata_to_dicts

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
    from .organizador import organizar

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
    from .organizador import renombrar

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
    from .organizador import eliminar_duplicados

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
    from .client import descargar_cfdi_inteligente

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
    from .ciec import descargar_cfdi_ciec

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

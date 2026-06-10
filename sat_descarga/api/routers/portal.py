"""
Router: portal del SAT (scraping con Playwright) — CIEC y e.firma.

Endpoints: /ciec/descargar, /constancia/descargar (síncronos), los jobs
/ciec/{cfdi,constancia,opinion} y /cfdi/fiel (SSE + captcha vía /jobs/* y
/events/*), y los documentos síncronos /constancia/fiel y /opinion/fiel.
"""

from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import jobs
from ...core.config import TIPO_RECIBIDO
from ..state import _session, _get_fiel, _descargas_base, _registrar_descarga

router = APIRouter()

# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Endpoints: Portal CIEC (scraping)
# ---------------------------------------------------------------------------

@router.post("/ciec/descargar")
def descargar_ciec(req: CIECDescargaRequest):
    """
    Descarga CFDIs via el portal web del SAT (autenticación CIEC).

    Apropiado para volúmenes pequeños (< 500 XMLs). Abre una ventana de
    browser para que el usuario resuelva el captcha.

    Requiere: pip install playwright && playwright install chromium
    """
    from ...portal.cfdi import descargar_cfdi_ciec

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


@router.post("/constancia/descargar")
def descargar_constancia(req: ConstanciaRequest):
    """
    Descarga la Constancia de Situación Fiscal (CSF) via el portal del SAT (CIEC).

    Abre una ventana de browser para que el usuario resuelva el captcha; luego da
    clic en «Generar Constancia» y captura el PDF de la ventana que abre el SAT.

    Requiere: pip install playwright && playwright install chromium
    """
    from ...portal.constancia import descargar_constancia_ciec

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


def _resolver_ciec(rfc: str, ciec: Optional[str]) -> str:
    """Usa la CIEC dada o, si falta, la guardada en el catálogo (keychain del SO)."""
    if ciec:
        return ciec
    from ...cli import config_store
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


@router.post("/ciec/cfdi")
def ciec_cfdi(req: CIECDescargaRequest):
    """Descarga CFDIs vía CIEC como job (captcha in-app por SSE). → {job_id}."""
    from ...portal.cfdi import descargar_cfdi_ciec
    from ...core import paths

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


@router.post("/ciec/constancia")
def ciec_constancia(req: ConstanciaRequest):
    """Descarga la Constancia de Situación Fiscal vía CIEC como job. → {job_id}."""
    from ...portal.constancia import descargar_constancia_ciec
    from ...core import paths

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
            from ...cli import config_store
            config_store.set_csf_descargada(req.rfc, archivo)

    return _lanzar_job_portal(factory, al_completar=al_completar)


@router.post("/ciec/opinion")
def ciec_opinion(req: OpinionRequest):
    """Descarga la Opinión de Cumplimiento 32-D vía CIEC como job. → {job_id}."""
    from ...portal.opinion import descargar_opinion_ciec
    from ...core import paths

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
            from ...cli import config_store
            config_store.set_opinion_descargada(req.rfc, archivo)

    return _lanzar_job_portal(factory, al_completar=al_completar)


@router.post("/jobs/{job_id}/captcha")
def responder_captcha_job(job_id: str, body: CaptchaSolution):
    """Entrega la solución del captcha (o solution=null para cancelar el job)."""
    job = jobs.registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")
    jobs.registry.responder_captcha(job, body.solution)
    return {"ok": True}


@router.get("/jobs/{job_id}")
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


@router.get("/events/{job_id}")
def eventos_job(job_id: str):
    """Stream SSE del progreso del job (incluye `captcha_required`)."""
    job = jobs.registry.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="job no encontrado")
    return StreamingResponse(jobs.registry.stream(job), media_type="text/event-stream")


# ---------------------------------------------------------------------------
# Endpoints: documentos vía e.firma (FIEL en sesión; sin captcha)
# ---------------------------------------------------------------------------

@router.post("/constancia/fiel")
def constancia_fiel_endpoint():
    """Constancia de Situación Fiscal con la e.firma cargada en sesión."""
    from ...portal.constancia import descargar_constancia_fiel
    from ...core import paths

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
            from ...cli import config_store
            config_store.set_csf_descargada(_session["rfc"], str(pdf))
        return {"ok": True, "archivo": str(pdf)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/opinion/fiel")
def opinion_fiel_endpoint():
    """Opinión de Cumplimiento 32-D con la e.firma cargada en sesión."""
    from ...portal.opinion import descargar_opinion_fiel
    from ...core import paths

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
            from ...cli import config_store
            config_store.set_opinion_descargada(_session["rfc"], str(pdf))
        return {"ok": True, "archivo": str(pdf)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cfdi/fiel")
def cfdi_fiel(req: FIELCfdiRequest):
    """
    Descarga CFDIs vía portal con la e.firma en sesión como job (sin captcha).
    Mismo patrón que /ciec/cfdi pero el login es e.firma → no se emite
    `captcha_required` en el SSE. → {job_id}.
    """
    from ...portal.cfdi import descargar_cfdi_fiel
    from ...core import paths

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

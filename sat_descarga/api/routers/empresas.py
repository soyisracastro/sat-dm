"""
Router: catálogo de empresas (persistente; credenciales en keychain del SO)
+ historial global de descargas.

Endpoints: /empresas* (CRUD, activar, default, archive, unarchive, solicitudes,
historial) y /historial (global).
"""

import os
import tempfile
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from ..state import _cargar_fiel_empresa

router = APIRouter()

# ---------------------------------------------------------------------------
# Modelos de request/response
# ---------------------------------------------------------------------------


class EmpresaCiecRequest(BaseModel):
    rfc: str
    # Opcional: si viene vacío, config_store usa el RFC como nombre provisional.
    nombre: str = ""
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


# ---------------------------------------------------------------------------
# Endpoints: catálogo de empresas (persistente; credenciales en keychain del SO)
# ---------------------------------------------------------------------------
#
# Reusa cli.config_store (capa de datos sin I/O de terminal): catálogo en
# ~/.sat-descarga/empresas.json + contraseñas en el keychain del SO (core.secretos).
# Así el usuario registra su e.firma/CIEC una vez y no las reingresa cada descarga.

@router.get("/empresas")
def empresas_list():
    """Lista las empresas registradas (sin credenciales)."""
    from ...cli import config_store
    return {"empresas": config_store.list_empresas()}


@router.post("/empresas/fiel")
async def empresas_add_fiel(
    cer_file: UploadFile = File(...),
    key_file: UploadFile = File(...),
    password: str = Form(...),
    nombre: str = Form(""),
    rfc_esperado: Optional[str] = Form(None),
):
    """
    Registra una empresa por e.firma. La contraseña se guarda en el keychain.
    `nombre` es opcional: si viene vacío se usa la razón social del certificado.
    Si se manda `rfc_esperado` (al agregar e.firma a una empresa existente), se valida
    que el RFC del certificado coincida y se rechaza si es de otro contribuyente.
    """
    from ...cli import config_store

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
        # Se degrada a 400 para el usuario, pero es un fallo operativo (p. ej. el
        # WinError 5 de permisos): repórtalo a Sentry, que si no la integración de
        # FastAPI no lo ve (solo captura excepciones no atrapadas).
        from ...core.telemetria import capturar_excepcion

        capturar_excepcion(e)
        raise HTTPException(status_code=400, detail=f"No se pudo registrar la empresa: {e}")
    finally:
        for p in (cer_tmp.name, key_tmp.name):
            try:
                os.unlink(p)
            except Exception:
                pass


@router.post("/empresas/ciec")
def empresas_add_ciec(req: EmpresaCiecRequest):
    """Registra una empresa por CIEC. La contraseña CIEC se guarda en el keychain."""
    from ...cli import config_store
    rfc = config_store.add_empresa_ciec(req.rfc, req.nombre, req.ciec)
    return {"ok": True, "rfc": rfc}


@router.delete("/empresas/{rfc}")
def empresas_remove(rfc: str):
    """Elimina la empresa del catálogo y borra sus credenciales del keychain."""
    from ...cli import config_store
    config_store.remove_empresa(rfc)
    return {"ok": True}


@router.delete("/empresas/{rfc}/fiel")
def empresas_remove_fiel(rfc: str):
    """
    Quita SOLO la e.firma de la empresa (archivos, contraseña del keychain y
    campos del catálogo); la CIEC no se toca. Si esa e.firma estaba cargada en
    la sesión, también se descarga de memoria.
    """
    from ...cli import config_store
    from ..state import _limpiar_session, _session

    try:
        config_store.remove_efirma(rfc)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if _session.get("rfc") == rfc:
        _limpiar_session()
    return {"ok": True}


@router.post("/empresas/{rfc}/activar")
def empresas_activar(rfc: str):
    """
    Activa una empresa para la sesión. Para FIEL, carga la e.firma guardada en memoria
    (como /auth/cargar-fiel, pero desde el catálogo). Para CIEC no carga e.firma.
    """
    from ...cli import config_store
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


@router.post("/empresas/{rfc}/default")
def empresas_default(rfc: str):
    """Marca la empresa como predeterminada (activa) del catálogo."""
    from ...cli import config_store
    try:
        config_store.set_default(rfc)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    return {"ok": True, "rfc": rfc}


@router.post("/empresas/{rfc}/archive")
def empresas_archive(rfc: str):
    """Soft-delete: archiva la empresa (la oculta de la lista principal)."""
    from ...cli import config_store
    try:
        config_store.archive_empresa(rfc)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    return {"ok": True, "rfc": rfc}


@router.post("/empresas/{rfc}/unarchive")
def empresas_unarchive(rfc: str):
    """Desarchiva la empresa (la regresa a la lista principal)."""
    from ...cli import config_store
    try:
        config_store.unarchive_empresa(rfc)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    return {"ok": True, "rfc": rfc}


@router.patch("/empresas/{rfc}")
def empresas_update(rfc: str, req: EmpresaUpdateRequest):
    """
    Actualiza campos editables de la empresa (regimenes_fiscales, actividades_economicas).
    Body parcial: solo los campos presentes (no nulos) se aplican.
    """
    from ...cli import config_store
    patch = req.model_dump(exclude_none=True)
    try:
        config_store.update_empresa(rfc, patch)
    except KeyError:
        raise HTTPException(status_code=404, detail="empresa no encontrada")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": True, "rfc": rfc}


@router.get("/empresas/{rfc}/solicitudes")
def empresas_solicitudes(rfc: str):
    """Historial de solicitudes de descarga de la empresa (más recientes primero)."""
    from ...cli import config_store
    return {"solicitudes": config_store.list_solicitudes(rfc)}


@router.delete("/empresas/{rfc}/solicitudes/{id_solicitud}")
def empresas_solicitudes_delete(rfc: str, id_solicitud: str):
    """Borra una solicitud del catálogo (solo limpia el registro local, no afecta al SAT)."""
    from ...cli import config_store
    borrada = config_store.delete_solicitud(rfc, id_solicitud)
    if not borrada:
        raise HTTPException(status_code=404, detail="Solicitud no encontrada")
    return {"ok": True}


@router.get("/empresas/{rfc}/historial")
def empresas_historial(rfc: str):
    """Historial de descargas completadas de la empresa (más recientes primero)."""
    from ...cli import config_store
    return {"descargas": config_store.list_descargas(rfc)}


@router.get("/historial")
def historial():
    """Historial de descargas de TODAS las empresas (con rfc + nombre), recientes primero."""
    from ...cli import config_store
    return {"descargas": config_store.list_todas_descargas()}

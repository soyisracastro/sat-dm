"""
Router: DIOT 2025 — prellenado, estado editable y export del TXT de carga masiva.

Endpoints: /diot/*. El estado vive por empresa Y periodo
(~/.sat-descarga/diot/{RFC}.json); el prellenado lee el buffer del procesador.
Layout y reglas del archivo: docs/producto/diot-2025.md.

Como en calculadoras, el gating premium del export vive en el frontend: el
agente local es del usuario y no re-valida licencia por endpoint.
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


def _rfc_requerido(rfc: Optional[str]) -> str:
    """Normaliza y valida el RFC dueño del estado; 400 si es inválido.

    Sin fallback a la "empresa activa" del agente: el RFC viaja SIEMPRE
    explícito desde el cliente (mismo contrato que procesador/calculadoras).
    """
    from ...procesador.db import normalizar_mi_rfc

    try:
        return normalizar_mi_rfc(rfc)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _validar_periodo_http(periodo: str) -> str:
    from ...diot import validar_periodo

    try:
        return validar_periodo(periodo)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _estado_con_validaciones(estado: Optional[dict]) -> dict:
    """Anexa errores/advertencias calculados server-side al estado guardado."""
    from ...diot import validar_filas

    if estado is None:
        return {"filas": [], "origen": None, "generado_en": None,
                "actualizado_en": None, "errores": [], "advertencias": []}
    validacion = validar_filas(estado.get("filas", []))
    return {**estado, **validacion}


class GuardarDiotRequest(BaseModel):
    rfc: str
    periodo: str  # YYYY-MM
    filas: List[dict]


class PrellenarDiotRequest(BaseModel):
    rfc: str
    periodo: str  # YYYY-MM


@router.get("/diot/estado")
def diot_estado(rfc: str, periodo: str):
    """Estado guardado del periodo (filas + validaciones), vacío si no existe."""
    from ...diot import get_periodo

    mi_rfc = _rfc_requerido(rfc)
    _validar_periodo_http(periodo)
    return _estado_con_validaciones(get_periodo(mi_rfc, periodo))


@router.put("/diot/estado")
def diot_guardar(req: GuardarDiotRequest):
    """Guarda la tabla completa del periodo (full-replace) y la re-valida."""
    from ...diot import set_periodo

    mi_rfc = _rfc_requerido(req.rfc)
    _validar_periodo_http(req.periodo)
    estado = set_periodo(mi_rfc, req.periodo, req.filas, origen="manual")
    return _estado_con_validaciones(estado)


@router.post("/diot/prellenar")
def diot_prellenar(req: PrellenarDiotRequest):
    """Prellena el periodo desde el buffer del procesador y lo persiste.

    Pisa los renglones de origen CFDI del periodo (la UI confirma antes si
    había ediciones); los renglones capturados a mano se conservan.
    """
    from ...diot import prellenar_y_guardar

    mi_rfc = _rfc_requerido(req.rfc)
    _validar_periodo_http(req.periodo)
    estado = prellenar_y_guardar(mi_rfc, req.periodo)
    respuesta = _estado_con_validaciones(estado)
    respuesta["resumen"] = estado.get("resumen")
    return respuesta


@router.get("/diot/exportar")
def diot_exportar(rfc: str, periodo: str):
    """Genera y descarga el TXT de carga masiva del periodo.

    400 con la lista de errores si la tabla viola el instructivo del SAT.
    """
    from ...diot import DiotInvalida, exportar_txt, get_periodo, nombre_archivo

    mi_rfc = _rfc_requerido(rfc)
    _validar_periodo_http(periodo)
    estado = get_periodo(mi_rfc, periodo)
    if estado is None or not estado.get("filas"):
        raise HTTPException(status_code=400, detail="No hay renglones en este periodo")

    try:
        data = exportar_txt(estado["filas"])
    except DiotInvalida as e:
        raise HTTPException(
            status_code=400,
            detail={"mensaje": str(e), "errores": e.errores},
        )

    filename = nombre_archivo(mi_rfc, periodo)
    return StreamingResponse(
        iter([data]),
        media_type="text/plain; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/diot/catalogos")
def diot_catalogos():
    """Catálogos oficiales para los selects de la UI."""
    from ...diot import (
        MANIFIESTO,
        OPERACIONES_POR_TERCERO,
        PAISES,
        TIPO_OPERACION,
        TIPO_TERCERO,
    )
    from ...diot.layout import CAMPOS_DIOT

    return {
        "tipo_tercero": TIPO_TERCERO,
        "tipo_operacion": TIPO_OPERACION,
        "operaciones_por_tercero": OPERACIONES_POR_TERCERO,
        "manifiesto": MANIFIESTO,
        "paises": PAISES,
        "campos": [
            {"clave": c.clave, "etiqueta": c.etiqueta, "tipo": c.tipo, "seccion": c.seccion}
            for c in CAMPOS_DIOT
        ],
    }

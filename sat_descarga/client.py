"""
Cliente principal: orquesta el flujo completo de descarga masiva.

Uso básico:
    from sat_descarga import descargar_cfdi
    from datetime import date

    descargar_cfdi(
        cer_path="mi_fiel.cer",
        key_path="mi_fiel.key",
        password="mi_contraseña",
        fecha_inicio=date(2024, 1, 1),
        fecha_fin=date(2024, 1, 31),
        directorio_salida="./cfdi_descargados/",
    )
"""

import logging
from datetime import date
from pathlib import Path
from typing import List, Optional

from .fiel import FIEL
from .auth import obtener_token
from .solicitud import solicitar_descarga
from .verificacion import verificar_solicitud
from .descarga import descargar_todos
from .config import TIPO_CFDI, TIPO_EMITIDO

logger = logging.getLogger(__name__)


def descargar_cfdi(
    cer_path: str,
    key_path: str,
    password: str,
    fecha_inicio: date,
    fecha_fin: date,
    directorio_salida: str = "./cfdi/",
    tipo_solicitud: str = TIPO_CFDI,
    tipo_comprobante: str = TIPO_EMITIDO,
    rfc_emisor: Optional[str] = None,
    rfc_receptor: Optional[str] = None,
    estado_comprobante: Optional[str] = None,
    extraer: bool = True,
) -> List[Path]:
    """
    Descarga CFDIs del SAT usando la Descarga Masiva (API v1.5).

    Flujo:
        1. Carga la e-firma y autentica con el SAT.
        2. Solicita la descarga del periodo (firmada con e-firma).
        3. Hace polling hasta que los paquetes estén listos.
        4. Descarga y extrae los ZIPs con los XMLs.
    """
    if fecha_inicio > fecha_fin:
        raise ValueError("fecha_inicio debe ser anterior o igual a fecha_fin.")

    logger.info("[Client] Cargando e-firma...")
    fiel = FIEL(cer_path, key_path, password)
    rfc = fiel.rfc
    logger.info("[Client] RFC detectado: %s", rfc)

    logger.info("[Client] Autenticando con el SAT...")
    token = obtener_token(fiel)

    logger.info(
        "[Client] Solicitando descarga: %s — %s a %s (%s/%s)",
        rfc, fecha_inicio, fecha_fin, tipo_solicitud, tipo_comprobante,
    )
    id_solicitud = solicitar_descarga(
        fiel=fiel,
        token=token,
        rfc_solicitante=rfc,
        fecha_inicio=fecha_inicio,
        fecha_fin=fecha_fin,
        tipo_solicitud=tipo_solicitud,
        tipo_comprobante=tipo_comprobante,
        rfc_emisor=rfc_emisor,
        rfc_receptor=rfc_receptor,
        estado_comprobante=estado_comprobante,
    )
    logger.info("[Client] RequestID: %s", id_solicitud)

    logger.info("[Client] Esperando a que el SAT procese la solicitud...")
    estado = verificar_solicitud(
        token=token,
        rfc_solicitante=rfc,
        id_solicitud=id_solicitud,
        fiel=fiel,
        poll=True,
    )

    logger.info(
        "[Client] Solicitud lista. CFDIs: %d, Paquetes: %d",
        estado.numero_cfdis,
        len(estado.package_ids),
    )

    if not estado.package_ids:
        logger.warning("[Client] No hay paquetes para descargar.")
        return []

    # Renovar token (puede haber expirado durante el polling)
    logger.info("[Client] Renovando token antes de la descarga...")
    token = obtener_token(fiel)

    zips = descargar_todos(
        token=token,
        rfc_solicitante=rfc,
        package_ids=estado.package_ids,
        directorio_salida=directorio_salida,
        fiel=fiel,
        extraer=extraer,
    )

    logger.info("[Client] Descarga completa. %d ZIP(s) guardados.", len(zips))
    return zips


def verificar_solicitud_existente(
    cer_path: str,
    key_path: str,
    password: str,
    id_solicitud: str,
    directorio_salida: str = "./cfdi/",
    extraer: bool = True,
    poll: bool = False,
) -> List[Path]:
    """
    Retoma una solicitud previa y descarga los paquetes si están listos.
    """
    fiel = FIEL(cer_path, key_path, password)
    rfc = fiel.rfc
    token = obtener_token(fiel)

    logger.info("[Client] Verificando solicitud existente: %s", id_solicitud)
    estado = verificar_solicitud(
        token=token,
        rfc_solicitante=rfc,
        id_solicitud=id_solicitud,
        fiel=fiel,
        poll=poll,
    )

    if not estado.terminada:
        logger.info("[Client] Solicitud aún no lista. Estado=%s", estado.cod_estado)
        return []

    logger.info("[Client] Paquetes listos: %d. Descargando...", len(estado.package_ids))
    token = obtener_token(fiel)
    return descargar_todos(
        token=token,
        rfc_solicitante=rfc,
        package_ids=estado.package_ids,
        directorio_salida=directorio_salida,
        fiel=fiel,
        extraer=extraer,
    )

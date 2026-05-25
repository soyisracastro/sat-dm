"""
Organizador de archivos XML CFDI.

Herramientas para organizar, renombrar y deduplicar archivos XML
descargados del SAT. Inspirado en las 20 formas de organización de
XMLSAT Premium.

Usa xml_reader.py para extraer datos mínimos del header de cada XML.
"""

import logging
import os
import shutil
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from .xml_reader import leer_cfdi, CfdiHeader

logger = logging.getLogger(__name__)

# Patrones de estructura de carpetas disponibles
ESTRUCTURAS = {
    "rfc_emisor/anio/mes": lambda h: f"{h.emisor_rfc}/{h.fecha_emision[:4]}/{h.fecha_emision[5:7]}",
    "rfc_emisor/anio": lambda h: f"{h.emisor_rfc}/{h.fecha_emision[:4]}",
    "anio/mes/rfc_emisor": lambda h: f"{h.fecha_emision[:4]}/{h.fecha_emision[5:7]}/{h.emisor_rfc}",
    "anio/mes": lambda h: f"{h.fecha_emision[:4]}/{h.fecha_emision[5:7]}",
    "anio/mes/dia": lambda h: f"{h.fecha_emision[:4]}/{h.fecha_emision[5:7]}/{h.fecha_emision[8:10]}",
    "tipo/anio/mes": lambda h: f"{_tipo_nombre(h.tipo_comprobante)}/{h.fecha_emision[:4]}/{h.fecha_emision[5:7]}",
    "rfc_emisor/tipo/anio/mes": lambda h: f"{h.emisor_rfc}/{_tipo_nombre(h.tipo_comprobante)}/{h.fecha_emision[:4]}/{h.fecha_emision[5:7]}",
    "rfc_receptor/anio/mes": lambda h: f"{h.receptor_rfc}/{h.fecha_emision[:4]}/{h.fecha_emision[5:7]}",
    "plano": lambda h: "",
}

# Patrones de renombrado
PATRONES_NOMBRE = {
    "emisor_fecha_total": lambda h: f"{h.emisor_rfc}_{h.fecha_emision[:10]}_{h.total:.2f}_{h.uuid[:8]}",
    "receptor_fecha_total": lambda h: f"{h.receptor_rfc}_{h.fecha_emision[:10]}_{h.total:.2f}_{h.uuid[:8]}",
    "uuid": lambda h: h.uuid,
    "fecha_emisor_total": lambda h: f"{h.fecha_emision[:10]}_{h.emisor_rfc}_{h.total:.2f}",
    "fecha_uuid": lambda h: f"{h.fecha_emision[:10]}_{h.uuid}",
}


@dataclass
class OrganizadorResult:
    """Resultado de una operación de organización."""
    archivos_procesados: int = 0
    archivos_movidos: int = 0
    archivos_omitidos: int = 0
    errores: List[str] = field(default_factory=list)


@dataclass
class DeduplicarResult:
    """Resultado de eliminación de duplicados."""
    archivos_analizados: int = 0
    duplicados_encontrados: int = 0
    duplicados_eliminados: int = 0
    errores: List[str] = field(default_factory=list)


def organizar(
    origen: str,
    destino: str,
    estructura: str = "rfc_emisor/anio/mes",
    copiar: bool = False,
) -> OrganizadorResult:
    """
    Organiza archivos XML en carpetas basándose en su contenido.

    Args:
        origen: Directorio con XMLs desordenados.
        destino: Directorio destino para la estructura organizada.
        estructura: Patrón de carpetas (ver ESTRUCTURAS).
        copiar: Si True copia en lugar de mover.

    Returns:
        OrganizadorResult con estadísticas.
    """
    if estructura not in ESTRUCTURAS:
        raise ValueError(
            f"Estructura '{estructura}' no válida. "
            f"Opciones: {', '.join(ESTRUCTURAS.keys())}"
        )

    path_fn = ESTRUCTURAS[estructura]
    result = OrganizadorResult()
    dest_path = Path(destino)

    for root_dir, _dirs, files in os.walk(origen):
        for filename in files:
            if not filename.lower().endswith(".xml"):
                continue

            result.archivos_procesados += 1
            src = Path(root_dir) / filename

            try:
                header = leer_cfdi(str(src))
            except (ValueError, Exception) as e:
                result.archivos_omitidos += 1
                result.errores.append(f"{filename}: {e}")
                continue

            # Construir ruta destino
            subdir = path_fn(header)
            target_dir = dest_path / subdir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / filename

            # Evitar sobrescribir
            if target_file.exists():
                result.archivos_omitidos += 1
                continue

            try:
                if copiar:
                    shutil.copy2(str(src), str(target_file))
                else:
                    shutil.move(str(src), str(target_file))
                result.archivos_movidos += 1
            except Exception as e:
                result.errores.append(f"{filename}: {e}")

    logger.info(
        "[Organizador] %d procesados, %d movidos, %d omitidos, %d errores",
        result.archivos_procesados, result.archivos_movidos,
        result.archivos_omitidos, len(result.errores),
    )
    return result


def renombrar(
    directorio: str,
    patron: str = "emisor_fecha_total",
    recursive: bool = True,
) -> OrganizadorResult:
    """
    Renombra masivamente archivos XML basándose en su contenido.

    Args:
        directorio: Directorio con XMLs.
        patron: Patrón de nombre (ver PATRONES_NOMBRE).
        recursive: Si buscar en subdirectorios.

    Returns:
        OrganizadorResult con estadísticas.
    """
    if patron not in PATRONES_NOMBRE:
        raise ValueError(
            f"Patrón '{patron}' no válido. "
            f"Opciones: {', '.join(PATRONES_NOMBRE.keys())}"
        )

    name_fn = PATRONES_NOMBRE[patron]
    result = OrganizadorResult()

    for root_dir, _dirs, files in os.walk(directorio):
        for filename in files:
            if not filename.lower().endswith(".xml"):
                continue

            result.archivos_procesados += 1
            src = Path(root_dir) / filename

            try:
                header = leer_cfdi(str(src))
            except (ValueError, Exception) as e:
                result.archivos_omitidos += 1
                result.errores.append(f"{filename}: {e}")
                continue

            new_name = name_fn(header) + ".xml"
            # Sanitizar nombre de archivo
            new_name = new_name.replace("/", "_").replace("\\", "_")
            target = Path(root_dir) / new_name

            if target == src:
                result.archivos_omitidos += 1
                continue

            if target.exists():
                result.archivos_omitidos += 1
                continue

            try:
                src.rename(target)
                result.archivos_movidos += 1
            except Exception as e:
                result.errores.append(f"{filename} → {new_name}: {e}")

        if not recursive:
            break

    logger.info(
        "[Renombrar] %d procesados, %d renombrados, %d omitidos",
        result.archivos_procesados, result.archivos_movidos, result.archivos_omitidos,
    )
    return result


def eliminar_duplicados(
    directorio: str,
    recursive: bool = True,
    dry_run: bool = False,
) -> DeduplicarResult:
    """
    Elimina archivos XML duplicados basándose en el UUID del CFDI.

    Conserva la primera aparición y elimina las copias posteriores.

    Args:
        directorio: Directorio con XMLs.
        recursive: Si buscar en subdirectorios.
        dry_run: Si True, solo reporta sin eliminar.

    Returns:
        DeduplicarResult con estadísticas.
    """
    result = DeduplicarResult()
    uuid_seen: dict[str, str] = {}  # UUID → primer archivo encontrado

    for root_dir, _dirs, files in os.walk(directorio):
        for filename in sorted(files):
            if not filename.lower().endswith(".xml"):
                continue

            result.archivos_analizados += 1
            path = Path(root_dir) / filename

            try:
                header = leer_cfdi(str(path))
            except (ValueError, Exception):
                continue

            if not header.uuid:
                continue

            if header.uuid in uuid_seen:
                result.duplicados_encontrados += 1
                if not dry_run:
                    try:
                        path.unlink()
                        result.duplicados_eliminados += 1
                        logger.debug(
                            "[Dedup] Eliminado duplicado: %s (original: %s)",
                            path, uuid_seen[header.uuid],
                        )
                    except Exception as e:
                        result.errores.append(f"{filename}: {e}")
            else:
                uuid_seen[header.uuid] = str(path)

        if not recursive:
            break

    logger.info(
        "[Dedup] %d analizados, %d duplicados, %d eliminados",
        result.archivos_analizados, result.duplicados_encontrados,
        result.duplicados_eliminados,
    )
    return result


def agrupar_por_version_tipo(
    origen: str,
    destino: str,
    copiar: bool = False,
) -> OrganizadorResult:
    """
    Agrupa XMLs en carpetas por versión CFDI y tipo de comprobante.

    Resultado: destino/v4.0/Ingreso/, destino/v3.3/Egreso/, etc.
    """
    result = OrganizadorResult()
    dest_path = Path(destino)

    for root_dir, _dirs, files in os.walk(origen):
        for filename in files:
            if not filename.lower().endswith(".xml"):
                continue

            result.archivos_procesados += 1
            src = Path(root_dir) / filename

            try:
                header = leer_cfdi(str(src))
            except (ValueError, Exception) as e:
                result.archivos_omitidos += 1
                continue

            tipo_nombre = _tipo_nombre(header.tipo_comprobante)
            subdir = f"v{header.version}/{tipo_nombre}"
            target_dir = dest_path / subdir
            target_dir.mkdir(parents=True, exist_ok=True)
            target_file = target_dir / filename

            if target_file.exists():
                result.archivos_omitidos += 1
                continue

            try:
                if copiar:
                    shutil.copy2(str(src), str(target_file))
                else:
                    shutil.move(str(src), str(target_file))
                result.archivos_movidos += 1
            except Exception as e:
                result.errores.append(f"{filename}: {e}")

    return result


def _tipo_nombre(tipo: str) -> str:
    """Convierte letra de tipo a nombre legible."""
    tipos = {
        "I": "Ingreso",
        "E": "Egreso",
        "P": "Pago",
        "T": "Traslado",
        "N": "Nomina",
    }
    return tipos.get(tipo.upper(), tipo)

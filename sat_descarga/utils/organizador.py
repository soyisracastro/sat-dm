"""
Organizador de archivos XML CFDI.

Herramientas para organizar, renombrar y deduplicar archivos XML
descargados del SAT. Inspirado en las 20 formas de organización de
XMLSAT Premium.

Usa xml_reader.py para extraer datos mínimos del header de cada XML.
"""

import logging
import os
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from .xml_reader import leer_cfdi, CfdiHeader

logger = logging.getLogger(__name__)

# Tokens para componer estructuras de carpetas: una estructura es una
# secuencia de tokens separados por "/" (p. ej. "rfc/anio/mes/flujo/tipo"),
# donde cada token produce un nivel de carpeta por CFDI. El segundo argumento
# es el RFC de la empresa (la activa en la UI, `--rfc` en el CLI).
TOKENS: dict[str, Callable[[CfdiHeader, Optional[str]], str]] = {
    "anio": lambda h, rfc: h.fecha_emision[:4],
    "mes": lambda h, rfc: h.fecha_emision[5:7],
    "dia": lambda h, rfc: h.fecha_emision[8:10],
    "rfc": lambda h, rfc: rfc or "",
    "rfc_emisor": lambda h, rfc: h.emisor_rfc,
    "rfc_receptor": lambda h, rfc: h.receptor_rfc,
    "tipo": lambda h, rfc: _tipo_nombre(h.tipo_comprobante),
    "flujo": lambda h, rfc: _flujo(h, rfc),
}

# Tokens que clasifican contra el RFC de la empresa
_TOKENS_POR_EMPRESA = {"rfc", "flujo"}

# Estructuras predefinidas (presets que ofrece la UI); cualquier otra
# combinación de TOKENS también es válida, más "plano" (sin subcarpetas).
ESTRUCTURAS = (
    "rfc_emisor/anio/mes",
    "rfc_emisor/anio",
    "anio/mes/rfc_emisor",
    "anio/mes",
    "anio/mes/dia",
    "tipo/anio/mes",
    "rfc_emisor/tipo/anio/mes",
    "rfc_receptor/anio/mes",
    "plano",
)

# Patrones de renombrado predefinidos (legacy; el modo por partes es el nuevo)
PATRONES_NOMBRE = {
    "emisor_fecha_total": lambda h: f"{h.emisor_rfc}_{h.fecha_emision[:10]}_{h.total:.2f}_{h.uuid[:8]}",
    "receptor_fecha_total": lambda h: f"{h.receptor_rfc}_{h.fecha_emision[:10]}_{h.total:.2f}_{h.uuid[:8]}",
    "uuid": lambda h: h.uuid,
    "fecha_emisor_total": lambda h: f"{h.fecha_emision[:10]}_{h.emisor_rfc}_{h.total:.2f}",
    "fecha_uuid": lambda h: f"{h.fecha_emision[:10]}_{h.uuid}",
}

# Partes disponibles para componer el nombre de archivo (modo por partes):
# se unen con un separador, más literales con prefijo "txt:".
NOMBRE_TOKENS: dict[str, Callable[[CfdiHeader], str]] = {
    "fecha": lambda h: h.fecha_emision[:10],
    "rfc_emisor": lambda h: h.emisor_rfc,
    "nombre_emisor": lambda h: h.emisor_nombre,
    "rfc_receptor": lambda h: h.receptor_rfc,
    "folio_fiscal": lambda h: h.uuid[:8],
    "serie_folio": lambda h: "-".join(p for p in (h.serie, h.folio) if p),
    "tipo": lambda h: _tipo_nombre(h.tipo_comprobante),
    "total": lambda h: f"{h.total:.2f}",
}


@dataclass
class OrganizadorResult:
    """Resultado de una operación de organización."""
    archivos_procesados: int = 0
    archivos_movidos: int = 0
    archivos_omitidos: int = 0
    errores: List[str] = field(default_factory=list)
    # Solo con estructuras que clasifican por empresa ("rfc"/"flujo"): CFDIs
    # donde la empresa no es emisor ni receptor — se quedan en su lugar y se
    # reportan (cuentan también en archivos_omitidos). Nunca van a "Otros".
    de_otro_rfc: int = 0


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
    rfc: Optional[str] = None,
) -> OrganizadorResult:
    """
    Organiza archivos XML en carpetas basándose en su contenido.

    Los tokens "rfc" y "flujo" clasifican cada CFDI contra el RFC de la
    empresa (`rfc`; en la app, la empresa activa). Los CFDIs donde la empresa
    no es emisor ni receptor se quedan en su lugar y se reportan en
    `de_otro_rfc` — nunca se crea una carpeta "Otros". Si NINGÚN XML de la
    carpeta pertenece a la empresa, no se organiza nada: se lanza ValueError
    pidiendo activar la empresa correcta.

    Args:
        origen: Directorio con XMLs desordenados.
        destino: Directorio destino para la estructura organizada. Si vive
            dentro del origen, su subárbol se excluye del recorrido (las
            corridas previas no se releen).
        estructura: Tokens de carpetas separados por "/" (ver TOKENS),
            o "plano" para no crear subcarpetas. Presets en ESTRUCTURAS.
        copiar: Si True copia en lugar de mover.
        rfc: RFC de la empresa; requerido si la estructura usa los tokens
            "rfc" o "flujo" (Emitidos/Recibidos se clasifican contra él).

    Returns:
        OrganizadorResult con estadísticas (incluye `de_otro_rfc`).
    """
    tokens = _validar_estructura(estructura)
    por_empresa = bool(_TOKENS_POR_EMPRESA & set(tokens))
    if por_empresa and not (rfc or "").strip():
        raise ValueError(
            "La estructura usa 'rfc' o 'flujo' (Emitidos/Recibidos) y "
            "requiere el RFC de la empresa."
        )

    result = OrganizadorResult()
    dest_path = Path(destino)
    dest_abs = os.path.abspath(destino)
    path_fn = _compilar_estructura(tokens)

    def _caminar():
        """Recorre el origen saltando el subárbol del destino (salida previa)."""
        for root_dir, dirs, files in os.walk(origen):
            dirs[:] = [
                d for d in dirs
                if os.path.abspath(os.path.join(root_dir, d)) != dest_abs
            ]
            for filename in files:
                if filename.lower().endswith(".xml"):
                    yield Path(root_dir) / filename

    def _leer(src: Path) -> Optional[CfdiHeader]:
        result.archivos_procesados += 1
        try:
            return leer_cfdi(str(src))
        except Exception as e:
            result.archivos_omitidos += 1
            result.errores.append(f"{src.name}: {e}")
            return None

    def _colocar(src: Path, subdir: str):
        target_dir = dest_path / subdir if subdir else dest_path
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / src.name

        # Evitar sobrescribir
        if target_file.exists():
            result.archivos_omitidos += 1
            return
        try:
            if copiar:
                shutil.copy2(str(src), str(target_file))
            else:
                shutil.move(str(src), str(target_file))
            result.archivos_movidos += 1
        except Exception as e:
            result.errores.append(f"{src.name}: {e}")

    if not por_empresa:
        for src in _caminar():
            header = _leer(src)
            if header is not None:
                _colocar(src, path_fn(header, None))
    else:
        mi_rfc = rfc.strip().upper()

        # Pase 1: leer headers y separar lo que pertenece a la empresa.
        # Nada se mueve hasta saber que la carpeta sí es de esta empresa.
        propios: list[tuple[Path, CfdiHeader]] = []
        ajenos = 0
        for src in _caminar():
            header = _leer(src)
            if header is None:
                continue
            if _es_de_la_empresa(header, mi_rfc):
                propios.append((src, header))
            else:
                ajenos += 1

        if ajenos and not propios:
            raise ValueError(
                f"Ninguno de los XML a organizar contiene el RFC {mi_rfc} "
                "de la empresa activa como emisor o receptor. Selecciona la "
                "empresa cuyo RFC deseas organizar y vuelve a intentarlo."
            )

        result.de_otro_rfc = ajenos
        result.archivos_omitidos += ajenos

        for src, header in propios:
            _colocar(src, path_fn(header, mi_rfc))

    logger.info(
        "[Organizador] %d procesados, %d movidos, %d omitidos (%d de otro RFC), %d errores",
        result.archivos_procesados, result.archivos_movidos,
        result.archivos_omitidos, result.de_otro_rfc, len(result.errores),
    )
    return result


def renombrar(
    directorio: str,
    patron: str = "emisor_fecha_total",
    recursive: bool = True,
    partes: Optional[List[str]] = None,
    separador: str = "-",
) -> OrganizadorResult:
    """
    Renombra masivamente archivos XML basándose en su contenido.

    Args:
        directorio: Directorio con XMLs.
        patron: Patrón de nombre predefinido (ver PATRONES_NOMBRE).
        recursive: Si buscar en subdirectorios.
        partes: Modo por partes: tokens de NOMBRE_TOKENS (o "txt:Literal")
            que componen el nombre; si se pasa, `patron` se ignora.
        separador: Separador entre partes (solo en modo por partes).

    Returns:
        OrganizadorResult con estadísticas.
    """
    if partes is not None:
        name_fn = _compilar_nombre(partes, separador)
    elif patron in PATRONES_NOMBRE:
        name_fn = PATRONES_NOMBRE[patron]
    else:
        raise ValueError(
            f"Patrón '{patron}' no válido. "
            f"Opciones: {', '.join(PATRONES_NOMBRE.keys())}"
        )

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
    dest_abs = os.path.abspath(destino)

    for root_dir, dirs, files in os.walk(origen):
        # No releer la salida de corridas previas (destino dentro del origen)
        dirs[:] = [
            d for d in dirs
            if os.path.abspath(os.path.join(root_dir, d)) != dest_abs
        ]
        for filename in files:
            if not filename.lower().endswith(".xml"):
                continue

            result.archivos_procesados += 1
            src = Path(root_dir) / filename

            try:
                header = leer_cfdi(str(src))
            except (ValueError, Exception):
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


def _es_de_la_empresa(header: CfdiHeader, rfc: str) -> bool:
    """True si la empresa es emisor o receptor del CFDI (`rfc` ya normalizado)."""
    return rfc in (
        (header.emisor_rfc or "").strip().upper(),
        (header.receptor_rfc or "").strip().upper(),
    )


def _flujo(header: CfdiHeader, rfc: Optional[str]) -> str:
    """Emitidos/Recibidos respecto al RFC de la empresa.

    El caller garantiza (vía `_es_de_la_empresa`) que la empresa es emisor o
    receptor del comprobante; auto-facturas cuentan como Emitidos.
    """
    mi_rfc = (rfc or "").strip().upper()
    if (header.emisor_rfc or "").strip().upper() == mi_rfc:
        return "Emitidos"
    return "Recibidos"


# Caracteres inválidos en nombres de carpeta (Windows es el SO principal)
_CHARS_INVALIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def _sanear_segmento(valor: Optional[str]) -> str:
    """Convierte un valor en nombre de carpeta seguro; vacío → SIN_DATO."""
    limpio = _CHARS_INVALIDOS.sub("_", (valor or "").strip()).rstrip(". ")
    return limpio or "SIN_DATO"


# Prefijo de segmento literal: "txt:Facturas" crea la carpeta fija "Facturas"
_PREFIJO_TEXTO = "txt:"


def _validar_estructura(estructura: str) -> List[str]:
    """
    Valida una estructura tokenizada y regresa su lista de tokens.

    Acepta "plano" (sin subcarpetas → lista vacía) o niveles separados por
    "/": tokens de TOKENS o literales con prefijo "txt:" (carpeta fija).
    """
    if estructura == "plano":
        return []

    tokens = estructura.split("/") if estructura else []

    def _es_valido(t: str) -> bool:
        if t.startswith(_PREFIJO_TEXTO):
            return bool(t[len(_PREFIJO_TEXTO):].strip())
        return t in TOKENS

    if not tokens or any(not _es_valido(t) for t in tokens):
        raise ValueError(
            f"Estructura '{estructura}' no válida. Combina niveles separados "
            f"por '/' usando: {', '.join(TOKENS)}, texto fijo con "
            f"'txt:NombreCarpeta' — o 'plano' (sin subcarpetas)."
        )
    return tokens


def _compilar_estructura(
    tokens: List[str],
) -> Callable[[CfdiHeader, Optional[str]], str]:
    """Regresa la función (header, dueño) → subruta para tokens ya validados."""
    if not tokens:
        return lambda h, rfc: ""

    def _segmento(t: str, header: CfdiHeader, rfc: Optional[str]) -> str:
        if t.startswith(_PREFIJO_TEXTO):
            return _sanear_segmento(t[len(_PREFIJO_TEXTO):])
        return _sanear_segmento(TOKENS[t](header, rfc))

    def path_fn(header: CfdiHeader, rfc: Optional[str]) -> str:
        return "/".join(_segmento(t, header, rfc) for t in tokens)

    return path_fn


def _compilar_nombre(
    partes: List[str],
    separador: str,
) -> Callable[[CfdiHeader], str]:
    """
    Valida las partes de un nombre de archivo y regresa header → nombre.

    Cada parte es un token de NOMBRE_TOKENS o un literal "txt:...".
    """

    def _es_valida(p: str) -> bool:
        if p.startswith(_PREFIJO_TEXTO):
            return bool(p[len(_PREFIJO_TEXTO):].strip())
        return p in NOMBRE_TOKENS

    if not partes or any(not _es_valida(p) for p in partes):
        raise ValueError(
            f"Partes del nombre no válidas: {partes!r}. "
            f"Opciones: {', '.join(NOMBRE_TOKENS)}, o texto fijo con 'txt:Algo'."
        )

    sep = _CHARS_INVALIDOS.sub("_", separador)

    def _parte(p: str, header: CfdiHeader) -> str:
        if p.startswith(_PREFIJO_TEXTO):
            return _sanear_segmento(p[len(_PREFIJO_TEXTO):])
        return _sanear_segmento(NOMBRE_TOKENS[p](header))

    def name_fn(header: CfdiHeader) -> str:
        return sep.join(_parte(p, header) for p in partes)

    return name_fn

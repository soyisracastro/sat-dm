"""
Parser del PDF de la Opinión de Cumplimiento de obligaciones fiscales (32-D).

Extrae el **sentido** (positiva / negativa) que alimenta el semáforo de la
empresa y, cuando es negativa, los **motivos** (créditos fiscales, omisiones de
obligaciones, etc.) que se muestran en el detalle de la empresa.

Diseño en dos capas (igual que `csf_parser.py`):
  - `_extraer_pdf()` — única que toca pdfplumber: PDF → texto.
  - `parsear_contenido_opinion()` — pura (texto → DatosOpinion), testeable sin
    PDFs reales (las opiniones traen datos personales y no se commitean).

Notas de calibración contra opiniones reales (formato actual del SAT + formato
2020, positivas y negativas):
  - El **sentido** más confiable NO es el texto "POSITIVO/NEGATIVO" sino la
    letra P/N de la Cadena Original (`||RFC|Folio|Fecha|N||…`), que es un campo
    machine-readable presente en TODOS los formatos. El texto se usa de respaldo.
  - Los **motivos** de una negativa vienen en secciones ("Créditos fiscales",
    "Cumplimiento de obligaciones", …) cada una con el patrón
    `Encabezado\nSe [verbo]…:` — la heurística "la línea siguiente empieza con
    'Se '" detecta el encabezado sin hardcodear los nombres de sección.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sat_descarga.opinion")

# Sin esta tolerancia el SAT "pega" las palabras (mismo caso que la CSF).
_X_TOLERANCE = 1

_SENTIDO_POR_LETRA = {"P": "positiva", "N": "negativa"}

# Letra de sentido en la Cadena Original: ||RFC|Folio|Fecha|<LETRA>||…
_RE_CADENA = re.compile(r"\|\|([^|]*)\|([^|]*)\|([^|]*)\|([A-Z])\|")


@dataclass
class MotivoOpinion:
    titulo: str  # encabezado de sección, p. ej. "Cumplimiento de obligaciones"
    descripcion: str  # frase introductoria ("Se detectan omisiones…:"), "" si no hay
    detalles: list[str] = field(default_factory=list)  # renglones específicos


@dataclass
class DatosOpinion:
    rfc: Optional[str]
    sentido: str  # "positiva" | "negativa" | "otro"
    folio: Optional[str]
    motivos: list[MotivoOpinion] = field(default_factory=list)


def _sentido(texto: str) -> tuple[str, Optional[str], Optional[str]]:
    """Devuelve (sentido, rfc, folio). Sentido por letra de la Cadena Original."""
    m = _RE_CADENA.search(texto)
    if m:
        rfc, folio, _fecha, letra = m.groups()
        sentido = _SENTIDO_POR_LETRA.get(letra, "otro")
        return sentido, (rfc or None), (folio or None)

    # Respaldo por texto (formato sin cadena legible): "en sentido NEGATIVO",
    # o el "POSITIVO/NEGATIVO" del encabezado.
    if re.search(r"sentido\s+NEGATIVO|\bNEGATIVO\b", texto, re.IGNORECASE):
        return "negativa", None, None
    if re.search(r"sentido\s+POSITIVO|\bPOSITIVO\b", texto, re.IGNORECASE):
        return "positiva", None, None
    return "", None, None


def _region_motivos(texto: str) -> str:
    """
    Bloque de motivos de una opinión negativa: lo que va entre la frase
    introductoria ("…se detallan a continuación:") y "Información importante".
    Vacío en las positivas (no traen ese bloque).
    """
    m = re.search(
        r"a continuaci[oó]n:\s*(.*?)\s*Informaci[oó]n importante",
        texto,
        re.DOTALL | re.IGNORECASE,
    )
    return m.group(1) if m else ""


def _norm(texto: str) -> str:
    """lowercase sin acentos, para comparar encabezados."""
    plano = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in plano if not unicodedata.combining(c)).strip()


# Secciones documentadas de una negativa (créditos, omisiones, buzón, 69-B,
# domicilio no localizado). Sirven de respaldo cuando una sección no trae la
# frase introductoria "Se …". La detección NO depende solo de esta lista: la
# heurística de abajo capta secciones nuevas para que el parser sea agnóstico
# al motivo — cualquier razón por la que salga negativa queda reflejada.
_ENCABEZADOS_CONOCIDOS = frozenset(
    _norm(h)
    for h in (
        "Créditos fiscales",
        "Cumplimiento de obligaciones",
        "Cumplimiento de declaraciones",
        "Localización del contribuyente",
        "Localización del domicilio fiscal",
        "Buzón Tributario",
        "Operaciones inexistentes",
    )
)


def _es_encabezado(linea: str, siguiente: str) -> bool:
    """
    Encabezado de sección: un nombre conocido, o —de forma agnóstica— un renglón
    corto sin puntuación final seguido de la frase introductoria del SAT
    (siempre empieza con "Se …"). Así se detectan también secciones nuevas sin
    depender de una lista fija de nombres.
    """
    if _norm(linea) in _ENCABEZADOS_CONOCIDOS:
        return True
    return (
        siguiente.startswith("Se ")
        and len(linea) < 70
        and not linea.endswith((":", "."))
    )


def _parse_motivos(texto: str) -> list[MotivoOpinion]:
    region = _region_motivos(texto)
    if not region:
        return []
    lineas = [l.strip() for l in region.splitlines() if l.strip()]

    motivos: list[MotivoOpinion] = []
    actual: Optional[MotivoOpinion] = None
    for i, linea in enumerate(lineas):
        siguiente = lineas[i + 1] if i + 1 < len(lineas) else ""
        if _es_encabezado(linea, siguiente):
            actual = MotivoOpinion(titulo=linea, descripcion="")
            motivos.append(actual)
        elif actual is None:
            # Renglón antes de cualquier encabezado (raro): sección genérica.
            actual = MotivoOpinion(titulo="Detalle", descripcion="")
            motivos.append(actual)
            actual.detalles.append(linea)
        elif not actual.descripcion and (linea.startswith("Se ") or linea.endswith(":")):
            # Frase introductoria de la sección ("Se detectan…", "Se ubican…:").
            actual.descripcion = linea
        else:
            actual.detalles.append(linea)
    return motivos


def parsear_contenido_opinion(texto: str) -> DatosOpinion:
    """Capa pura: texto del PDF → DatosOpinion."""
    es_opinion = bool(_RE_CADENA.search(texto)) or bool(
        re.search(r"Opini[oó]n del cumplimiento de obligaciones fiscales", texto, re.IGNORECASE)
    )
    if not es_opinion:
        raise ValueError("El PDF no parece una Opinión de Cumplimiento 32-D.")

    sentido, rfc, folio = _sentido(texto)
    motivos = _parse_motivos(texto) if sentido == "negativa" else []
    return DatosOpinion(rfc=rfc, sentido=sentido, folio=folio, motivos=motivos)


def _extraer_pdf(pdf_path: Path) -> str:
    """Única capa que toca pdfplumber: PDF → texto completo."""
    try:
        import pdfplumber
    except ImportError as e:  # instalación incompleta
        raise RuntimeError(
            "Falta la librería pdfplumber para leer la opinión 32-D "
            "(reinstala con `pip install -e .`)."
        ) from e

    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join(
            (pagina.extract_text(x_tolerance=_X_TOLERANCE) or "") for pagina in pdf.pages
        )


def parsear_opinion(pdf_path: str | Path) -> DatosOpinion:
    """
    Parsea una Opinión de Cumplimiento 32-D descargada.

    Lanza ValueError si el PDF no parece una opinión y RuntimeError si falta la
    librería de lectura; cualquier otro error de lectura se propaga tal cual.
    """
    ruta = Path(pdf_path)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    return parsear_contenido_opinion(_extraer_pdf(ruta))

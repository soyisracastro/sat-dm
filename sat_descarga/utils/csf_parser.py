"""
Parser del PDF de la Constancia de Situación Fiscal (CSF).

Extrae los datos que alimentan el catálogo de empresas: nombre/razón social,
regímenes fiscales activos y actividades económicas activas (con porcentaje).

Diseño en dos capas:
  - `_extraer_pdf()` — única que toca pdfplumber: PDF → texto + tablas crudas.
  - `parsear_contenido_csf()` — pura (texto + tablas → DatosCsf), testeable sin
    PDFs reales (las constancias contienen datos personales y no se commitean).

Notas de calibración contra constancias reales (PM y PF, 2026):
  - El SAT comprime el espaciado en las celdas: con la tolerancia default de
    pdfplumber los espacios se pierden ("SUPERSERVICIOAJUCHITLAN"). Con
    `text_x_tolerance=1` la extracción es correcta en todo el corpus probado.
  - El nombre más confiable viene del bloque de la cédula (QR): las líneas
    entre "Registro Federal de Contribuyentes" y "Nombre, denominación o razón
    social". Para PF ahí ya viene Nombre(s) + apellidos concatenado; el
    fallback arma el nombre desde las filas de la tabla de identificación.
  - Una tabla puede continuar en la página siguiente repitiendo su encabezado;
    por eso se recolectan filas de TODAS las tablas con encabezado reconocible.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .regimenes_fiscales import clave_de_regimen

logger = logging.getLogger("sat_descarga.csf")

# Sin esta tolerancia el SAT "pega" las palabras dentro de las celdas.
_TABLE_SETTINGS = {"text_x_tolerance": 1}

_RE_FECHA = re.compile(r"^\d{2}/\d{2}/\d{4}$")


@dataclass
class RegimenCsf:
    clave: str  # "" si la descripción no matcheó el catálogo
    descripcion: str


@dataclass
class ActividadCsf:
    descripcion: str
    porcentaje: Optional[float]  # None si la celda no parsea; entero cuando aplica
    principal: bool = False


@dataclass
class DatosCsf:
    rfc: Optional[str]
    nombre: str  # tal cual el SAT (MAYÚSCULAS)
    tipo_persona: str  # "PF" | "PM" | "" si no se pudo determinar
    regimenes: list[RegimenCsf] = field(default_factory=list)
    actividades: list[ActividadCsf] = field(default_factory=list)


def _celda(valor) -> str:
    """Celda cruda de pdfplumber → texto en una línea (None → "")."""
    return " ".join((valor or "").split())


def _sin_espacios(texto: str) -> str:
    """Clave de comparación tolerante a espacios perdidos por la extracción."""
    return re.sub(r"\s+", "", texto).lower()


def _nombre_desde_cedula(tablas: list) -> str:
    """
    Nombre desde el bloque de la cédula (QR): líneas entre "Registro Federal
    de Contribuyentes" y "Nombre, denominación o razón social".
    """
    for tabla in tablas:
        for fila in tabla:
            for celda in fila:
                if not celda or "Registro Federal de Contribuyentes" not in celda:
                    continue
                lineas = [" ".join(l.split()) for l in celda.splitlines()]
                inicio = fin = None
                for i, linea in enumerate(lineas):
                    plano = _sin_espacios(linea)
                    if plano == "registrofederaldecontribuyentes":
                        inicio = i
                    elif inicio is not None and plano.startswith("nombre,denominaci"):
                        fin = i
                        break
                if inicio is not None and fin is not None and fin > inicio + 1:
                    nombre = " ".join(l for l in lineas[inicio + 1:fin] if l)
                    if nombre:
                        return nombre
    return ""


def _valor_identificacion(tablas: list, *etiquetas: str) -> Optional[str]:
    """
    Valor de una fila etiqueta→valor de la tabla "Datos de Identificación del
    Contribuyente". `etiquetas` se comparan sin espacios ni mayúsculas.
    """
    planas = [_sin_espacios(e) for e in etiquetas]
    for tabla in tablas:
        for fila in tabla:
            if len(fila) < 2:
                continue
            etiqueta = _sin_espacios(_celda(fila[0]))
            if etiqueta in planas:
                return _celda(fila[1])
    return None


def _filas_de_seccion(tablas: list, *encabezados: str) -> list[list[str]]:
    """
    Filas de datos de las tablas cuyo encabezado contenga TODOS los
    `encabezados`. Junta las de todas las páginas (las tablas que continúan
    en la página siguiente repiten su encabezado).
    """
    planos = [_sin_espacios(e) for e in encabezados]
    filas: list[list[str]] = []
    for tabla in tablas:
        idx_encabezado = None
        for i, fila in enumerate(tabla):
            fila_plana = _sin_espacios(" ".join(_celda(c) for c in fila))
            if all(p in fila_plana for p in planos):
                idx_encabezado = i
                break
        if idx_encabezado is None:
            continue
        for fila in tabla[idx_encabezado + 1:]:
            normalizada = [_celda(c) for c in fila]
            if any(normalizada):
                filas.append(normalizada)
    return filas


def _parse_porcentaje(texto: str) -> Optional[float]:
    try:
        valor = float(texto.strip())
    except (ValueError, AttributeError):
        return None
    return int(valor) if valor.is_integer() else valor


def _parse_regimenes(tablas: list) -> list[RegimenCsf]:
    regimenes: list[RegimenCsf] = []
    for fila in _filas_de_seccion(tablas, "Régimen", "Fecha Inicio"):
        if len(fila) < 2:
            continue
        descripcion, fecha_fin = fila[0], fila[-1] if len(fila) >= 3 else ""
        if not descripcion or fecha_fin:  # con Fecha Fin = régimen concluido
            continue
        clave = clave_de_regimen(descripcion)
        if clave is None:
            logger.warning("Régimen sin clave en el catálogo: %r", descripcion)
        regimenes.append(RegimenCsf(clave=clave or "", descripcion=descripcion))
    return regimenes


def _parse_actividades(tablas: list) -> list[ActividadCsf]:
    actividades: list[ActividadCsf] = []
    for fila in _filas_de_seccion(tablas, "Actividad Económica", "Porcentaje"):
        # [orden, descripción, porcentaje, fecha inicio, fecha fin]
        if len(fila) < 5 or not fila[1]:
            continue
        if fila[4]:  # con Fecha Fin = actividad concluida
            continue
        actividades.append(
            ActividadCsf(descripcion=fila[1], porcentaje=_parse_porcentaje(fila[2]))
        )
    # Mayor porcentaje primero (sort estable: empates conservan el orden del
    # SAT); la de mayor peso queda como principal.
    actividades.sort(key=lambda a: -(a.porcentaje if a.porcentaje is not None else 0))
    if actividades:
        actividades[0].principal = True
    return actividades


def parsear_contenido_csf(texto: str, tablas: list) -> DatosCsf:
    """
    Capa pura: texto completo + tablas crudas (celdas con saltos de línea y
    None tal como las entrega pdfplumber) → DatosCsf.
    """
    rfc = _valor_identificacion(tablas, "RFC:")
    if not rfc:
        m = re.search(r"^\s*RFC:?\s*([A-ZÑ&0-9]{12,13})\s*$", texto, re.MULTILINE)
        rfc = m.group(1) if m else None

    razon_social = _valor_identificacion(tablas, "Denominación/Razón Social:")
    tiene_campos_pf = _valor_identificacion(tablas, "Nombre (s):", "Nombre(s):") is not None

    if razon_social is not None:
        tipo_persona = "PM"
    elif tiene_campos_pf or _valor_identificacion(tablas, "CURP:") is not None:
        tipo_persona = "PF"
    elif rfc and len(rfc) in (12, 13):
        tipo_persona = "PM" if len(rfc) == 12 else "PF"
    else:
        tipo_persona = ""

    # El bloque de la cédula trae el nombre completo con espacios confiables;
    # las filas de identificación son el fallback.
    nombre = _nombre_desde_cedula(tablas)
    if not nombre:
        if tipo_persona == "PM":
            nombre = razon_social or ""
        else:
            partes = [
                _valor_identificacion(tablas, "Nombre (s):", "Nombre(s):"),
                _valor_identificacion(tablas, "Primer Apellido:", "PrimerApellido:"),
                _valor_identificacion(tablas, "Segundo Apellido:", "SegundoApellido:"),
            ]
            nombre = " ".join(p for p in partes if p)

    datos = DatosCsf(
        rfc=rfc,
        nombre=nombre.strip(),
        tipo_persona=tipo_persona,
        regimenes=_parse_regimenes(tablas),
        actividades=_parse_actividades(tablas),
    )

    if not datos.nombre and not datos.regimenes and not datos.actividades:
        raise ValueError("El PDF no parece una Constancia de Situación Fiscal.")
    return datos


def _extraer_pdf(pdf_path: Path) -> tuple[str, list]:
    """Única capa que toca pdfplumber: PDF → (texto completo, tablas crudas)."""
    try:
        import pdfplumber
    except ImportError as e:  # instalación incompleta
        raise RuntimeError(
            "Falta la librería pdfplumber para leer la constancia "
            "(reinstala con `pip install -e .`)."
        ) from e

    textos: list[str] = []
    tablas: list = []
    with pdfplumber.open(pdf_path) as pdf:
        for pagina in pdf.pages:
            textos.append(pagina.extract_text(x_tolerance=_TABLE_SETTINGS["text_x_tolerance"]) or "")
            tablas.extend(pagina.extract_tables(_TABLE_SETTINGS) or [])
    return "\n".join(textos), tablas


def parsear_csf(pdf_path: str | Path) -> DatosCsf:
    """
    Parsea una Constancia de Situación Fiscal descargada.

    Lanza ValueError si el PDF no parece una CSF y RuntimeError si falta la
    librería de lectura; cualquier otro error de lectura se propaga tal cual.
    """
    ruta = Path(pdf_path)
    if not ruta.is_file():
        raise FileNotFoundError(f"No existe el archivo: {ruta}")
    texto, tablas = _extraer_pdf(ruta)
    return parsear_contenido_csf(texto, tablas)

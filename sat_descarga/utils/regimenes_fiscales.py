"""
Catálogo de regímenes fiscales SAT (c_RegimenFiscal del Anexo 20 CFDI 4.0).

Archivo gemelo de `ui/src/lib/fiscal/regimenes-fiscales.ts` — mantener ambos en
espejo al agregar/retirar regímenes. Este lado lo consume el parser de la
Constancia de Situación Fiscal para mapear la descripción impresa en el PDF a
su clave de catálogo.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Optional

# {clave, descripcion, tipo_persona: "PF" | "PM" | "ambos"}
REGIMENES_FISCALES: list[dict] = [
    # Personas Morales
    {"clave": "601", "descripcion": "General de Ley Personas Morales", "tipo_persona": "PM"},
    {"clave": "603", "descripcion": "Personas Morales con Fines no Lucrativos", "tipo_persona": "PM"},
    {"clave": "620", "descripcion": "Sociedades Cooperativas de Producción", "tipo_persona": "PM"},
    {"clave": "622", "descripcion": "Actividades Agrícolas, Ganaderas, Silvícolas y Pesqueras", "tipo_persona": "PM"},
    {"clave": "623", "descripcion": "Opcional para Grupos de Sociedades", "tipo_persona": "PM"},
    {"clave": "624", "descripcion": "Coordinados", "tipo_persona": "PM"},

    # Personas Físicas
    {"clave": "605", "descripcion": "Sueldos y Salarios e Ingresos Asimilados a Salarios", "tipo_persona": "PF"},
    {"clave": "606", "descripcion": "Arrendamiento", "tipo_persona": "PF"},
    {"clave": "607", "descripcion": "Régimen de Enajenación o Adquisición de Bienes", "tipo_persona": "PF"},
    {"clave": "608", "descripcion": "Demás Ingresos", "tipo_persona": "PF"},
    {"clave": "610", "descripcion": "Residentes en el Extranjero sin Establecimiento Permanente en México", "tipo_persona": "PF"},
    {"clave": "611", "descripcion": "Ingresos por Dividendos (socios y accionistas)", "tipo_persona": "PF"},
    {"clave": "612", "descripcion": "Personas Físicas con Actividades Empresariales y Profesionales", "tipo_persona": "PF"},
    {"clave": "614", "descripcion": "Ingresos por Intereses", "tipo_persona": "PF"},
    {"clave": "615", "descripcion": "Régimen de los Ingresos por Obtención de Premios", "tipo_persona": "PF"},
    {"clave": "616", "descripcion": "Sin Obligaciones Fiscales", "tipo_persona": "PF"},
    {"clave": "621", "descripcion": "Incorporación Fiscal", "tipo_persona": "PF"},
    {"clave": "629", "descripcion": "De los Regímenes Fiscales Preferentes y de las Empresas Multinacionales", "tipo_persona": "PF"},

    # Ambos
    {"clave": "625", "descripcion": "Régimen de las Actividades Empresariales con Ingresos a través de Plataformas Tecnológicas", "tipo_persona": "ambos"},
    {"clave": "626", "descripcion": "Régimen Simplificado de Confianza", "tipo_persona": "ambos"},
]

# La CSF antepone "Régimen de/del/de los…" a nombres que el catálogo lista sin
# prefijo (y viceversa: 607/615/625/626 ya lo traen en el catálogo). Se quita
# en ambos lados antes de comparar.
_PREFIJO_REGIMEN = re.compile(r"^regimen\s+(de\s+(los|las|la|el)\s+|de\s+|del\s+)?")


def _normalizar(texto: str) -> str:
    """lowercase, sin acentos, espacios colapsados y sin prefijo 'Régimen de…'."""
    plano = unicodedata.normalize("NFD", texto.lower())
    plano = "".join(c for c in plano if not unicodedata.combining(c))
    plano = " ".join(plano.split())
    return _PREFIJO_REGIMEN.sub("", plano)


_CATALOGO_NORMALIZADO = [(_normalizar(r["descripcion"]), r) for r in REGIMENES_FISCALES]


def clave_de_regimen(descripcion_csf: str) -> Optional[str]:
    """
    Mapea la descripción de un régimen tal como viene en la CSF a su clave del
    catálogo. Tolerante a acentos, mayúsculas y al prefijo "Régimen de…".
    Devuelve None si no hay match razonable.
    """
    objetivo = _normalizar(descripcion_csf)
    if not objetivo:
        return None

    for normalizada, regimen in _CATALOGO_NORMALIZADO:
        if normalizada == objetivo:
            return regimen["clave"]

    # Containment bidireccional; si varios matchean gana la descripción más
    # larga del catálogo (la más específica).
    candidatos = [
        (len(normalizada), regimen)
        for normalizada, regimen in _CATALOGO_NORMALIZADO
        if normalizada in objetivo or objetivo in normalizada
    ]
    if candidatos:
        return max(candidatos, key=lambda c: c[0])[1]["clave"]
    return None

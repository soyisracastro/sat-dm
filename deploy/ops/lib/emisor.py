"""Compone la "cara" del emisor para una marca.

TodoConta y soycontador.ai son el MISMO contribuyente: mismo RFC, mismo banco,
distinta presentación. `data/emisor.json` guarda los datos fiscales y bancarios
una sola vez y una cara por marca; esta función los mezcla y devuelve el dict
**plano** que `cotizacion_pdf.py` ya espera (marca, submarca, nombre, rfc,
whatsapp, web, banco, condicionesDefault, vigenciaDias, notaIva).

Que devuelva la forma plana es a propósito: así el generador de PDF no se entera
del cambio de estructura y no hubo que tocarlo.

Uso:
    from lib import emisor
    e = emisor.cargar("soycontador")   # o "todoconta", o sin argumento
"""

from __future__ import annotations

import json
from pathlib import Path

DATA = Path(__file__).resolve().parent.parent / "data"


class MarcaDesconocida(KeyError):
    """La marca pedida no existe en emisor.json — mejor fallar que inventar."""


def cargar(marca: str | None = None, ruta: Path | None = None) -> dict:
    """Devuelve el emisor plano para `marca`.

    Sin `marca`, usa `marcaPorDefecto`. Si la marca no existe, lanza
    MarcaDesconocida en vez de caer a un default silencioso: una cotización con
    el membrete equivocado es peor que una que no se genera.
    """
    archivo = ruta or (DATA / "emisor.json")
    datos = json.loads(archivo.read_text(encoding="utf-8"))

    clave = marca or datos.get("marcaPorDefecto")
    marcas = datos.get("marcas", {})
    if clave not in marcas:
        raise MarcaDesconocida(
            f"marca '{clave}' no está en emisor.json (hay: {', '.join(sorted(marcas))})"
        )

    cara = marcas[clave]
    defaults = datos.get("defaults", {})

    plano = {
        **datos.get("fiscal", {}),
        "banco": datos.get("banco", {}),
        "vigenciaDias": defaults.get("vigenciaDias", 15),
        "notaIva": defaults.get("notaIva", ""),
        # Las condiciones de la marca ganan sobre las generales: el taller de
        # soycontador.ai cobra por adelantado y TodoConta no.
        "condicionesDefault": cara.get(
            "condicionesDefault", defaults.get("condicionesDefault", [])
        ),
        **{k: v for k, v in cara.items() if k != "condicionesDefault"},
    }
    return plano


def marca_para_alias(alias: str) -> str:
    """Qué cara usar según el alias por el que entró el correo.

    Se decide por el DOMINIO, no por el nombre del buzón: `hola@soycontador.ai`
    y `soporte@soycontador.ai` son la misma marca.
    """
    dominio = alias.split("@")[-1].strip().lower()
    return "soycontador" if dominio.endswith("soycontador.ai") else "todoconta"

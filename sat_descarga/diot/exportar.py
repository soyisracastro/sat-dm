"""Generación del archivo .txt de carga masiva de la DIOT.

Formato (docs/diot-2025.md): una línea por tercero, 54 campos unidos por pipe,
UTF-8 **con BOM** y saltos CRLF — igual que la plantilla de Excel de TodoConta
que ya funciona contra el portal del SAT.
"""

from __future__ import annotations

import re

from .layout import formatear_linea
from .validaciones import validar_filas


class DiotInvalida(ValueError):
    """La tabla tiene errores que violan el instructivo del SAT."""

    def __init__(self, errores: list[dict]):
        self.errores = errores
        mensajes = "; ".join(e["mensaje"] for e in errores[:5])
        extra = f" (y {len(errores) - 5} más)" if len(errores) > 5 else ""
        super().__init__(f"La DIOT tiene {len(errores)} error(es): {mensajes}{extra}")


def exportar_txt(filas: list[dict]) -> bytes:
    """Serializa los renglones al .txt del SAT. Lanza DiotInvalida si hay errores."""
    if not filas:
        raise DiotInvalida([{"fila": None, "campo": None, "mensaje": "No hay renglones que exportar"}])
    resultado = validar_filas(filas)
    if resultado["errores"]:
        raise DiotInvalida(resultado["errores"])
    lineas = [formatear_linea(f) for f in filas]
    # CRLF tras cada línea, incluida la última (como la plantilla de Excel).
    contenido = "\r\n".join(lineas) + "\r\n"
    return contenido.encode("utf-8-sig")


def nombre_archivo(rfc: str | None, periodo: str) -> str:
    """`{RFC}_diot_{YYYY-MM}.txt`; si el RFC no es válido se omite."""
    rfc_limpio = (rfc or "").strip().upper()
    if not re.fullmatch(r"[A-ZÑ&0-9]{12,13}", rfc_limpio):
        rfc_limpio = ""
    partes = [p for p in (rfc_limpio, "diot", periodo) if p]
    return "_".join(partes) + ".txt"

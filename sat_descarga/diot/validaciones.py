"""Validaciones de renglones DIOT antes de exportar.

Devuelve dos niveles (ver reglas textuales en docs/diot-2025.md):
- ``errores``: violan el instructivo del SAT → bloquean la exportación.
- ``advertencias``: no bloquean, pero el usuario debería revisarlas.

Cada hallazgo: {"fila": índice 0-based, "campo": clave | None, "mensaje": str}.
"""

from __future__ import annotations

import re

from .catalogos import (
    MANIFIESTO,
    OPERACIONES_POR_TERCERO,
    PAISES,
    RFC_GLOBAL,
    TIPO_TERCERO,
)
from .layout import CAMPOS_DIOT, CAMPOS_ENTEROS

_RFC_RE = re.compile(r"^[A-ZÑ&0-9]{12,13}$")
MAX_POSICIONES = 14

# Pares (devoluciones ≤ valor total) que el SAT valida explícitamente.
_PARES_DEV = (
    ("dev_rf_norte", "valor_rf_norte"),
    ("dev_rf_sur", "valor_rf_sur"),
    ("dev_16", "valor_16"),
    ("dev_imp_aduana_16", "valor_imp_aduana_16"),
    ("dev_imp_intang_16", "valor_imp_intang_16"),
)

_ETIQUETAS = {c.clave: c.etiqueta for c in CAMPOS_DIOT}


def _entero_o_none(valor) -> int | None:
    try:
        return int(round(float(valor or 0)))
    except (TypeError, ValueError):
        return None


def validar_filas(filas: list[dict]) -> dict:
    """Valida la tabla completa. Devuelve {"errores": [...], "advertencias": [...]}."""
    errores: list[dict] = []
    advertencias: list[dict] = []

    def error(i: int, campo: str | None, mensaje: str) -> None:
        errores.append({"fila": i, "campo": campo, "mensaje": mensaje})

    def advertir(i: int, campo: str | None, mensaje: str) -> None:
        advertencias.append({"fila": i, "campo": campo, "mensaje": mensaje})

    vistos: dict[tuple[str, str], int] = {}
    for i, fila in enumerate(filas):
        tercero = str(fila.get("tipo_tercero", "")).strip()
        operacion = str(fila.get("tipo_operacion", "")).strip()
        rfc = str(fila.get("rfc", "")).strip().upper()
        pais = str(fila.get("pais", "")).strip().upper()
        quien = rfc or fila.get("nombre") or f"renglón {i + 1}"

        # Tipo de tercero y de operación (catálogos oficiales).
        if tercero not in TIPO_TERCERO:
            error(i, "tipo_tercero", f"Tipo de tercero inválido en {quien}: {tercero!r}")
        elif operacion not in OPERACIONES_POR_TERCERO[tercero]:
            validas = ", ".join(OPERACIONES_POR_TERCERO[tercero])
            error(
                i, "tipo_operacion",
                f"Tipo de operación {operacion!r} no aplica para tercero {tercero} "
                f"en {quien} (válidos: {validas})",
            )

        # RFC según el tipo de tercero.
        if tercero == "04":
            if not rfc:
                error(i, "rfc", f"El RFC es obligatorio para proveedor nacional ({quien})")
            elif not _RFC_RE.match(rfc):
                error(i, "rfc", f"RFC con formato inválido: {rfc}")
        elif tercero == "15":
            if rfc != RFC_GLOBAL:
                error(i, "rfc", f"El proveedor global debe llevar RFC {RFC_GLOBAL}")
        elif tercero == "05":
            if rfc and not _RFC_RE.match(rfc):
                error(i, "rfc", f"RFC con formato inválido: {rfc}")
            # Campos obligatorios del extranjero.
            if not str(fila.get("id_fiscal", "")).strip():
                error(i, "id_fiscal", f"El núm. de identificación fiscal es obligatorio para extranjero ({quien})")
            if not str(fila.get("nombre_extranjero", "")).strip():
                error(i, "nombre_extranjero", f"El nombre del extranjero es obligatorio ({quien})")
            if not pais:
                error(i, "pais", f"El país de residencia fiscal es obligatorio para extranjero ({quien})")
            elif pais not in PAISES:
                error(i, "pais", f"País fuera del catálogo del SAT: {pais!r}")
            if pais == "ZZZ" and not str(fila.get("lugar_jurisdiccion", "")).strip():
                error(i, "lugar_jurisdiccion", f"Con país ZZZ (Otro) debes especificar el lugar de jurisdicción ({quien})")

        # Manifiesto (obligatorio).
        if str(fila.get("manifiesto", "")).strip() not in MANIFIESTO:
            error(i, "manifiesto", f"El manifiesto de efectos fiscales debe ser 01 (Sí) o 02 (No) en {quien}")

        # Montos: enteros, no negativos, máximo 14 posiciones.
        con_monto = False
        for clave in CAMPOS_ENTEROS:
            monto = _entero_o_none(fila.get(clave))
            if monto is None:
                error(i, clave, f"Monto no numérico en «{_ETIQUETAS[clave]}» ({quien})")
                continue
            if monto < 0:
                error(
                    i, clave,
                    f"Monto negativo en «{_ETIQUETAS[clave]}» ({quien}). La DIOT no acepta "
                    "negativos: captura las notas de crédito en los campos de devoluciones.",
                )
            if len(str(abs(monto))) > MAX_POSICIONES:
                error(i, clave, f"Monto excede 14 posiciones en «{_ETIQUETAS[clave]}» ({quien})")
            if monto > 0:
                con_monto = True

        # Devoluciones ≤ valor total (regla explícita del instructivo).
        for clave_dev, clave_valor in _PARES_DEV:
            dev = _entero_o_none(fila.get(clave_dev)) or 0
            valor = _entero_o_none(fila.get(clave_valor)) or 0
            if dev > valor:
                error(
                    i, clave_dev,
                    f"Las devoluciones ({dev}) superan el valor de los actos ({valor}) "
                    f"en «{_ETIQUETAS[clave_valor]}» para {quien}. El SAT exige "
                    "devoluciones ≤ valor; ajusta los montos.",
                )

        if not con_monto:
            advertir(i, None, f"El renglón de {quien} no tiene ningún monto mayor a cero")

        if fila.get("estimado"):
            advertir(
                i, None,
                f"Las bases de {quien} incluyen CFDIs cargados con una versión anterior: "
                "la base 16% se estimó desde el IVA. Recarga los XMLs para el dato exacto.",
            )

        # Renglones duplicados (mismo RFC + tipo de operación).
        if rfc:
            llave = (rfc, operacion)
            if llave in vistos:
                advertir(
                    i, "rfc",
                    f"{rfc} con tipo de operación {operacion} ya aparece en el "
                    f"renglón {vistos[llave] + 1}; el SAT los tratará como registros separados",
                )
            else:
                vistos[llave] = i

    return {"errores": errores, "advertencias": advertencias}

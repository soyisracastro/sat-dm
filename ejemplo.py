#!/usr/bin/env python3
"""
Ejemplo de uso de sat_descarga como librería Python.

Para el CLI interactivo multi-empresa, usa:
    uv run python sat_dm.py descargar

Este script muestra cómo usar la API directamente.
"""

import logging
import sys
from datetime import date
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

from sat_descarga import descargar_cfdi, verificar_solicitud_existente

# ---------------------------------------------------------------------------
# Configuración — ajustar antes de usar
# ---------------------------------------------------------------------------

CER_PATH = "efirma/XAXX010101000/fiel.cer"  # Ruta a tu certificado
KEY_PATH = "efirma/XAXX010101000/fiel.key"   # Ruta a tu llave privada
PASSWORD = "tu_contraseña"

FECHA_INICIO = date(2025, 1, 1)
FECHA_FIN = date(2025, 12, 31)
TIPO_COMPROBANTE = "E"                        # "E" = emitidos | "R" = recibidos
ESTADO_COMPROBANTE = "Vigente"                # "Vigente" | "Cancelado" | "Todos"

DIRECTORIO_SALIDA = "./descargas/"


# ---------------------------------------------------------------------------
# Flujo 1: Descarga completa (solicitud + espera + descarga)
# ---------------------------------------------------------------------------

def flujo_completo():
    print(f"\n=== Descarga Masiva de CFDIs ===")
    print(f"  Periodo: {FECHA_INICIO} a {FECHA_FIN}")
    print(f"  Tipo: {TIPO_COMPROBANTE} / Estado: {ESTADO_COMPROBANTE}\n")

    zips = descargar_cfdi(
        cer_path=CER_PATH,
        key_path=KEY_PATH,
        password=PASSWORD,
        fecha_inicio=FECHA_INICIO,
        fecha_fin=FECHA_FIN,
        tipo_comprobante=TIPO_COMPROBANTE,
        estado_comprobante=ESTADO_COMPROBANTE,
        directorio_salida=DIRECTORIO_SALIDA,
        extraer=True,
    )

    if zips:
        print(f"\nDescarga exitosa: {len(zips)} paquete(s)")
        for z in zips:
            cfdi_dir = Path(DIRECTORIO_SALIDA) / z.stem
            xmls = list(cfdi_dir.glob("*.xml")) if cfdi_dir.exists() else []
            print(f"  {z.name}: {len(xmls)} XMLs")
    else:
        print("\nNo se encontraron CFDIs para el periodo indicado.")


# ---------------------------------------------------------------------------
# Flujo 2: Retomar solicitud previa
# ---------------------------------------------------------------------------

def retomar_solicitud(id_solicitud: str):
    print(f"\n=== Retomando solicitud: {id_solicitud} ===\n")

    zips = verificar_solicitud_existente(
        cer_path=CER_PATH,
        key_path=KEY_PATH,
        password=PASSWORD,
        id_solicitud=id_solicitud,
        directorio_salida=DIRECTORIO_SALIDA,
        extraer=True,
        poll=True,
    )

    if zips:
        print(f"\nDescargados {len(zips)} paquete(s).")
    else:
        print("\nLa solicitud aun no esta lista.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        retomar_solicitud(sys.argv[1])
    else:
        flujo_completo()

#!/usr/bin/env python3
"""
Prueba de descarga de la Constancia de Situación Fiscal (CSF) usando e.firma (FIEL).

Uso:
    python prueba_constancia_fiel.py RUTA.cer RUTA.key CONTRASEÑA [directorio_salida]

Se abre un Chromium VISIBLE. El script intenta seleccionar .cer/.key + contraseña en
la pestaña e.firma automáticamente; si no lo logra, complétalo TÚ en el browser (la
e.firma no tiene captcha). Tras el login, da clic en «Generar Constancia» y guarda el PDF.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if len(sys.argv) < 4:
    print(__doc__)
    sys.exit(1)

cer = sys.argv[1]
key = sys.argv[2]
password = sys.argv[3]
salida = sys.argv[4] if len(sys.argv) > 4 else "./constancia_fiel/"

print(f"\n.cer:   {cer}")
print(f".key:   {key}")
print(f"Salida: {salida}")
print("\nAbriendo browser... selecciona/confirma la e.firma cuando aparezca.\n")

from sat_descarga.constancia import descargar_constancia_fiel

pdf = descargar_constancia_fiel(
    cer_path=cer, key_path=key, password=password, directorio_salida=salida,
)

if pdf:
    print(f"\n✓ Constancia descargada: {pdf}")
else:
    print("\n✗ No se pudo descargar la constancia (revisa el log de arriba).")
    sys.exit(1)

#!/usr/bin/env python3
"""
Prueba de descarga de la Constancia de Situación Fiscal (CSF) vía portal CIEC.

Uso:
    python prueba_constancia.py RFC CIEC [directorio_salida] [URL_ENTRADA]

Se abre un Chromium VISIBLE: resuelve el captcha y haz clic en «Enviar». El script
detecta el login, da clic en «Generar constancia» y guarda el PDF.

URL_ENTRADA: opcional; la URL por donde inicias el login (la que abres/tecleas tú).
Útil porque las URLs SSO del SAT pueden traer parámetros de sesión.
"""

import sys
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

rfc = sys.argv[1]
ciec = sys.argv[2]
salida = sys.argv[3] if len(sys.argv) > 3 else f"./constancia_{rfc.upper()}/"
url_entrada = sys.argv[4] if len(sys.argv) > 4 else None

print(f"\nRFC:    {rfc}")
print(f"Salida: {salida}")
print("\nAbriendo browser... resuelve el captcha cuando aparezca.\n")

from sat_descarga.constancia import descargar_constancia_ciec, CSF_URL_ENTRADA

pdf = descargar_constancia_ciec(
    rfc=rfc, ciec=ciec, directorio_salida=salida,
    url_entrada=url_entrada or CSF_URL_ENTRADA,
)

if pdf:
    print(f"\n✓ Constancia descargada: {pdf}")
else:
    print("\n✗ No se pudo descargar la constancia (revisa el log de arriba).")
    sys.exit(1)

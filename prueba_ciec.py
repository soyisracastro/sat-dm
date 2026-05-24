#!/usr/bin/env python3
"""
Prueba del módulo CIEC.

Uso:
    python prueba_ciec.py RFC CIEC [fecha_inicio] [fecha_fin] [R|E|RE]

El 5º arg: R=recibidos, E=emitidos, RE/ambos (default si se omite).
Con "ambos" se baja todo con UN solo captcha; cada tipo va a su subcarpeta.

Ejemplo:
    python prueba_ciec.py XAXX010101000 miClaveCIEC 2025-01-01 2025-01-31      # ambos
    python prueba_ciec.py XAXX010101000 miClaveCIEC 2025-01-01 2025-01-31 E    # solo emitidos

Se abrirá una ventana de Chromium. Tienes hasta 3 minutos para resolver el
captcha y hacer clic en "Enviar". El script continúa automáticamente tras el login.
"""

import sys
import logging
from datetime import date

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

# --- Leer argumentos ---
if len(sys.argv) < 3:
    print(__doc__)
    sys.exit(1)

rfc   = sys.argv[1]
ciec  = sys.argv[2]
fi    = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date(2025, 1, 1)
ff    = date.fromisoformat(sys.argv[4]) if len(sys.argv) > 4 else date(2025, 1, 31)
tipo  = sys.argv[5] if len(sys.argv) > 5 else "RE"  # R, E, o RE=ambos (default)

_etiqueta = {"R": "Recibidos", "E": "Emitidos"}.get(tipo.upper(), "Ambos (recibidos + emitidos)")
print(f"\nRFC:    {rfc}")
print(f"Periodo: {fi} → {ff}")
print(f"Tipo:    {_etiqueta}")
print(f"\nAbriendo browser... resuelve el captcha cuando aparezca.\n")

from sat_descarga.ciec import descargar_cfdi_ciec

archivos = descargar_cfdi_ciec(
    rfc=rfc,
    ciec=ciec,
    fecha_inicio=fi,
    fecha_fin=ff,
    tipo_comprobante=tipo,
    directorio_salida=f"./cfdi_ciec_{rfc}/",
    max_registros=2000,  # tope alto; la cuota diaria del portal manda
)

print(f"\n✓ Descargados: {len(archivos)} XMLs")
for a in archivos[:10]:
    print(f"  {a}")
if len(archivos) > 10:
    print(f"  ... y {len(archivos)-10} más")

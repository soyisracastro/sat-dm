"""
Envío del Requerimiento de Renovación de e.firma (`.ren`) al portal CertiSAT Web
con autenticación por e.firma (FIEL). Reutiliza toda la mecánica del CSD
(`csd.py`): el login NIDP, el número de operación, el seguimiento y la
recuperación del `.cer` son idénticos; solo cambian el menú, el input del archivo
y el nombre del acuse (ver docs/renovacion-efirma-csd.md).

Flujo (confirmado 2026-07-08 contra el SAT real, docs/path-renovacion-efirma.md):
  login e.firma → `renovacion.do?menu=renovacion` → subir el `.ren` (input
  `#txtFileRen`, name `renovacion`) → «Renovar» → número de operación → Seguimiento
  (acuse `Acuse_renovacion.pdf`) → Recuperación → descarga del `.cer` NUEVO.

⚠️ La renovación SUSTITUYE la e.firma vigente: tras el trámite, el certificado
anterior queda revocado y hay que usar el `.cer` nuevo + la `.key` generada junto
al `.ren`. Además el SAT tarda horas en reconocer la e.firma nueva para login.
"""

import logging
from typing import Optional

from .csd import CSDPortalClient, CSD_LANDING_HOST

logger = logging.getLogger(__name__)

# Único cambio de URL vs CSD: el menú de subida del `.ren`.
RENOVACION_URL = f"https://{CSD_LANDING_HOST}/certisat/renovacion.do?menu=renovacion"


class RenovacionPortalClient(CSDPortalClient):
    """Envía el `.ren` y recupera la e.firma renovada. Igual que CSD salvo estos
    atributos de clase."""

    MENU_URL = RENOVACION_URL
    FILE_INPUT = "#txtFileRen"          # input file del `.ren` (name="renovacion")
    ACUSE_PREFIX = "Acuse_renovacion"
    ETIQUETA = "REN"


def enviar_renovacion_fiel(
    cer_path: str,
    key_path: str,
    password: str,
    ren_path: str,
    directorio_salida: str = "./renovacion/",
    key_nueva_path: Optional[str] = None,
    headless: bool = True,
    recuperar: bool = True,
    intentos_cert: int = 6,
    espera_cert_s: int = 30,
    on_progreso=None,
) -> dict:
    """
    Sube un `.ren` (Requerimiento de Renovación de e.firma) a CertiSAT Web y
    devuelve el número de operación + acuse; opcionalmente recupera el `.cer` nuevo.

    `cer_path`/`key_path`/`password` son la e.firma VIGENTE (con la que se firma el
    login y el `.ren`). `key_nueva_path` es la `.key` nueva generada junto al `.ren`:
    si se pasa, confirma que el certificado recuperado es el renovado (empareja).
    `on_progreso(fase, data)` refleja el avance para la UI (ver csd.py).
    """
    client = RenovacionPortalClient(cer_path, key_path, password, headless=headless,
                                    on_progreso=on_progreso)
    return client.enviar(
        ren_path, directorio_salida=directorio_salida, key_nueva_path=key_nueva_path,
        recuperar=recuperar, intentos_cert=intentos_cert, espera_cert_s=espera_cert_s,
    )


def recuperar_renovacion_fiel(
    cer_path: str,
    key_path: str,
    password: str,
    directorio_salida: str = "./renovacion/",
    key_nueva_path: Optional[str] = None,
    headless: bool = True,
    intentos: int = 10,
    espera_s: int = 30,
    on_progreso=None,
) -> dict:
    """Descarga el `.cer` de la e.firma renovada (para cuando no estaba listo al
    enviar; tarda minutos). Con `key_nueva_path` verifica el emparejamiento.

    OJO: puede usarse con la e.firma VIGENTE para el login mientras el SAT aún la
    reconozca; una vez que la nueva sea válida, se usa la nueva para autenticar."""
    client = RenovacionPortalClient(cer_path, key_path, password, headless=headless,
                                    on_progreso=on_progreso)
    return client.recuperar(
        directorio_salida=directorio_salida, key_nueva_path=key_nueva_path,
        intentos=intentos, espera_s=espera_s,
    )

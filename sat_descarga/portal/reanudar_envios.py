"""Reanudación de envíos pendientes de contabilidad electrónica.

Compartido por `sat-dm ce reanudar` y por el poller de la app (por eso vive en
`portal/` y no en `cli/`: la API no debe importar el CLI). La cola la llena
`cli/contabilidad.py` cuando un envío agota reintentos por errores TRANSITORIOS
del SAT (lentitud, mantenimiento sin aviso, la carrera del xmlTemp) — nunca por
errores de fondo.

Idempotencia: `EnviadorCE.enviar(omitir_enviados=True)` consulta el portal
antes de subir, así que reanudar un pendiente cuyo lote ya entró (total o
parcialmente) no duplica nada: los ya presentados se omiten y el registro se
cierra como "completado".
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Callable, Optional

from ..core.errores import ErrorEsperado

logger = logging.getLogger(__name__)


def reanudar_envios_ce(
    rfc: str,
    cer_path: str,
    key_path: str,
    password: str,
    *,
    headless: bool = True,
    destino_de: Optional[Callable[[dict], Path]] = None,
    progreso: Optional[Callable[[str], None]] = None,
    on_progreso: Optional[Callable[[str, dict], None]] = None,
) -> dict:
    """Retoma los envíos pendientes de un RFC. Devuelve un resumen.

    Estructura del resumen: ``{"reanudados": [ids], "completados": [ids],
    "aun_pendientes": [ids], "sin_pendientes": bool}``.
    """
    from ..cli import config_store  # solo el store; no toca comandos click
    from .contabilidad_electronica import EnviadorCE, RE_ERROR_TRANSITORIO

    pendientes = [e for e in config_store.get_envios_pendientes(rfc)
                  if e.get("tramite") == "ce"]
    resumen = {"reanudados": [], "completados": [], "aun_pendientes": [],
               "sin_pendientes": not pendientes}
    if not pendientes:
        return resumen

    enviador = EnviadorCE(headless=headless, progreso=progreso,
                          on_progreso=on_progreso)
    for envio in pendientes:
        eid = envio["id"]
        archivos = [a for a in envio.get("archivos", []) if Path(a).is_file()]
        desaparecidos = [a for a in envio.get("archivos", []) if a not in archivos]
        if desaparecidos:
            logger.warning("[CE] %d archivo(s) del pendiente %s ya no existen "
                           "en disco; se descartan: %s",
                           len(desaparecidos), eid, desaparecidos)
        if not archivos:
            config_store.update_envio(rfc, eid, estado="abandonado",
                                      error="los archivos ya no existen en disco")
            continue

        params = envio.get("params") or {}
        config_store.update_envio(rfc, eid, estado="curso")
        resumen["reanudados"].append(eid)
        try:
            res = enviador.enviar(
                cer_path, key_path, password, archivos,
                sellar=params.get("sellar", True),
                enviar=True,
                motivo=params.get("motivo", "mensual"),
                destino_de=destino_de,
                omitir_enviados=True,   # la idempotencia real
            )
        except ErrorEsperado as e:
            # el SAT sigue caído: el pendiente se queda tal cual, con el error
            config_store.update_envio(rfc, eid, estado="pendiente", error=str(e))
            resumen["aun_pendientes"].append(eid)
            continue
        except Exception as e:  # noqa: BLE001 — bug real: no perder el pendiente
            config_store.update_envio(rfc, eid, estado="pendiente", error=str(e))
            resumen["aun_pendientes"].append(eid)
            raise

        transitorios = [f for f in res["fallidos"]
                        if RE_ERROR_TRANSITORIO.search(f.get("mensaje") or "")]
        if transitorios:
            config_store.update_envio(
                rfc, eid, estado="pendiente",
                archivos=[f["path"] for f in transitorios],
                error=(transitorios[0].get("mensaje") or "")[:300])
            resumen["aun_pendientes"].append(eid)
        else:
            folios = {r["archivo"]: r.get("folio")
                      for r in res["enviados"] if r.get("folio")}
            omitidos = {r["archivo"]: r.get("estatus")
                        for r in res.get("omitidos", [])}
            config_store.update_envio(
                rfc, eid, estado="completado",
                resultado={"folios": folios, "omitidos": omitidos,
                           "fallidos_de_fondo": [f["archivo"]
                                                 for f in res["fallidos"]]})
            resumen["completados"].append(eid)
    return resumen

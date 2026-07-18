"""Persistencia de las tareas personales en ``~/.sat-descarga/tareas.json``.

Las tareas son del usuario (no por empresa): un solo archivo global, con el
mismo patrón resiliente del resto de la config (escritura atómica + fsync,
lectura tolerante a encodings legacy, ``RLock`` para read-modify-write).

Esquema (versión explícita para migraciones futuras):
    {
      "version": 1,
      "tareas": [
        {
          "id": "a1b2c3d4e5f6",
          "titulo": "Presentar DIOT de junio",
          "rfc": "XAXX010101000" | null,        # empresa vinculada (opcional)
          "tipo": "fiscal" | "manual" | "recurrente",
          "estado": "pendiente" | "curso" | "hecho",
          "prioridad": "alta" | "media" | "baja",
          "fecha": "YYYY-MM-DD" | null,          # fecha límite
          "origen": "manual" | "sugerencia",
          "sugerencia_id": "efirma-XAXX...-2026-08-01" | null,
          "creado_en": "...", "actualizado_en": "...",
          "completado_en": "..." | null,
          "eliminada_en": "..." | null,          # tombstone: borrada pero se
                                                 # conserva para que el borrado
                                                 # viaje en el sync
          "updated_at": "...Z",                  # stamp UTC del merge LWW
                                                 # (sync desktop ⇄ online)
          "gcal_event_id": null                  # reservado: sync con Google
                                                 # Calendar (docs/producto/tareas-gcal-sync.md)
        }
      ],
      "sugerencias_descartadas": ["diot-2026-06", ...]
    }

Las sugerencias se DERIVAN en el cliente (e.firma por vencer, DIOT del mes);
aquí solo persisten sus descartes y, vía ``sugerencia_id`` en la tarea, las
aceptadas — ambos suprimen la sugerencia al re-derivar.
"""

from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

from ..cli.config_store import (
    _ahora_sync,
    _load_json_resiliente,
    _ts_sync,
    _write_json_atomico,
    get_config_dir,
)

_tareas_lock = threading.RLock()

TIPOS = ("fiscal", "manual", "recurrente")
ESTADOS = ("pendiente", "curso", "hecho")
PRIORIDADES = ("alta", "media", "baja")

_FECHA_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\d|3[01])$")

# Campos que acepta `actualizar()` (PATCH); el resto los administra el store.
_CAMPOS_EDITABLES = frozenset(
    {"titulo", "rfc", "tipo", "estado", "prioridad", "fecha"}
)


def _path() -> Path:
    return get_config_dir() / "tareas.json"


def _vacio() -> dict:
    return {"version": 1, "tareas": [], "sugerencias_descartadas": []}


def _load() -> dict:
    data = _load_json_resiliente(_path(), _vacio)
    data.setdefault("version", 1)
    data.setdefault("tareas", [])
    data.setdefault("sugerencias_descartadas", [])
    return data


def _ahora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def validar_fecha(fecha: str | None) -> str | None:
    """Normaliza la fecha límite; ValueError si no es YYYY-MM-DD."""
    if not fecha:
        return None
    limpio = fecha.strip()
    if not _FECHA_RE.match(limpio):
        raise ValueError(f"Fecha inválida: {fecha!r} (formato YYYY-MM-DD)")
    return limpio


def listar() -> dict:
    """Estado completo: {"tareas": [...], "sugerencias_descartadas": [...]}.

    Los tombstones (``eliminada_en``) no salen: existen solo para que el
    borrado viaje en el sync entre instalaciones.
    """
    with _tareas_lock:
        data = _load()
        return {
            "tareas": [t for t in data["tareas"] if not t.get("eliminada_en")],
            "sugerencias_descartadas": data["sugerencias_descartadas"],
        }


def crear(
    titulo: str,
    *,
    rfc: str | None = None,
    tipo: str = "manual",
    estado: str = "pendiente",
    prioridad: str = "media",
    fecha: str | None = None,
    sugerencia_id: str | None = None,
) -> dict:
    """Crea la tarea (al inicio de la lista) y la devuelve.

    ValueError con mensaje en español si algún campo no es válido.
    """
    limpio = (titulo or "").strip()
    if not limpio:
        raise ValueError("El título de la tarea no puede ir vacío")
    if tipo not in TIPOS:
        raise ValueError(f"Tipo inválido: {tipo!r}")
    if estado not in ESTADOS:
        raise ValueError(f"Estado inválido: {estado!r}")
    if prioridad not in PRIORIDADES:
        raise ValueError(f"Prioridad inválida: {prioridad!r}")

    ahora = _ahora()
    tarea = {
        "id": uuid.uuid4().hex[:12],
        "titulo": limpio,
        "rfc": (rfc or "").strip().upper() or None,
        "tipo": tipo,
        "estado": estado,
        "prioridad": prioridad,
        "fecha": validar_fecha(fecha),
        "origen": "sugerencia" if sugerencia_id else "manual",
        "sugerencia_id": sugerencia_id,
        "creado_en": ahora,
        "actualizado_en": ahora,
        "completado_en": ahora if estado == "hecho" else None,
        "eliminada_en": None,
        "updated_at": _ahora_sync(),
        "gcal_event_id": None,
    }
    with _tareas_lock:
        data = _load()
        data["tareas"].insert(0, tarea)
        _write_json_atomico(_path(), data)
    return tarea


def actualizar(tarea_id: str, cambios: dict) -> dict | None:
    """Aplica un patch parcial y devuelve la tarea, o None si no existe.

    Solo campos de ``_CAMPOS_EDITABLES``; al pasar a "hecho" estampa
    ``completado_en`` (y lo limpia al reabrirla).
    """
    campos = {k: v for k, v in cambios.items() if k in _CAMPOS_EDITABLES}
    if "titulo" in campos:
        campos["titulo"] = (campos["titulo"] or "").strip()
        if not campos["titulo"]:
            raise ValueError("El título de la tarea no puede ir vacío")
    if "tipo" in campos and campos["tipo"] not in TIPOS:
        raise ValueError(f"Tipo inválido: {campos['tipo']!r}")
    if "estado" in campos and campos["estado"] not in ESTADOS:
        raise ValueError(f"Estado inválido: {campos['estado']!r}")
    if "prioridad" in campos and campos["prioridad"] not in PRIORIDADES:
        raise ValueError(f"Prioridad inválida: {campos['prioridad']!r}")
    if "fecha" in campos:
        campos["fecha"] = validar_fecha(campos["fecha"])
    if "rfc" in campos:
        campos["rfc"] = (campos["rfc"] or "").strip().upper() or None

    with _tareas_lock:
        data = _load()
        for tarea in data["tareas"]:
            if tarea["id"] != tarea_id or tarea.get("eliminada_en"):
                continue
            previo = tarea.get("estado")
            tarea.update(campos)
            tarea["actualizado_en"] = _ahora()
            tarea["updated_at"] = _ahora_sync()
            if "estado" in campos and campos["estado"] != previo:
                tarea["completado_en"] = (
                    _ahora() if campos["estado"] == "hecho" else None
                )
            _write_json_atomico(_path(), data)
            return tarea
    return None


def eliminar(tarea_id: str) -> bool:
    """Borra la tarea. Devuelve False si no existía.

    El borrado es un tombstone: la tarea se conserva oculta con
    ``eliminada_en`` para que también viaje en el sync — sin él, la tarea
    borrada aquí resucitaría con el siguiente pull de la otra instalación.
    """
    with _tareas_lock:
        data = _load()
        for tarea in data["tareas"]:
            if tarea["id"] != tarea_id or tarea.get("eliminada_en"):
                continue
            ahora = _ahora()
            tarea["eliminada_en"] = ahora
            tarea["actualizado_en"] = ahora
            tarea["updated_at"] = _ahora_sync()
            _write_json_atomico(_path(), data)
            return True
    return False


def descartar_sugerencia(sug_id: str) -> list[str]:
    """Registra el descarte (idempotente) y devuelve la lista completa."""
    limpio = (sug_id or "").strip()
    if not limpio:
        raise ValueError("Falta el id de la sugerencia")
    with _tareas_lock:
        data = _load()
        if limpio not in data["sugerencias_descartadas"]:
            data["sugerencias_descartadas"].append(limpio)
            _write_json_atomico(_path(), data)
        return data["sugerencias_descartadas"]


# ---------------------------------------------------------------------------
# Sync de tareas entre instalaciones (desktop ⇄ online) — mismo patrón que el
# catálogo de empresas (config_store): cada mutación estampa `updated_at`
# (UTC) en SU tarea y el backend (/api/desktop/tareas-sync) fusiona
# last-write-wins por fila. A diferencia de empresas, los borrados SÍ viajan
# vía tombstones (`eliminada_en`); no se purgan en v1 — pesan poco y purgarlos
# reabriría el ciclo de re-importación desde la nube. Los descartes de
# sugerencias se unen (idempotentes, sin LWW).
# ---------------------------------------------------------------------------

# `gcal_event_id` es un vínculo LOCAL de esta instalación con Google Calendar:
# no viaja ni se pisa al aplicar filas remotas.
_CAMPOS_SYNC = (
    "titulo", "rfc", "tipo", "estado", "prioridad", "fecha", "origen",
    "sugerencia_id", "creado_en", "actualizado_en", "completado_en",
    "eliminada_en",
)


def tareas_para_sync() -> dict:
    """
    Estado local en el shape que espera /api/desktop/tareas-sync (tombstones
    incluidos). Tareas previas al sync (sin `updated_at`) se estampan una sola
    vez con su `actualizado_en` para no ganar merges que no les tocan.
    """
    with _tareas_lock:
        data = _load()
        cambios = False
        tareas = []
        for t in data["tareas"]:
            if not t.get("updated_at"):
                t["updated_at"] = t.get("actualizado_en") or _ahora_sync()
                cambios = True
            fila = {"id": t["id"]}
            fila.update({campo: t.get(campo) for campo in _CAMPOS_SYNC})
            fila["updated_at"] = t["updated_at"]
            tareas.append(fila)
        if cambios:
            _write_json_atomico(_path(), data)
        return {
            "tareas": tareas,
            "sugerencias_descartadas": list(data["sugerencias_descartadas"]),
        }


def aplicar_sync_remoto(remotas: list, descartes: list) -> int:
    """
    Aplica el estado fusionado que devolvió el backend: pisa la tarea local
    solo cuando la fila remota es MÁS nueva (LWW por `updated_at`), crea las
    que no existan (tombstones incluidos, para que el borrado también
    converja) y une los descartes de sugerencias. Devuelve cuántas tareas
    cambió.
    """
    aplicadas = 0
    with _tareas_lock:
        data = _load()
        por_id = {t["id"]: t for t in data["tareas"]}
        for r in remotas:
            if not isinstance(r, dict):
                continue
            tarea_id = str(r.get("id") or "").strip()
            remoto_ts = _ts_sync(r.get("updated_at"))
            if not tarea_id or not remoto_ts:
                continue
            local = por_id.get(tarea_id)
            if local is not None and _ts_sync(local.get("updated_at")) >= remoto_ts:
                continue
            if local is None:
                local = {"id": tarea_id, "gcal_event_id": None}
                data["tareas"].append(local)
                por_id[tarea_id] = local
            for campo in _CAMPOS_SYNC:
                local[campo] = r.get(campo)
            if not local.get("titulo") and not local.get("eliminada_en"):
                local["titulo"] = "(sin título)"
            local["updated_at"] = r.get("updated_at")
            aplicadas += 1
        nuevos_descartes = [
            d for d in descartes
            if isinstance(d, str) and d and d not in data["sugerencias_descartadas"]
        ]
        if aplicadas or nuevos_descartes:
            data["sugerencias_descartadas"].extend(nuevos_descartes)
            # Orden estable entre instalaciones: la más reciente primero,
            # como las deja `crear()` localmente.
            data["tareas"].sort(key=lambda t: t.get("creado_en") or "", reverse=True)
            _write_json_atomico(_path(), data)
    return aplicadas

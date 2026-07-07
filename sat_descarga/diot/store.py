"""Persistencia del estado editable de la DIOT por empresa (RFC) y periodo.

Un archivo por empresa en ``~/.sat-descarga/diot/{RFC}.json`` (mismo patrón
que ``calculadoras/{RFC}.json``): el aislamiento entre empresas es estructural.

Esquema (versión explícita para migraciones futuras):
    {
      "version": 1,
      "periodos": {
        "2025-01": {
          "filas": [ {<54 claves del layout> + nombre/origen/estimado/num_cfdis}, ... ],
          "origen": "prellenado" | "manual",
          "generado_en": "...",
          "actualizado_en": "..."
        }
      }
    }

Guardar es full-replace de las filas del periodo: la UI manda la tabla
completa en cada PUT (debounced), no diffs.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime
from pathlib import Path

from ..cli.config_store import _load_json_resiliente, _write_json_atomico, get_config_dir

# Lock propio: serializa read-modify-write ante requests concurrentes del agente.
_diot_lock = threading.RLock()

_RFC_RE = re.compile(r"^[A-ZÑ&0-9]{12,13}$")
PERIODO_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")


def validar_periodo(periodo: str) -> str:
    if not PERIODO_RE.match(periodo or ""):
        raise ValueError(f"Periodo inválido: {periodo!r} (formato YYYY-MM)")
    return periodo


def _normalizar_rfc(rfc: str) -> str:
    """Valida el RFC para usarlo como nombre de archivo (evita path traversal)."""
    limpio = (rfc or "").strip().upper()
    if not _RFC_RE.match(limpio):
        raise ValueError(f"RFC inválido: {rfc!r}")
    return limpio


def _diot_dir() -> Path:
    d = get_config_dir() / "diot"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(rfc: str) -> Path:
    return _diot_dir() / f"{_normalizar_rfc(rfc)}.json"


def _vacio() -> dict:
    return {"version": 1, "periodos": {}}


def _load(rfc: str) -> dict:
    data = _load_json_resiliente(_path(rfc), _vacio)
    data.setdefault("version", 1)
    data.setdefault("periodos", {})
    return data


def get_periodo(rfc: str, periodo: str) -> dict | None:
    """Estado guardado del periodo (filas + metadatos), o None si no existe."""
    validar_periodo(periodo)
    with _diot_lock:
        return _load(rfc)["periodos"].get(periodo)


def set_periodo(rfc: str, periodo: str, filas: list[dict], origen: str = "manual") -> dict:
    """Persiste las filas del periodo (full-replace) y devuelve el estado."""
    validar_periodo(periodo)
    with _diot_lock:
        data = _load(rfc)
        previo = data["periodos"].get(periodo) or {}
        ahora = datetime.now().isoformat(timespec="seconds")
        estado = {
            "filas": filas,
            "origen": origen,
            "generado_en": previo.get("generado_en") or ahora
            if origen == "manual"
            else ahora,
            "actualizado_en": ahora,
        }
        data["periodos"][periodo] = estado
        _write_json_atomico(_path(rfc), data)
    return estado


def delete_periodo(rfc: str, periodo: str) -> bool:
    """Borra el estado del periodo. Devuelve False si no existía."""
    validar_periodo(periodo)
    with _diot_lock:
        data = _load(rfc)
        if periodo not in data["periodos"]:
            return False
        del data["periodos"][periodo]
        _write_json_atomico(_path(rfc), data)
    return True

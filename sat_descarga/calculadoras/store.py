"""Persistencia del estado de calculadoras por empresa (RFC).

Un archivo por empresa en ``~/.sat-descarga/calculadoras/{RFC}.json`` (mismo
patrón que ``historial/{RFC}.json``): el aislamiento entre empresas es
estructural — la empresa A y la B jamás comparten archivo, así que cambiar de
empresa nunca pisa el estado de otra. Sin empresa activa se persiste bajo
``__general__``.

Esquema (versión explícita para migraciones futuras):
    {
      "version": 1,
      "estados": { "<calculadora>": {"inputs": {...}, "resultado": {...},
                    "anio": 2026, "actualizado_en": "..."} },
      "guardados": [ {"id": "...", "calculadora": "...", "nombre": "...",
                      "inputs": {...}, "resultado": {...}, "creado_en": "..."} ]
    }

Se persisten inputs Y resultado: restaurar no recalcula, y un cálculo guardado
no cambia si el año siguiente cambian las constantes.
"""

from __future__ import annotations

import re
import threading
import uuid
from datetime import datetime
from pathlib import Path

from ..cli.config_store import _load_json_resiliente, _write_json_atomico, get_config_dir

# Lock propio (no el del catálogo): serializa read-modify-write de los archivos
# de calculadoras ante requests concurrentes del agente.
_calculadoras_lock = threading.RLock()

RFC_GENERAL = "__general__"
MAX_GUARDADOS = 500

CALCULADORAS_VALIDAS = frozenset(
    {"aguinaldo", "sbc", "isr", "finiquito", "liquidacion", "carga-patronal", "ptu"}
)

_RFC_RE = re.compile(r"^[A-ZÑ&0-9]{12,13}$")


def _normalizar_rfc(rfc: str | None) -> str:
    """Normaliza el RFC para usarlo como nombre de archivo, o ``__general__``.

    Rechaza cualquier valor que no sea un RFC válido (evita path traversal).
    """
    if not rfc:
        return RFC_GENERAL
    limpio = rfc.strip()
    if limpio.lower() == RFC_GENERAL:
        return RFC_GENERAL
    limpio = limpio.upper()
    if not _RFC_RE.match(limpio):
        raise ValueError(f"RFC inválido: {rfc!r}")
    return limpio


def _calculadoras_dir() -> Path:
    d = get_config_dir() / "calculadoras"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _path(rfc: str | None) -> Path:
    return _calculadoras_dir() / f"{_normalizar_rfc(rfc)}.json"


def _vacio() -> dict:
    return {"version": 1, "estados": {}, "guardados": []}


def _load(rfc: str | None) -> dict:
    data = _load_json_resiliente(_path(rfc), _vacio)
    data.setdefault("version", 1)
    data.setdefault("estados", {})
    data.setdefault("guardados", [])
    return data


def _validar_calculadora(calculadora: str) -> str:
    if calculadora not in CALCULADORAS_VALIDAS:
        validas = ", ".join(sorted(CALCULADORAS_VALIDAS))
        raise ValueError(f"Calculadora desconocida: {calculadora!r} (válidas: {validas})")
    return calculadora


def get_estado(rfc: str | None) -> dict:
    """Estado completo de la empresa: últimos estados por calculadora + guardados."""
    with _calculadoras_lock:
        return _load(rfc)


def get_estado_calculadora(rfc: str | None, calculadora: str) -> dict | None:
    """Último estado (inputs + resultado) de una calculadora, o None."""
    _validar_calculadora(calculadora)
    with _calculadoras_lock:
        return _load(rfc)["estados"].get(calculadora)


def set_estado_calculadora(
    rfc: str | None, calculadora: str, inputs: dict, resultado: dict, anio: int
) -> dict:
    """Persiste el último estado de una calculadora (auto-guardado al calcular)."""
    _validar_calculadora(calculadora)
    estado = {
        "inputs": inputs,
        "resultado": resultado,
        "anio": anio,
        "actualizado_en": datetime.now().isoformat(timespec="seconds"),
    }
    with _calculadoras_lock:
        data = _load(rfc)
        data["estados"][calculadora] = estado
        _write_json_atomico(_path(rfc), data)
    return estado


def add_guardado(
    rfc: str | None,
    calculadora: str,
    nombre: str,
    inputs: dict,
    resultado: dict,
    anio: int,
) -> dict:
    """Guarda un snapshot con nombre (explícito, botón "Guardar cálculo").

    Cap de ``MAX_GUARDADOS`` por empresa: al exceder se descartan los más viejos.
    """
    _validar_calculadora(calculadora)
    guardado = {
        "id": str(uuid.uuid4()),
        "calculadora": calculadora,
        "nombre": nombre.strip() or f"Cálculo de {calculadora}",
        "inputs": inputs,
        "resultado": resultado,
        "anio": anio,
        "creado_en": datetime.now().isoformat(timespec="seconds"),
    }
    with _calculadoras_lock:
        data = _load(rfc)
        data["guardados"].append(guardado)
        if len(data["guardados"]) > MAX_GUARDADOS:
            data["guardados"] = data["guardados"][-MAX_GUARDADOS:]
        _write_json_atomico(_path(rfc), data)
    return guardado


def list_guardados(rfc: str | None, calculadora: str | None = None) -> list[dict]:
    """Cálculos guardados de la empresa, recientes primero."""
    if calculadora is not None:
        _validar_calculadora(calculadora)
    with _calculadoras_lock:
        guardados = _load(rfc)["guardados"]
    if calculadora:
        guardados = [g for g in guardados if g.get("calculadora") == calculadora]
    return list(reversed(guardados))


def delete_guardado(rfc: str | None, guardado_id: str) -> bool:
    """Elimina un guardado por id. Devuelve False si no existía."""
    with _calculadoras_lock:
        data = _load(rfc)
        antes = len(data["guardados"])
        data["guardados"] = [g for g in data["guardados"] if g.get("id") != guardado_id]
        if len(data["guardados"]) == antes:
            return False
        _write_json_atomico(_path(rfc), data)
    return True

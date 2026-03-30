"""
Capa de datos para el catálogo de empresas y tracking de solicitudes.

Almacena en ~/.sat-descarga/:
  empresas.json              — catálogo de FIELs registradas
  solicitudes/{RFC}.json     — historial de solicitudes por empresa

Este módulo NO tiene I/O de terminal; es reutilizable por CLI y GUI.
"""

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from sat_descarga.fiel import FIEL

CONFIG_DIR = Path.home() / ".sat-descarga"
EFIRMA_DIR = Path("efirma")


def get_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------

def _empresas_path() -> Path:
    return get_config_dir() / "empresas.json"


def load_empresas() -> dict:
    path = _empresas_path()
    if not path.exists():
        return {"empresas": {}, "default_rfc": None}
    return json.loads(path.read_text())


def save_empresas(data: dict):
    _empresas_path().write_text(json.dumps(data, indent=2, ensure_ascii=False))


def _efirma_dir(rfc: str) -> Path:
    """Retorna ./efirma/{RFC}/, creándola si no existe."""
    d = EFIRMA_DIR / rfc
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_empresa(nombre: str, cer_path: str, key_path: str, password: str) -> str:
    """
    Registra una empresa. Valida la FIEL, copia archivos a ./efirma/{RFC}/
    con nombres estándar (fiel.cer, fiel.key, fiel.txt) y guarda en catálogo.
    Retorna el RFC.
    """
    cer_src = Path(cer_path).expanduser().resolve()
    key_src = Path(key_path).expanduser().resolve()

    # Validar FIEL y extraer RFC
    fiel = FIEL(str(cer_src), str(key_src), password)
    rfc = fiel.rfc

    # Copiar a ./efirma/{RFC}/fiel.*
    dest = _efirma_dir(rfc)
    cer_dest = dest / "fiel.cer"
    key_dest = dest / "fiel.key"
    pwd_dest = dest / "fiel.txt"

    if cer_src.resolve() != cer_dest.resolve():
        shutil.copy2(cer_src, cer_dest)
    if key_src.resolve() != key_dest.resolve():
        shutil.copy2(key_src, key_dest)
    pwd_dest.write_text(password)

    data = load_empresas()
    data["empresas"][rfc] = {
        "nombre": nombre,
        "cer_path": str(cer_dest),
        "key_path": str(key_dest),
        "password": password,
        "vencimiento": fiel.not_valid_after.strftime("%Y-%m-%d"),
    }
    if data["default_rfc"] is None:
        data["default_rfc"] = rfc
    save_empresas(data)
    return rfc


def remove_empresa(rfc: str):
    data = load_empresas()
    data["empresas"].pop(rfc, None)
    if data["default_rfc"] == rfc:
        rfcs = list(data["empresas"].keys())
        data["default_rfc"] = rfcs[0] if rfcs else None
    save_empresas(data)


def list_empresas() -> list[dict]:
    data = load_empresas()
    default = data.get("default_rfc")
    result = []
    for rfc, info in data["empresas"].items():
        result.append({
            "rfc": rfc,
            "nombre": info["nombre"],
            "cer_path": info["cer_path"],
            "vencimiento": info.get("vencimiento", ""),
            "default": rfc == default,
        })
    return result


def get_empresa(rfc: str) -> dict:
    data = load_empresas()
    empresa = data["empresas"].get(rfc)
    if empresa is None:
        raise KeyError(f"No se encontró empresa con RFC {rfc}")
    return {"rfc": rfc, **empresa}


def get_default() -> Optional[str]:
    return load_empresas().get("default_rfc")


def set_default(rfc: str):
    data = load_empresas()
    if rfc not in data["empresas"]:
        raise KeyError(f"No se encontró empresa con RFC {rfc}")
    data["default_rfc"] = rfc
    save_empresas(data)


# ---------------------------------------------------------------------------
# Solicitudes
# ---------------------------------------------------------------------------

def _solicitudes_dir() -> Path:
    d = get_config_dir() / "solicitudes"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _solicitudes_path(rfc: str) -> Path:
    return _solicitudes_dir() / f"{rfc}.json"


def _load_solicitudes(rfc: str) -> dict:
    path = _solicitudes_path(rfc)
    if not path.exists():
        return {"solicitudes": []}
    return json.loads(path.read_text())


def _save_solicitudes(rfc: str, data: dict):
    _solicitudes_path(rfc).write_text(json.dumps(data, indent=2, ensure_ascii=False))


def save_solicitud(
    rfc: str,
    id_solicitud: str,
    fecha_inicio: str,
    fecha_fin: str,
    tipo: str,
    estado: str = "solicitada",
):
    data = _load_solicitudes(rfc)
    data["solicitudes"].append({
        "id_solicitud": id_solicitud,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "tipo": tipo,
        "estado": estado,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    })
    _save_solicitudes(rfc, data)


def update_solicitud(rfc: str, id_solicitud: str, estado: str, package_ids: Optional[list] = None):
    data = _load_solicitudes(rfc)
    for sol in data["solicitudes"]:
        if sol["id_solicitud"] == id_solicitud:
            sol["estado"] = estado
            if package_ids is not None:
                sol["package_ids"] = package_ids
            break
    _save_solicitudes(rfc, data)


def get_solicitudes_pendientes(rfc: str) -> list[dict]:
    data = _load_solicitudes(rfc)
    return [s for s in data["solicitudes"] if s["estado"] not in ("terminada", "error")]


def get_solicitud(rfc: str, id_solicitud: str) -> Optional[dict]:
    data = _load_solicitudes(rfc)
    for s in data["solicitudes"]:
        if s["id_solicitud"] == id_solicitud:
            return s
    return None

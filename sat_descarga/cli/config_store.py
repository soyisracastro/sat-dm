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

from sat_descarga.core.fiel import FIEL
from sat_descarga.core import secretos

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
    Registra una empresa por e.firma (FIEL). Valida la FIEL, copia .cer/.key a
    ./efirma/{RFC}/ y guarda la contraseña en el keychain del SO (NUNCA en texto
    plano en disco). Retorna el RFC.
    """
    cer_src = Path(cer_path).expanduser().resolve()
    key_src = Path(key_path).expanduser().resolve()

    # Validar FIEL y extraer RFC
    fiel = FIEL(str(cer_src), str(key_src), password)
    rfc = fiel.rfc

    # Copiar a ./efirma/{RFC}/fiel.{cer,key} (la contraseña va al keychain).
    dest = _efirma_dir(rfc)
    cer_dest = dest / "fiel.cer"
    key_dest = dest / "fiel.key"

    if cer_src.resolve() != cer_dest.resolve():
        shutil.copy2(cer_src, cer_dest)
    if key_src.resolve() != key_dest.resolve():
        shutil.copy2(key_src, key_dest)
    secretos.guardar(rfc, secretos.FIEL, password)

    data = load_empresas()
    existente = data["empresas"].get(rfc, {})
    data["empresas"][rfc] = {
        **existente,
        "nombre": nombre,
        "metodo": "fiel",
        "cer_path": str(cer_dest),
        "key_path": str(key_dest),
        "vencimiento": fiel.not_valid_after.strftime("%Y-%m-%d"),
    }
    if data["default_rfc"] is None:
        data["default_rfc"] = rfc
    save_empresas(data)
    return rfc


def add_empresa_ciec(rfc: str, nombre: str, ciec: str) -> str:
    """
    Registra (o actualiza) una empresa por CIEC. Guarda la contraseña CIEC en el
    keychain del SO; en el catálogo solo queda RFC + nombre + método. Retorna el RFC.
    """
    rfc = rfc.strip().upper()
    secretos.guardar(rfc, secretos.CIEC, ciec)

    data = load_empresas()
    existente = data["empresas"].get(rfc, {})
    data["empresas"][rfc] = {
        **existente,
        "nombre": nombre,
        "metodo": "ciec",
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
    # Borrar credenciales del keychain (ambos métodos; no falla si no existen).
    secretos.borrar(rfc, secretos.FIEL)
    secretos.borrar(rfc, secretos.CIEC)


def list_empresas() -> list[dict]:
    data = load_empresas()
    default = data.get("default_rfc")
    result = []
    for rfc, info in data["empresas"].items():
        result.append({
            "rfc": rfc,
            "nombre": info["nombre"],
            "metodo": info.get("metodo", "fiel"),
            "cer_path": info.get("cer_path"),
            "vencimiento": info.get("vencimiento", ""),
            "default": rfc == default,
        })
    return result


def get_empresa(rfc: str) -> dict:
    """
    Devuelve los datos de la empresa MÁS sus credenciales recuperadas del keychain:
    `password` (FIEL) y/o `ciec` (CIEC), según estén guardadas. Compat: si quedó un
    `password` en texto plano de una versión vieja del catálogo, se respeta.
    """
    data = load_empresas()
    empresa = data["empresas"].get(rfc)
    if empresa is None:
        raise KeyError(f"No se encontró empresa con RFC {rfc}")
    info = {"rfc": rfc, **empresa}
    info.setdefault("metodo", "fiel")

    password = empresa.get("password") or secretos.obtener(rfc, secretos.FIEL)
    if password:
        info["password"] = password
    ciec = secretos.obtener(rfc, secretos.CIEC)
    if ciec:
        info["ciec"] = ciec
    return info


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


def list_solicitudes(rfc: str) -> list[dict]:
    """Todas las solicitudes de la empresa, más recientes primero (para Historial)."""
    data = _load_solicitudes(rfc)
    return list(reversed(data["solicitudes"]))


def get_solicitud(rfc: str, id_solicitud: str) -> Optional[dict]:
    data = _load_solicitudes(rfc)
    for s in data["solicitudes"]:
        if s["id_solicitud"] == id_solicitud:
            return s
    return None

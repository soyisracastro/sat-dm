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


def _metodos(info: dict) -> list[str]:
    """
    Métodos de autenticación de una empresa, como lista (['ciec'], ['fiel'] o ambos).
    Compat: migra el viejo campo `metodo` (string) y, si solo hay .cer, infiere 'fiel'.
    """
    if info.get("metodos"):
        return list(info["metodos"])
    if info.get("metodo"):
        return [info["metodo"]]
    return ["fiel"] if info.get("cer_path") else []


def add_empresa(nombre: str, cer_path: str, key_path: str, password: str,
                rfc_esperado: Optional[str] = None) -> str:
    """
    Registra una empresa por e.firma (FIEL) — o le AGREGA el método e.firma si el RFC
    ya existía (p. ej. con CIEC), sin quitar el otro método. Valida la FIEL, copia
    .cer/.key a ./efirma/{RFC}/ y guarda la contraseña en el keychain. Retorna el RFC.

    Si se pasa `rfc_esperado` (al agregar e.firma a una empresa existente), se valida
    que el RFC del certificado coincida; si no, se rechaza (evita subir la e.firma de
    otro contribuyente).
    """
    cer_src = Path(cer_path).expanduser().resolve()
    key_src = Path(key_path).expanduser().resolve()

    fiel = FIEL(str(cer_src), str(key_src), password)
    rfc = fiel.rfc

    if rfc_esperado and rfc != rfc_esperado.strip().upper():
        raise ValueError(
            f"La e.firma corresponde al RFC {rfc}, no a {rfc_esperado.strip().upper()}. "
            "Sube la e.firma de este contribuyente."
        )

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
    entry = {
        **existente,
        "nombre": existente.get("nombre") or nombre,
        "metodos": sorted(set(_metodos(existente)) | {"fiel"}),
        "cer_path": str(cer_dest),
        "key_path": str(key_dest),
        "vencimiento": fiel.not_valid_after.strftime("%Y-%m-%d"),
    }
    entry.pop("metodo", None)  # quitar campo legacy
    data["empresas"][rfc] = entry
    if data["default_rfc"] is None:
        data["default_rfc"] = rfc
    save_empresas(data)
    return rfc


def add_empresa_ciec(rfc: str, nombre: str, ciec: str) -> str:
    """
    Registra una empresa por CIEC — o le AGREGA el método CIEC si el RFC ya existía
    (p. ej. con e.firma), sin quitar el otro. Guarda la contraseña CIEC en el keychain.
    """
    rfc = rfc.strip().upper()
    secretos.guardar(rfc, secretos.CIEC, ciec)

    data = load_empresas()
    existente = data["empresas"].get(rfc, {})
    entry = {
        **existente,
        "nombre": existente.get("nombre") or nombre,
        "metodos": sorted(set(_metodos(existente)) | {"ciec"}),
    }
    entry.pop("metodo", None)
    data["empresas"][rfc] = entry
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
            "metodos": _metodos(info),
            "cer_path": info.get("cer_path"),
            "vencimiento": info.get("vencimiento", ""),
            "default": rfc == default,
        })
    return result


def get_empresa(rfc: str) -> dict:
    """
    Devuelve los datos de la empresa MÁS sus credenciales del keychain: `password`
    (FIEL) y/o `ciec` (CIEC), según los métodos que tenga. `metodos` es una lista.
    Compat: respeta un `password` en texto plano de un catálogo viejo.
    """
    data = load_empresas()
    empresa = data["empresas"].get(rfc)
    if empresa is None:
        raise KeyError(f"No se encontró empresa con RFC {rfc}")
    info = {"rfc": rfc, **empresa}
    info["metodos"] = _metodos(empresa)
    info.pop("metodo", None)

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
    *,
    tipo_comprobante: Optional[str] = None,  # "E" (emitidos) / "R" (recibidos)
):
    """Guarda una solicitud WS. `tipo_comprobante` se conserva para luego ubicar la
    descarga en la carpeta correcta (`{RFC}/{emitidos|recibidos}/{rango}/`)."""
    data = _load_solicitudes(rfc)
    registro = {
        "id_solicitud": id_solicitud,
        "fecha_inicio": fecha_inicio,
        "fecha_fin": fecha_fin,
        "tipo": tipo,
        "estado": estado,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
    }
    if tipo_comprobante:
        registro["tipo_comprobante"] = tipo_comprobante.strip().upper()
    data["solicitudes"].append(registro)
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


# ---------------------------------------------------------------------------
# Historial de descargas (log unificado: WS + CIEC + documentos)
#
# A diferencia de `solicitudes/` (lifecycle de las solicitudes WS, para retomar),
# esto es un registro plano de descargas YA COMPLETADAS, por empresa, para que la
# pantalla Historial las muestre. Una línea por descarga terminada.
# ---------------------------------------------------------------------------

def _historial_dir() -> Path:
    d = get_config_dir() / "historial"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _historial_path(rfc: str) -> Path:
    return _historial_dir() / f"{rfc}.json"


def registrar_descarga(
    rfc: str,
    canal: str,                 # "ws" | "ciec" | "fiel"
    tipo: str,                  # "cfdi" | "metadata" | "constancia" | "opinion"
    descripcion: str = "",
    ruta: str = "",
    total: Optional[int] = None,  # nº de XML (CFDIs) cuando aplica
    estado: str = "completada",
) -> dict:
    """Registra una descarga completada en el historial de la empresa. Devuelve el registro."""
    rfc = rfc.strip().upper()
    path = _historial_path(rfc)
    data = json.loads(path.read_text()) if path.exists() else {"descargas": []}
    registro = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "canal": canal,
        "tipo": tipo,
        "descripcion": descripcion,
        "ruta": ruta,
        "total": total,
        "estado": estado,
    }
    data["descargas"].append(registro)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    return registro


def list_descargas(rfc: str) -> list[dict]:
    """Descargas de una empresa, más recientes primero."""
    path = _historial_path(rfc)
    if not path.exists():
        return []
    data = json.loads(path.read_text())
    return list(reversed(data.get("descargas", [])))


def list_todas_descargas() -> list[dict]:
    """Descargas de TODAS las empresas (con rfc + nombre), más recientes primero."""
    nombres = {e["rfc"]: e["nombre"] for e in list_empresas()}
    resultado: list[dict] = []
    for path in _historial_dir().glob("*.json"):
        rfc = path.stem
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        for d in data.get("descargas", []):
            resultado.append({**d, "rfc": rfc, "nombre": nombres.get(rfc, rfc)})
    resultado.sort(key=lambda d: d.get("timestamp", ""), reverse=True)
    return resultado


# ---------------------------------------------------------------------------
# Ajustes (settings.json) — p. ej. la carpeta base de descargas
# ---------------------------------------------------------------------------

def _settings_path() -> Path:
    return get_config_dir() / "settings.json"


def _load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _save_settings(data: dict):
    _settings_path().write_text(json.dumps(data, indent=2, ensure_ascii=False))


def descargas_dir_default() -> str:
    """Carpeta de descargas por defecto: la carpeta Documentos del usuario."""
    return str(Path.home() / "Documents" / "TodoConta")


def get_descargas_dir() -> str:
    """Carpeta base donde se guardan las descargas (configurable)."""
    return _load_settings().get("descargas_dir") or descargas_dir_default()


def asegurar_descargas_dir() -> str:
    """Devuelve la carpeta de descargas, creándola si no existe."""
    d = get_descargas_dir()
    Path(d).mkdir(parents=True, exist_ok=True)
    return d


def set_descargas_dir(path: str) -> str:
    """Fija la carpeta base de descargas (y la crea). Retorna la ruta absoluta."""
    p = str(Path(path).expanduser())
    Path(p).mkdir(parents=True, exist_ok=True)
    data = _load_settings()
    data["descargas_dir"] = p
    _save_settings(data)
    return p

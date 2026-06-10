"""
Capa de datos para el catálogo de empresas y tracking de solicitudes.

Almacena en ~/.sat-descarga/:
  empresas.json              — catálogo de FIELs registradas
  solicitudes/{RFC}.json     — historial de solicitudes por empresa

Este módulo NO tiene I/O de terminal; es reutilizable por CLI y GUI.
"""

import json
import logging
import os
import shutil
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from sat_descarga.core.fiel import FIEL
from sat_descarga.core import secretos

logger = logging.getLogger(__name__)

# Lock para serializar lecturas/escrituras del catálogo de solicitudes. Sin esto,
# dos requests concurrentes (p. ej. el active flow + el auto-poll de no-terminales
# pegándole a /verificar al mismo tiempo) hacen read-modify-write entrelazado y
# corrompen el JSON.
_solicitudes_lock = threading.RLock()

# Mismo problema para empresas.json, historial/{RFC}.json y settings.json: el
# agente atiende requests concurrentes y los mutadores hacen read-modify-write.
_catalogo_lock = threading.RLock()

CONFIG_DIR = Path.home() / ".sat-descarga"
EFIRMA_DIR = Path("efirma")


def get_config_dir() -> Path:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    return CONFIG_DIR


def _write_json_atomico(path: Path, data: dict):
    """Escritura atómica: a `.tmp` y luego `os.replace` (rename atómico en POSIX),
    así un lector concurrente nunca ve un archivo a medias."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    os.replace(tmp, path)


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------

def _empresas_path() -> Path:
    return get_config_dir() / "empresas.json"


def load_empresas() -> dict:
    with _catalogo_lock:
        path = _empresas_path()
        if not path.exists():
            return {"empresas": {}, "default_rfc": None}
        return json.loads(path.read_text())


def save_empresas(data: dict):
    with _catalogo_lock:
        _write_json_atomico(_empresas_path(), data)


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

    `nombre` puede venir vacío: se resuelve con la razón social del certificado
    (CN del subject) y, en último caso, con el RFC.

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

    with _catalogo_lock:
        data = load_empresas()
        existente = data["empresas"].get(rfc, {})
        entry = {
            **existente,
            "nombre": existente.get("nombre") or nombre or fiel.legal_name or rfc,
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

    `nombre` puede venir vacío: queda el RFC como nombre y se completa después
    (p. ej. al parsear la Constancia de Situación Fiscal).
    """
    rfc = rfc.strip().upper()
    secretos.guardar(rfc, secretos.CIEC, ciec)

    with _catalogo_lock:
        data = load_empresas()
        existente = data["empresas"].get(rfc, {})
        entry = {
            **existente,
            "nombre": existente.get("nombre") or nombre or rfc,
            "metodos": sorted(set(_metodos(existente)) | {"ciec"}),
        }
        entry.pop("metodo", None)
        data["empresas"][rfc] = entry
        if data["default_rfc"] is None:
            data["default_rfc"] = rfc
        save_empresas(data)
    return rfc


def remove_empresa(rfc: str):
    with _catalogo_lock:
        data = load_empresas()
        data["empresas"].pop(rfc, None)
        if data["default_rfc"] == rfc:
            rfcs = list(data["empresas"].keys())
            data["default_rfc"] = rfcs[0] if rfcs else None
        save_empresas(data)
    # Borrar credenciales del keychain (ambos métodos; no falla si no existen).
    secretos.borrar(rfc, secretos.FIEL)
    secretos.borrar(rfc, secretos.CIEC)


def remove_efirma(rfc: str):
    """
    Quita SOLO el método e.firma de una empresa (la CIEC no se toca): borra
    .cer/.key de ./efirma/{RFC}/, la contraseña del keychain y los campos del
    catálogo. Caso de uso: la e.firma venció y el contribuyente no puede
    renovarla aún — la empresa queda operando solo con CIEC.
    Lanza KeyError si el RFC no existe.
    """
    with _catalogo_lock:
        data = load_empresas()
        if rfc not in data["empresas"]:
            raise KeyError(f"No se encontró empresa con RFC {rfc}")
        info = data["empresas"][rfc]
        info["metodos"] = [m for m in _metodos(info) if m != "fiel"]
        for campo in ("cer_path", "key_path", "vencimiento"):
            info.pop(campo, None)
        info.pop("metodo", None)  # campo legacy
        save_empresas(data)
    secretos.borrar(rfc, secretos.FIEL)
    shutil.rmtree(EFIRMA_DIR / rfc, ignore_errors=True)


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
            "archived_at": info.get("archived_at"),
            "csf_path": info.get("csf_path"),
            "csf_descargada_en": info.get("csf_descargada_en"),
            "opinion_path": info.get("opinion_path"),
            "opinion_descargada_en": info.get("opinion_descargada_en"),
            "regimenes_fiscales": info.get("regimenes_fiscales", []),
            "actividades_economicas": info.get("actividades_economicas", []),
        })
    return result


# Campos editables por update_empresa(). Cualquier otra key del patch se ignora.
_EDITABLE_FIELDS = {"regimenes_fiscales", "actividades_economicas"}


def update_empresa(rfc: str, patch: dict):
    """
    Aplica un patch parcial a la empresa. Solo acepta keys en `_EDITABLE_FIELDS`;
    el resto se ignora silenciosamente (defensa básica).
    Valida shapes:
      - regimenes_fiscales:    list[{clave: str, descripcion: str}]
      - actividades_economicas: list[{descripcion: str, principal?: bool}]
    Lanza ValueError si el shape es inválido y KeyError si el RFC no existe.
    """
    with _catalogo_lock:
        data = load_empresas()
        if rfc not in data["empresas"]:
            raise KeyError(f"No se encontró empresa con RFC {rfc}")

        for key, value in patch.items():
            if key not in _EDITABLE_FIELDS:
                continue
            if not isinstance(value, list):
                raise ValueError(f"{key} debe ser una lista")
            if key == "regimenes_fiscales":
                for item in value:
                    if not isinstance(item, dict) \
                            or not isinstance(item.get("clave"), str) \
                            or not isinstance(item.get("descripcion"), str):
                        raise ValueError("régimen inválido: requiere clave y descripcion (str)")
                data["empresas"][rfc][key] = [
                    {"clave": i["clave"], "descripcion": i["descripcion"]} for i in value
                ]
            elif key == "actividades_economicas":
                for item in value:
                    if not isinstance(item, dict) \
                            or not isinstance(item.get("descripcion"), str):
                        raise ValueError("actividad inválida: requiere descripcion (str)")
                    if "principal" in item and not isinstance(item["principal"], bool):
                        raise ValueError("actividad.principal debe ser bool")
                data["empresas"][rfc][key] = [
                    {k: v for k, v in i.items() if k in ("descripcion", "principal")}
                    for i in value
                ]
        save_empresas(data)


def archive_empresa(rfc: str):
    """
    Soft-delete: marca la empresa como archivada (no la borra). Si era la default,
    promueve la primera empresa activa restante (o None si no quedan activas).
    """
    with _catalogo_lock:
        data = load_empresas()
        if rfc not in data["empresas"]:
            raise KeyError(f"No se encontró empresa con RFC {rfc}")
        data["empresas"][rfc]["archived_at"] = datetime.now().isoformat(timespec="seconds")
        if data.get("default_rfc") == rfc:
            candidatos = [
                r for r, info in data["empresas"].items()
                if r != rfc and not info.get("archived_at")
            ]
            data["default_rfc"] = candidatos[0] if candidatos else None
        save_empresas(data)


def unarchive_empresa(rfc: str):
    """Reactiva una empresa archivada."""
    with _catalogo_lock:
        data = load_empresas()
        if rfc not in data["empresas"]:
            raise KeyError(f"No se encontró empresa con RFC {rfc}")
        data["empresas"][rfc]["archived_at"] = None
        save_empresas(data)


def set_csf_descargada(rfc: str, path: str):
    """Best-effort: persiste path + timestamp de la última CSF descargada."""
    with _catalogo_lock:
        data = load_empresas()
        if rfc not in data["empresas"]:
            return
        data["empresas"][rfc]["csf_path"] = path
        data["empresas"][rfc]["csf_descargada_en"] = datetime.now().isoformat(timespec="seconds")
        save_empresas(data)


def set_opinion_descargada(rfc: str, path: str):
    """Best-effort: persiste path + timestamp de la última opinión 32-D descargada."""
    with _catalogo_lock:
        data = load_empresas()
        if rfc not in data["empresas"]:
            return
        data["empresas"][rfc]["opinion_path"] = path
        data["empresas"][rfc]["opinion_descargada_en"] = datetime.now().isoformat(timespec="seconds")
        save_empresas(data)


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
    with _catalogo_lock:
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
    """Lee el catálogo de solicitudes de la empresa. Si el JSON quedó corrupto
    (p. ej. write race anterior, antes de que esto fuera atómico), recupera el
    primer objeto válido con raw_decode y reescribe el archivo limpio."""
    path = _solicitudes_path(rfc)
    if not path.exists():
        return {"solicitudes": []}
    raw = path.read_text()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning(
            "[config_store] solicitudes/%s.json corrupto; recuperando primer objeto…",
            rfc,
        )
        try:
            obj, _end = json.JSONDecoder().raw_decode(raw)
        except json.JSONDecodeError:
            logger.error(
                "[config_store] No se pudo recuperar; reseteando catálogo de %s", rfc,
            )
            obj = {"solicitudes": []}
        if not isinstance(obj, dict) or "solicitudes" not in obj:
            obj = {"solicitudes": obj if isinstance(obj, list) else []}
        _save_solicitudes(rfc, obj)
        return obj


def _save_solicitudes(rfc: str, data: dict):
    _write_json_atomico(_solicitudes_path(rfc), data)


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
    with _solicitudes_lock:
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


def update_solicitud(
    rfc: str,
    id_solicitud: str,
    estado: str,
    package_ids: Optional[list] = None,
    *,
    mensaje: Optional[str] = None,
    numero_cfdis: Optional[int] = None,
):
    """Actualiza el estado y, opcionalmente, los campos auxiliares que devuelve el
    SAT en /verificar (mensaje, numero_cfdis). Estos últimos alimentan los detalles
    de la fila expandida en la UI."""
    with _solicitudes_lock:
        data = _load_solicitudes(rfc)
        for sol in data["solicitudes"]:
            if sol["id_solicitud"] == id_solicitud:
                sol["estado"] = estado
                if package_ids is not None:
                    sol["package_ids"] = package_ids
                if mensaje is not None:
                    sol["mensaje"] = mensaje
                if numero_cfdis is not None:
                    sol["numero_cfdis"] = numero_cfdis
                break
        _save_solicitudes(rfc, data)


def delete_solicitud(rfc: str, id_solicitud: str) -> bool:
    """Borra una solicitud del catálogo de la empresa. Devuelve True si se borró,
    False si no se encontró."""
    with _solicitudes_lock:
        data = _load_solicitudes(rfc)
        n = len(data["solicitudes"])
        data["solicitudes"] = [s for s in data["solicitudes"] if s.get("id_solicitud") != id_solicitud]
        if len(data["solicitudes"]) == n:
            return False
        _save_solicitudes(rfc, data)
        return True


def get_solicitudes_pendientes(rfc: str) -> list[dict]:
    with _solicitudes_lock:
        data = _load_solicitudes(rfc)
    return [s for s in data["solicitudes"] if s["estado"] not in ("terminada", "error")]


def list_solicitudes(rfc: str) -> list[dict]:
    """Todas las solicitudes de la empresa, más recientes primero (para Historial)."""
    with _solicitudes_lock:
        data = _load_solicitudes(rfc)
    return list(reversed(data["solicitudes"]))


def get_solicitud(rfc: str, id_solicitud: str) -> Optional[dict]:
    with _solicitudes_lock:
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
    registro = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "canal": canal,
        "tipo": tipo,
        "descripcion": descripcion,
        "ruta": ruta,
        "total": total,
        "estado": estado,
    }
    with _catalogo_lock:
        data = json.loads(path.read_text()) if path.exists() else {"descargas": []}
        data["descargas"].append(registro)
        _write_json_atomico(path, data)
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
    with _catalogo_lock:
        _write_json_atomico(_settings_path(), data)


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
    with _catalogo_lock:
        data = _load_settings()
        data["descargas_dir"] = p
        _save_settings(data)
    return p

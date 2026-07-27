"""GitHub REST mínimo para el agente de contenido: rama + archivos + PR.

Solo necesita un fine-grained PAT con permiso "Contents: write" y
"Pull requests: write" sobre el repo destino (env GITHUB_PAT).
"""

from __future__ import annotations

import base64
import os

import requests

API = "https://api.github.com"
TIMEOUT = 20


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['GITHUB_PAT']}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def leer_archivo(repo: str, ruta: str, ref: str = "main") -> str | None:
    """Contenido de un archivo del repo (o None si no existe / sin PAT)."""
    if not os.environ.get("GITHUB_PAT"):
        return None
    try:
        resp = requests.get(
            f"{API}/repos/{repo}/contents/{ruta}",
            headers={**_headers(), "Accept": "application/vnd.github.raw+json"},
            params={"ref": ref},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return None
        return resp.text
    except requests.RequestException as e:
        print(f"[github] no pude leer {ruta}: {e}")
        return None


def listar_directorio(repo: str, ruta: str, ref: str = "main") -> list[str]:
    """Nombres de archivo de un directorio del repo (o [] si no existe / sin PAT).

    Lo usa el agente de contenido para conocer los posts ya publicados: sirve
    para interlinkear con slugs REALES y para no repetir un tema ya cubierto.
    """
    if not os.environ.get("GITHUB_PAT"):
        return []
    try:
        resp = requests.get(
            f"{API}/repos/{repo}/contents/{ruta}",
            headers=_headers(),
            params={"ref": ref},
            timeout=TIMEOUT,
        )
        if resp.status_code != 200:
            return []
        return [e["name"] for e in resp.json() if e.get("type") == "file"]
    except (requests.RequestException, ValueError, KeyError, TypeError) as e:
        print(f"[github] no pude listar {ruta}: {e}")
        return []


def crear_pr_con_archivos(
    repo: str,
    rama: str,
    titulo: str,
    cuerpo: str,
    archivos: dict[str, str | bytes],
    base: str = "main",
) -> str:
    """Crea `rama` desde `base`, sube `archivos` {ruta: contenido} y abre el PR.

    El contenido puede ser str (texto) o bytes (binarios, p. ej. imágenes).

    Idempotente a nivel corrida: si la rama o el PR ya existen, los reutiliza.
    Devuelve la URL del PR.
    """
    # SHA de la punta de base → crear la rama (422 = ya existe, seguimos).
    resp = requests.get(
        f"{API}/repos/{repo}/git/ref/heads/{base}", headers=_headers(), timeout=TIMEOUT
    )
    resp.raise_for_status()
    sha_base = resp.json()["object"]["sha"]

    resp = requests.post(
        f"{API}/repos/{repo}/git/refs",
        headers=_headers(),
        json={"ref": f"refs/heads/{rama}", "sha": sha_base},
        timeout=TIMEOUT,
    )
    if resp.status_code not in (201, 422):
        resp.raise_for_status()

    # Subir cada archivo (PUT contents crea el commit en la rama).
    for ruta, contenido in archivos.items():
        crudo = contenido.encode("utf-8") if isinstance(contenido, str) else contenido
        payload: dict = {
            "message": f"drafts: {ruta}",
            "content": base64.b64encode(crudo).decode("ascii"),
            "branch": rama,
        }
        # Si el archivo ya existe en la rama (re-corrida), hay que mandar su sha.
        existente = requests.get(
            f"{API}/repos/{repo}/contents/{ruta}",
            headers=_headers(),
            params={"ref": rama},
            timeout=TIMEOUT,
        )
        if existente.status_code == 200:
            payload["sha"] = existente.json()["sha"]
        resp = requests.put(
            f"{API}/repos/{repo}/contents/{ruta}",
            headers=_headers(),
            json=payload,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()

    # Abrir el PR (422 = ya hay PR de esta rama → lo buscamos y devolvemos).
    resp = requests.post(
        f"{API}/repos/{repo}/pulls",
        headers=_headers(),
        json={"title": titulo, "body": cuerpo, "head": rama, "base": base},
        timeout=TIMEOUT,
    )
    if resp.status_code == 201:
        return resp.json()["html_url"]
    if resp.status_code == 422:
        duenio = repo.split("/")[0]
        abiertos = requests.get(
            f"{API}/repos/{repo}/pulls",
            headers=_headers(),
            params={"head": f"{duenio}:{rama}", "state": "open"},
            timeout=TIMEOUT,
        )
        abiertos.raise_for_status()
        datos = abiertos.json()
        if datos:
            return datos[0]["html_url"]
    resp.raise_for_status()
    return ""  # inalcanzable; para el type checker

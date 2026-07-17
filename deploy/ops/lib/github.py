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


def crear_pr_con_archivos(
    repo: str,
    rama: str,
    titulo: str,
    cuerpo: str,
    archivos: dict[str, str],
    base: str = "main",
) -> str:
    """Crea `rama` desde `base`, sube `archivos` {ruta: contenido} y abre el PR.

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
        payload: dict = {
            "message": f"drafts: {ruta}",
            "content": base64.b64encode(contenido.encode("utf-8")).decode("ascii"),
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

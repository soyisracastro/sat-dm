"""Notion REST mínimo para los agentes de ops. Igual que lib/github.py:
requests directo, sin SDK.

- LEE la waitlist de Abacus (`consultar_bd` / `propiedad`), que llena el
  formulario de la landing.
- ESCRIBE los posts sociales de la semana (`crear_pagina`), que antes viajaban
  como un .md dentro del PR de drafts y eran incómodos de encontrar.
"""

from __future__ import annotations

import os
from typing import Any

import requests

API = "https://api.notion.com/v1"
VERSION = "2022-06-28"
TIMEOUT = 20


def _headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['NOTION_API_KEY']}",
        "Notion-Version": VERSION,
        "Content-Type": "application/json",
    }


def consultar_bd(db_id: str, filtro: dict | None = None) -> list[dict]:
    """Todas las páginas de la base (paginado incluido)."""
    paginas: list[dict] = []
    cursor: str | None = None
    while True:
        payload: dict[str, Any] = {"page_size": 100}
        if filtro:
            payload["filter"] = filtro
        if cursor:
            payload["start_cursor"] = cursor
        resp = requests.post(
            f"{API}/databases/{db_id}/query",
            headers=_headers(),
            json=payload,
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        datos = resp.json()
        paginas.extend(datos.get("results", []))
        if not datos.get("has_more"):
            return paginas
        cursor = datos.get("next_cursor")


LIMITE_RICH_TEXT = 2000  # tope de Notion por bloque de texto


def _bloques(texto: str) -> list[dict]:
    """Texto plano → bloques `paragraph`, respetando el tope de 2,000 chars."""
    bloques: list[dict] = []
    for parrafo in texto.split("\n"):
        parrafo = parrafo.rstrip()
        trozos = [
            parrafo[i : i + LIMITE_RICH_TEXT]
            for i in range(0, len(parrafo), LIMITE_RICH_TEXT)
        ] or [""]
        for trozo in trozos:
            bloques.append(
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": (
                            [{"type": "text", "text": {"content": trozo}}]
                            if trozo
                            else []
                        )
                    },
                }
            )
    return bloques[:100]  # Notion acepta máx 100 bloques por creación


def crear_pagina(db_id: str, propiedades: dict, cuerpo: str = "") -> str | None:
    """Crea una página en la base y devuelve su URL (None si falla).

    `propiedades` va en el formato nativo de Notion. `cuerpo` es texto plano
    que se convierte en párrafos — es donde vive el copy completo del post.
    """
    try:
        resp = requests.post(
            f"{API}/pages",
            headers=_headers(),
            json={
                "parent": {"database_id": db_id},
                "properties": propiedades,
                "children": _bloques(cuerpo) if cuerpo else [],
            },
            timeout=TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json().get("url")
    except requests.RequestException as e:
        detalle = getattr(e.response, "text", "")[:300] if e.response is not None else e
        print(f"[notion] no pude crear la página: {detalle}")
        return None


def texto(valor: str) -> dict:
    """Helper: valor para una propiedad rich_text."""
    return {"rich_text": [{"type": "text", "text": {"content": valor[:LIMITE_RICH_TEXT]}}]}


def titulo(valor: str) -> dict:
    """Helper: valor para la propiedad title."""
    return {"title": [{"type": "text", "text": {"content": valor[:LIMITE_RICH_TEXT]}}]}


def propiedad(pagina: dict, nombre: str) -> str:
    """Valor de una propiedad como texto plano ("" si está vacía).

    Cubre los tipos que usa la waitlist: title, rich_text, email,
    phone_number, select, date y formula/rollup simples.
    """
    prop = (pagina.get("properties") or {}).get(nombre)
    if not prop:
        return ""
    tipo = prop.get("type")

    if tipo in ("title", "rich_text"):
        return "".join(t.get("plain_text", "") for t in prop.get(tipo) or []).strip()
    if tipo in ("email", "phone_number", "url"):
        return (prop.get(tipo) or "").strip()
    if tipo == "select":
        return ((prop.get("select") or {}).get("name") or "").strip()
    if tipo == "date":
        return ((prop.get("date") or {}).get("start") or "").strip()
    if tipo == "number":
        valor = prop.get("number")
        return "" if valor is None else str(valor)
    if tipo == "checkbox":
        return "sí" if prop.get("checkbox") else ""
    if tipo == "formula":
        f = prop.get("formula") or {}
        return str(f.get(f.get("type"), "") or "").strip()
    return ""

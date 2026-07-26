"""Notion REST mínimo (solo lo que necesita el sync de la waitlist de Abacus).

La waitlist vive en una base de Notion que llena el formulario de la landing;
este módulo solo LEE. Igual que lib/github.py: requests directo, sin SDK.
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

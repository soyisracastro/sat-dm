"""REST mínimo de Supabase (service role) para leer/escribir el CRM (034).

Regla del contenedor: los agentes SOLO escriben en tablas crm_* — nada más.
"""

from __future__ import annotations

import os
from typing import Any

import requests

TIMEOUT = 15


def _base_headers() -> tuple[str, dict[str, str]]:
    base = os.environ["TODOCONTA_SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_KEY"]
    return base, {"apikey": key, "Authorization": f"Bearer {key}"}


def sb_get(path: str) -> list[dict[str, Any]]:
    """GET rest/v1/{path} → lista de filas."""
    base, headers = _base_headers()
    resp = requests.get(f"{base}/rest/v1/{path}", headers=headers, timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def sb_patch(path: str, datos: dict[str, Any]) -> None:
    base, headers = _base_headers()
    resp = requests.patch(
        f"{base}/rest/v1/{path}",
        headers={**headers, "Prefer": "return=minimal"},
        json=datos,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()


def sb_post(path: str, datos: dict[str, Any]) -> None:
    base, headers = _base_headers()
    resp = requests.post(
        f"{base}/rest/v1/{path}",
        headers={**headers, "Prefer": "return=minimal"},
        json=datos,
        timeout=TIMEOUT,
    )
    resp.raise_for_status()

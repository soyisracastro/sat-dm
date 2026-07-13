#!/usr/bin/env python3
"""
Emite una API key de TodoConta (v1: manual, corre donde haya el service key).

    python3 emitir-key.py --email usuario@x.mx --nombre "Sistema de Facturación" \
        [--scopes documentos:leer,cfdi:solicitar,listas-negras:consultar,mcp]

Imprime la key COMPLETA una sola vez (solo el hash queda en Supabase).
Env requeridas: TODOCONTA_SUPABASE_URL, SUPABASE_SERVICE_KEY.
"""

import argparse
import hashlib
import os
import secrets
import sys

import requests

SCOPES_DEFAULT = "documentos:leer,cfdi:solicitar,listas-negras:consultar,mcp"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--email", required=True)
    ap.add_argument("--nombre", required=True)
    ap.add_argument("--scopes", default=SCOPES_DEFAULT)
    args = ap.parse_args()

    url = os.environ["TODOCONTA_SUPABASE_URL"].rstrip("/")
    svc = os.environ["SUPABASE_SERVICE_KEY"]
    h = {"apikey": svc, "Authorization": f"Bearer {svc}"}

    # user_id por email (GoTrue admin).
    r = requests.get(f"{url}/auth/v1/admin/users", params={"page": 1, "per_page": 1000}, headers=h, timeout=30)
    r.raise_for_status()
    user = next((u for u in r.json().get("users", []) if u.get("email") == args.email), None)
    if not user:
        print(f"No existe usuario con email {args.email}", file=sys.stderr)
        return 1

    key = f"tc_live_{secrets.token_urlsafe(32)}"
    fila = {
        "user_id": user["id"],
        "nombre": args.nombre,
        "key_hash": hashlib.sha256(key.encode()).hexdigest(),
        "prefijo": key[:16],
        "scopes": [s.strip() for s in args.scopes.split(",") if s.strip()],
    }
    r = requests.post(f"{url}/rest/v1/api_keys", json=fila, headers={**h, "Prefer": "return=minimal"}, timeout=30)
    if r.status_code not in (200, 201):
        print(f"Error al insertar: {r.status_code} {r.text}", file=sys.stderr)
        return 1

    print("API key emitida (guárdala AHORA; no se puede recuperar):\n")
    print(f"  {key}\n")
    print(f"  usuario: {args.email} · scopes: {fila['scopes']} · prefijo: {fila['prefijo']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

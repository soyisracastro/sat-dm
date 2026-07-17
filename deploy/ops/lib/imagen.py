"""heroImage del post semanal: generación (Gemini) + compresión (TinyPNG).

Best-effort de punta a punta: sin GEMINI_API_KEY/TINYPNG_API_KEY o ante
cualquier fallo devuelven None y el paquete semanal sale SIN imagen — la
ficha-seo.md siempre trae el prompt para correrlo a mano.

Modelo por env GEMINI_IMAGE_MODEL; default gemini-3.1-flash-lite-image
(Nano Banana 2 Lite, el económico: ~$0.03 por imagen — decisión de Israel
2026-07-17: las heroImage no necesitan un modelo grande).
"""

from __future__ import annotations

import base64
import os

import requests

MODELO_DEFAULT = "gemini-3.1-flash-lite-image"


def generar_hero(prompt: str) -> bytes | None:
    """PNG 16:9 desde el prompt Estilo 06, vía el endpoint interactions."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        return None
    try:
        resp = requests.post(
            "https://generativelanguage.googleapis.com/v1beta/interactions",
            headers={"x-goog-api-key": key, "Content-Type": "application/json"},
            json={
                "model": os.environ.get("GEMINI_IMAGE_MODEL", MODELO_DEFAULT),
                "input": prompt,
                "response_format": {"type": "image", "aspect_ratio": "16:9"},
            },
            timeout=180,
        )
        resp.raise_for_status()
        for step in resp.json().get("steps", []):
            if step.get("type") != "model_output":
                continue
            for bloque in step.get("content", []):
                if bloque.get("type") == "image" and bloque.get("data"):
                    return base64.b64decode(bloque["data"])
        print("[imagen] la respuesta de Gemini no trae bloque de imagen")
        return None
    except Exception as e:  # noqa: BLE001
        print(f"[imagen] Gemini falló: {e}")
        return None


def comprimir_jpg(png: bytes) -> bytes | None:
    """TinyPNG: shrink + conversión a JPEG con fondo #FAFAF7 (paleta Estilo 06)."""
    key = os.environ.get("TINYPNG_API_KEY")
    if not key:
        print("[imagen] sin TINYPNG_API_KEY — no comprimo")
        return None
    try:
        resp = requests.post(
            "https://api.tinify.com/shrink", auth=("api", key), data=png, timeout=90
        )
        resp.raise_for_status()
        url = resp.headers.get("Location") or resp.json()["output"]["url"]
        resp = requests.post(
            url,
            auth=("api", key),
            json={
                "convert": {"type": "image/jpeg"},
                "transform": {"background": "#FAFAF7"},
            },
            timeout=90,
        )
        resp.raise_for_status()
        return resp.content
    except Exception as e:  # noqa: BLE001
        print(f"[imagen] TinyPNG falló: {e}")
        return None

"""Generación con Claude (opcional — sin ANTHROPIC_API_KEY cada agente se
degrada solo: el reporte sale con puros números, el SDR usa su plantilla fija,
soporte notifica sin borrador)."""

from __future__ import annotations

import json
import os


def generar(
    prompt: str,
    sistema: str | None = None,
    modelo: str | None = None,
    max_tokens: int = 1200,
) -> str | None:
    """Una llamada de texto a Claude. None si no hay key o si falla."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic

        cliente = anthropic.Anthropic()
        kwargs: dict = {
            "model": modelo or os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001"),
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if sistema:
            kwargs["system"] = sistema
        respuesta = cliente.messages.create(**kwargs)
        return "".join(b.text for b in respuesta.content if b.type == "text").strip()
    except Exception as e:  # noqa: BLE001
        print(f"[llm] generación no disponible: {e}")
        return None


def generar_json(
    prompt: str,
    sistema: str | None = None,
    modelo: str | None = None,
    max_tokens: int = 1200,
) -> dict | None:
    """Como generar(), pero espera un objeto JSON (tolera fences ```json)."""
    crudo = generar(prompt, sistema=sistema, modelo=modelo, max_tokens=max_tokens)
    if not crudo:
        return None
    limpio = crudo.strip()
    if limpio.startswith("```"):
        limpio = limpio.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        datos = json.loads(limpio)
        return datos if isinstance(datos, dict) else None
    except ValueError:
        print(f"[llm] respuesta no es JSON válido: {crudo[:120]}…")
        return None


def narrar(prompt: str) -> str | None:
    """Compat: narrativa breve con el modelo default (reporte semanal)."""
    return generar(prompt)

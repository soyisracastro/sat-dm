"""Narrativa con Claude (opcional — sin ANTHROPIC_API_KEY el reporte sale
solo con números)."""

from __future__ import annotations

import os


def narrar(prompt: str) -> str | None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return None
    try:
        import anthropic

        cliente = anthropic.Anthropic()
        respuesta = cliente.messages.create(
            model=os.environ.get("LLM_MODEL", "claude-haiku-4-5-20251001"),
            max_tokens=1200,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in respuesta.content if b.type == "text").strip()
    except Exception as e:  # noqa: BLE001
        print(f"[llm] narrativa no disponible: {e}")
        return None

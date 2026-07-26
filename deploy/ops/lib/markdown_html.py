"""Markdown → HTML con estilos EN LÍNEA, para el cuerpo de los correos.

La narrativa de los agentes la escribe Claude en markdown, pero los clientes de
correo no lo renderizan: el reporte semanal llegaba con "## Resumen Ejecutivo" y
"**negritas**" en crudo. Este módulo convierte el subconjunto que el modelo sí
usa —encabezados, énfasis, listas, párrafos, código, citas y reglas— a HTML.

Los estilos van en línea a propósito: Gmail descarta <style> del <head>.

No es un markdown completo (sin tablas ni imágenes) y NUNCA deja pasar HTML
crudo: todo se escapa antes de aplicar formato. Uso:

    from lib import markdown_html
    cuerpo = markdown_html.render(narrativa)
"""

from __future__ import annotations

import html
import re

E = {
    "h_grande": "font-size:17px;font-weight:700;letter-spacing:-0.01em;margin:18px 0 6px",
    "h_chico": "font-size:15px;font-weight:700;margin:14px 0 4px",
    "p": "margin:0 0 10px;line-height:1.55",
    "lista": "margin:0 0 10px;padding:0 0 0 20px;line-height:1.55",
    "li": "margin:0 0 5px",
    "cita": "margin:0 0 10px;padding:0 0 0 12px;border-left:3px solid #e6e4e0;color:#52514e",
    "code": (
        "font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;"
        "background:#f4f3f1;padding:1px 4px;border-radius:3px"
    ),
    "hr": "border:0;border-top:1px solid #e6e4e0;margin:16px 0",
    "a": "color:#0b57d0",
}

RE_ENCABEZADO = re.compile(r"^(#{1,6})\s+(.*)$")
RE_VINETA = re.compile(r"^\s*[-*+]\s+(.*)$")
RE_NUMERADA = re.compile(r"^\s*\d+[.)]\s+(.*)$")
RE_CITA = re.compile(r"^\s*>\s?(.*)$")
RE_REGLA = re.compile(r"^\s*(?:-{3,}|_{3,}|\*{3,})\s*$")
RE_CODIGO = re.compile(r"`([^`\n]+)`")
RE_ENLACE = re.compile(r"\[([^\]\n]+)\]\((https?://[^\s)]+|mailto:[^\s)]+)\)")
RE_NEGRITA = re.compile(r"(?:\*\*|__)(.+?)(?:\*\*|__)", re.DOTALL)
RE_CURSIVA = re.compile(r"(?<![\w*])\*([^*\n]+)\*(?![\w*])")


def _en_linea(texto: str) -> str:
    """Escapa y aplica formato de línea. El código va primero y se aparta con un
    marcador para que ni negritas ni enlaces lo toquen por dentro."""
    escapado = html.escape(texto, quote=False)

    apartados: list[str] = []

    def _aparta(m: re.Match[str]) -> str:
        apartados.append(f'<code style="{E["code"]}">{m.group(1)}</code>')
        return f"\x00{len(apartados) - 1}\x00"

    salida = RE_CODIGO.sub(_aparta, escapado)
    salida = RE_ENLACE.sub(
        lambda m: f'<a href="{m.group(2)}" style="{E["a"]}">{m.group(1)}</a>', salida
    )
    salida = RE_NEGRITA.sub(r"<strong>\1</strong>", salida)
    salida = RE_CURSIVA.sub(r"<em>\1</em>", salida)
    for i, fragmento in enumerate(apartados):
        salida = salida.replace(f"\x00{i}\x00", fragmento)
    return salida


def _lista(etiqueta: str, elementos: list[str]) -> str:
    puntos = "".join(
        f'<li style="{E["li"]}">{_en_linea(t)}</li>' for t in elementos
    )
    return f'<{etiqueta} style="{E["lista"]}">{puntos}</{etiqueta}>'


def render(markdown: str | None) -> str:
    """HTML listo para incrustar en el cuerpo del correo ("" si no hay texto)."""
    if not markdown or not markdown.strip():
        return ""

    bloques: list[str] = []
    parrafo: list[str] = []
    elementos: list[str] = []
    tipo_lista = ""  # "ul" | "ol" | ""
    cita: list[str] = []

    def cerrar() -> None:
        nonlocal parrafo, elementos, tipo_lista, cita
        if parrafo:
            bloques.append(f'<p style="{E["p"]}">{_en_linea(" ".join(parrafo))}</p>')
            parrafo = []
        if elementos:
            bloques.append(_lista(tipo_lista or "ul", elementos))
            elementos, tipo_lista = [], ""
        if cita:
            bloques.append(
                f'<blockquote style="{E["cita"]}">{_en_linea(" ".join(cita))}</blockquote>'
            )
            cita = []

    for linea in markdown.replace("\r\n", "\n").split("\n"):
        if not linea.strip():
            cerrar()
            continue

        if RE_REGLA.match(linea):
            cerrar()
            bloques.append(f'<hr style="{E["hr"]}">')
            continue

        m = RE_ENCABEZADO.match(linea)
        if m:
            cerrar()
            estilo = E["h_grande"] if len(m.group(1)) <= 2 else E["h_chico"]
            # Todo encabezado sale como <div>: el correo ya trae su propio <h2> y
            # los <h1>/<h2> anidados descuadran la jerarquía en algunos clientes.
            bloques.append(f'<div style="{estilo}">{_en_linea(m.group(2))}</div>')
            continue

        m = RE_CITA.match(linea)
        if m:
            if parrafo or elementos:
                cerrar()
            cita.append(m.group(1))
            continue

        m = RE_NUMERADA.match(linea)
        if m:
            if parrafo or cita or tipo_lista == "ul":
                cerrar()
            tipo_lista = "ol"
            elementos.append(m.group(1))
            continue

        m = RE_VINETA.match(linea)
        if m:
            if parrafo or cita or tipo_lista == "ol":
                cerrar()
            tipo_lista = "ul"
            elementos.append(m.group(1))
            continue

        # Continuación: si veníamos en lista o cita, la línea pertenece al último
        # elemento (el modelo parte renglones largos sin dejar línea en blanco).
        if elementos:
            elementos[-1] = f"{elementos[-1]} {linea.strip()}"
        elif cita:
            cita.append(linea.strip())
        else:
            parrafo.append(linea.strip())

    cerrar()
    return "".join(bloques)

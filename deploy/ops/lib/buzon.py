"""Lectura SOLO-LECTURA del buzón de Israel, compartida por los agentes.

`soporte.py` ya entra por IMAP con la cuenta real (SOPORTE_EMAIL +
SOPORTE_APP_PASSWORD). El SDR necesita lo mismo para UNA pregunta antes de
mandar un seguimiento: ¿este lead ya respondió? Sin esa verificación, la
secuencia le escribiría encima a alguien que ya contestó — peor que no dar
seguimiento.

Nunca marca, mueve ni borra nada: `select(..., readonly=True)`.
"""

from __future__ import annotations

import imaplib
import math
import os
import re
from datetime import datetime, timedelta, timezone


def _carpeta_todo(imap: imaplib.IMAP4_SSL) -> str:
    """Carpeta con el flag \\All (Gmail la nombra según el idioma de la cuenta).

    Buscamos ahí y no en INBOX porque una respuesta archivada, etiquetada o
    movida por un filtro sigue siendo una respuesta.
    """
    try:
        ok, carpetas = imap.list()
        if ok == "OK" and carpetas:
            for linea in carpetas:
                texto = (
                    linea.decode("utf-8", errors="replace")
                    if isinstance(linea, bytes)
                    else str(linea)
                )
                if "\\All" in texto:
                    m = re.search(r'"([^"]+)"\s*$', texto)
                    if m:
                        return m.group(1)
    except imaplib.IMAP4.error:
        pass
    return "INBOX"


def hay_correo_de(remitente: str, desde: datetime) -> bool | None:
    """¿Hay algún correo de `remitente` recibido desde `desde`?

    Devuelve True/False cuando se pudo revisar y **None** cuando no (sin
    credenciales, IMAP caído, búsqueda rechazada). None NO es "no hay": el
    llamador debe tratarlo como "no sé" y abstenerse.
    """
    cuenta = os.environ.get("SOPORTE_EMAIL")
    password = os.environ.get("SOPORTE_APP_PASSWORD")
    if not cuenta or not password:
        return None

    dias = max(1, math.ceil((datetime.now(timezone.utc) - desde).total_seconds() / 86400) + 1)
    imap = None
    try:
        imap = imaplib.IMAP4_SSL(os.environ.get("SOPORTE_IMAP_HOST", "imap.gmail.com"))
        imap.login(cuenta, password)
        imap.select(_carpeta_todo(imap), readonly=True)

        try:
            ok, resultado = imap.uid(
                "SEARCH", "X-GM-RAW", f'"from:{remitente} newer_than:{dias}d"'
            )
            if ok == "OK":
                return bool(resultado and resultado[0] and resultado[0].split())
        except imaplib.IMAP4.error:
            pass

        # Sin X-GM-RAW (servidor no-Gmail): IMAP estándar.
        corte = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%d-%b-%Y")
        ok, resultado = imap.uid("SEARCH", None, f'(FROM "{remitente}") SINCE {corte}')
        if ok != "OK":
            return None
        return bool(resultado and resultado[0] and resultado[0].split())
    except Exception as e:  # noqa: BLE001
        print(f"[buzon] no pude revisar respuestas de {remitente}: {e}")
        return None
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass

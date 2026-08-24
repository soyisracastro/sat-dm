"""Lectura SOLO-LECTURA del buzón de Israel, compartida por los agentes.

`soporte.py` ya entra por IMAP con la cuenta real (SOPORTE_EMAIL +
SOPORTE_APP_PASSWORD). El SDR necesita lo mismo para UNA pregunta antes de
mandar un seguimiento: ¿este lead ya respondió? Sin esa verificación, la
secuencia le escribiría encima a alguien que ya contestó — peor que no dar
seguimiento.

Nunca marca, mueve ni borra nada: `select(..., readonly=True)`.
"""

from __future__ import annotations

import email
import email.utils
import html as html_mod
import imaplib
import math
import os
import re
from datetime import datetime, timedelta, timezone
from email.header import decode_header


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


def _dec(valor: str | None) -> str:
    if not valor:
        return ""
    partes = []
    for texto, charset in decode_header(valor):
        if isinstance(texto, bytes):
            partes.append(texto.decode(charset or "utf-8", errors="replace"))
        else:
            partes.append(texto)
    return "".join(partes)


def _texto_plano(msg: email.message.Message) -> str:
    """Texto plano (o HTML desetiquetado) del mensaje, para un extracto corto."""
    def _payload(parte: email.message.Message) -> str:
        crudo = parte.get_payload(decode=True) or b""
        return crudo.decode(parte.get_content_charset() or "utf-8", errors="replace")

    if msg.is_multipart():
        html_fallback = ""
        for parte in msg.walk():
            if "attachment" in str(parte.get("Content-Disposition", "")):
                continue
            tipo = parte.get_content_type()
            if tipo == "text/plain":
                return _payload(parte)
            if tipo == "text/html" and not html_fallback:
                html_fallback = _payload(parte)
        texto = re.sub(r"<[^>]+>", " ", html_fallback)
        return html_mod.unescape(re.sub(r"\s+", " ", texto)).strip()
    if msg.get_content_type() == "text/html":
        texto = re.sub(r"<[^>]+>", " ", _payload(msg))
        return html_mod.unescape(re.sub(r"\s+", " ", texto)).strip()
    return _payload(msg)


def hilos_con(correo: str, n: int = 5, dias: int = 400) -> list[dict] | None:
    """Últimos ~n correos intercambiados con `correo` (como remitente o
    destinatario), para armar la bitácora de un cliente. Solo lectura sobre
    Todos los mensajes (incluye archivados). Más reciente primero.

    Devuelve [] cuando no hay historial y **None** cuando no se pudo revisar
    (sin credenciales, IMAP caído): el llamador trata None como "no sé".
    """
    cuenta = os.environ.get("SOPORTE_EMAIL")
    password = os.environ.get("SOPORTE_APP_PASSWORD")
    if not cuenta or not password or not correo:
        return None

    imap = None
    try:
        imap = imaplib.IMAP4_SSL(os.environ.get("SOPORTE_IMAP_HOST", "imap.gmail.com"))
        imap.login(cuenta, password)
        imap.select(_carpeta_todo(imap), readonly=True)

        uids: list[bytes] = []
        try:
            ok, resultado = imap.uid(
                "SEARCH", "X-GM-RAW",
                f'"(from:{correo} OR to:{correo}) newer_than:{dias}d"',
            )
            if ok == "OK" and resultado and resultado[0]:
                uids = resultado[0].split()
        except imaplib.IMAP4.error:
            uids = []
        if not uids:
            corte = (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%d-%b-%Y")
            ok, resultado = imap.uid(
                "SEARCH", None, f'(OR FROM "{correo}" TO "{correo}") SINCE {corte}'
            )
            if ok != "OK":
                return None
            uids = resultado[0].split() if resultado and resultado[0] else []

        salida: list[dict] = []
        for uid in reversed(uids[-n:]):  # UIDs ascendentes → los últimos son recientes
            ok, datos = imap.uid("FETCH", uid, "(BODY.PEEK[])")
            if ok != "OK" or not datos or not isinstance(datos[0], tuple):
                continue
            msg = email.message_from_bytes(datos[0][1])
            salida.append({
                "fecha": _dec(msg.get("Date")),
                "de": email.utils.parseaddr(_dec(msg.get("From")))[1],
                "asunto": _dec(msg.get("Subject")) or "(sin asunto)",
                "extracto": _texto_plano(msg)[:500],
            })
        return salida
    except Exception as e:  # noqa: BLE001
        print(f"[buzon] no pude leer el historial con {correo}: {e}")
        return None
    finally:
        if imap is not None:
            try:
                imap.logout()
            except Exception:  # noqa: BLE001
                pass


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

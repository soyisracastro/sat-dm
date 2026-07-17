"""Envío de correo por Amazon SES (mismas credenciales que apps/web)."""

from __future__ import annotations

import os


def enviar(
    asunto: str,
    html: str,
    texto: str,
    para: str | None = None,
    de: str | None = None,
    bcc: str | None = None,
    reply_to: str | None = None,
) -> None:
    """Manda un correo por SES.

    Sin `para`/`de` usa los defaults del reporte (REPORTE_TO/REPORTE_FROM),
    así los llamadores existentes no cambian.
    """
    import boto3

    # Mismos nombres de env que apps/web (AWS_SES_*), con fallback al estándar.
    cliente = boto3.client(
        "ses",
        region_name=os.environ.get("AWS_SES_REGION", "us-east-1"),
        aws_access_key_id=os.environ.get("AWS_SES_ACCESS_KEY_ID")
        or os.environ["AWS_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ.get("AWS_SES_SECRET_ACCESS_KEY")
        or os.environ["AWS_SECRET_ACCESS_KEY"],
    )
    destino: dict = {
        "ToAddresses": [para or os.environ.get("REPORTE_TO", "israel.castro@gmail.com")]
    }
    if bcc:
        destino["BccAddresses"] = [bcc]
    kwargs: dict = {
        "Source": de or os.environ.get("REPORTE_FROM", "no-reply@todoconta.com"),
        "Destination": destino,
        "Message": {
            "Subject": {"Data": asunto, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html, "Charset": "UTF-8"},
                "Text": {"Data": texto, "Charset": "UTF-8"},
            },
        },
    }
    if reply_to:
        kwargs["ReplyToAddresses"] = [reply_to]
    cliente.send_email(**kwargs)

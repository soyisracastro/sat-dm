"""Envío de correo por Amazon SES (mismas credenciales que apps/web)."""

from __future__ import annotations

import os


def enviar(asunto: str, html: str, texto: str) -> None:
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
    cliente.send_email(
        Source=os.environ.get("REPORTE_FROM", "no-reply@todoconta.com"),
        Destination={"ToAddresses": [os.environ.get("REPORTE_TO", "israel.castro@gmail.com")]},
        Message={
            "Subject": {"Data": asunto, "Charset": "UTF-8"},
            "Body": {
                "Html": {"Data": html, "Charset": "UTF-8"},
                "Text": {"Data": texto, "Charset": "UTF-8"},
            },
        },
    )

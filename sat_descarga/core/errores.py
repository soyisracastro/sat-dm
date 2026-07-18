"""
Errores ESPERADOS: fallos de entorno o del usuario, no bugs del agente.

Una credencial CIEC incorrecta, la descarga de Chromium bloqueada por la red
del usuario o el SAT caído son condiciones normales de operación: el mensaje
se muestra al usuario tal cual y quien lo reporta (jobs, warm-up, poller) lo
loguea como *warning* — no como error — para que la telemetría (Sentry captura
los logs de nivel ERROR) no los registre como bugs (TODOCONTA-DESKTOP-F, -5).

Hereda de RuntimeError para que los `except RuntimeError` existentes sigan
atrapándolos igual que siempre.
"""


class ErrorEsperado(RuntimeError):
    """Fallo esperado de cara al usuario; no se reporta a telemetría como bug."""

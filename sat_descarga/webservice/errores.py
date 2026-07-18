"""
Errores del Web Service del SAT que NO son culpa de la solicitud del usuario.

`CodEstatus=404 «Error no controlado»` es el error interno genérico del SAT:
llega en una respuesta SOAP exitosa (no es un fallo de red, así que el manejo
de timeouts/SSL no lo ve) pero significa "el servicio del SAT está fallando,
reintenta más tarde" — típico en fines de semana y ventanas de mantenimiento.
Verificado en vivo (2026-07-12): la misma solicitud falla igual desde
cualquier red, y minutos u horas después vuelve a funcionar sin cambios.
"""

from sat_descarga.core.errores import ErrorEsperado

# Códigos de estatus del WS que indican fallo interno transitorio del SAT
# (no un rechazo de la solicitud). Hoy solo el 404; si aparecen otros se
# agregan aquí.
CODIGOS_TRANSITORIOS = {"404"}


class ErrorTransitorioSAT(ErrorEsperado):
    """El SAT respondió con un error interno transitorio (p. ej. CodEstatus=404).

    Los routers lo traducen a HTTP 503 («el SAT está fallando, reintenta»),
    igual que los fallos de red — no a 400, que la UI pinta como rechazo
    definitivo de la solicitud.
    """

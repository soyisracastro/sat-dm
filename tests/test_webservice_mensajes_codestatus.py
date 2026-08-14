"""Traducción de los CodEstatus del WS a mensajes accionables.

El SAT devuelve etiquetas de tres palabras ("Certificado Inválido") que no le
dicen al contador qué hacer. Estos tests fijan el contrato del mensaje y, sobre
todo, el invariante que sostiene la lógica que ramifica por código leyendo el
string del error.
"""

import pytest

from sat_descarga.webservice.errores import _AYUDA_CODESTATUS, mensaje_rechazo


class TestMensajeRechazo:
    def test_305_manda_a_descarga_rapida_antes_que_a_renovar(self):
        # El caso de los certs del SAT de mayo 2023: el WS masiva los rechaza,
        # pero el portal SÍ los acepta. Renovar la e.firma es el último recurso,
        # no el primero — para la mayoría de usuarios no hace falta.
        m = mensaje_rechazo("305", "Certificado Inválido")
        assert "Descarga rápida" in m
        assert m.index("Descarga rápida") < m.index("renovar")

    def test_304_si_manda_a_renovar(self):
        # Revocado o caduco: aquí la renovación sí es la salida.
        m = mensaje_rechazo("304", "Certificado Revocado o Caduco")
        assert "renovar" in m.lower()
        assert "Descarga rápida" not in m

    @pytest.mark.parametrize("cod", sorted(_AYUDA_CODESTATUS))
    def test_todo_mensaje_conserva_el_codigo(self, cod):
        # INVARIANTE: `solicitud.py` reintenta el 5002 con `if "5002" not in str(e)`,
        # y soporte necesita el código para diagnosticar. Si un mensaje pierde el
        # `CodEstatus=<cod>`, esa lógica deja de disparar en silencio.
        assert f"CodEstatus={cod}" in mensaje_rechazo(cod, "mensaje del SAT")

    def test_codigo_sin_ayuda_cae_al_mensaje_crudo(self):
        m = mensaje_rechazo("9999", "Algo raro")
        assert m == "SAT rechazó la solicitud. CodEstatus=9999, Mensaje=Algo raro"

    def test_conserva_el_mensaje_del_sat(self):
        # El texto del SAT trae el detalle (p. ej. qué dato del request iba mal).
        m = mensaje_rechazo("305", "Certificado Inválido")
        assert "Certificado Inválido" in m


def _respuesta_soap(cod: str, mensaje: str) -> bytes:
    """Respuesta de SolicitaDescargaEmitidos con el CodEstatus dado."""
    return (
        '<?xml version="1.0"?>'
        '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"><s:Body>'
        '<SolicitaDescargaEmitidosResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">'
        f'<SolicitaDescargaEmitidosResult CodEstatus="{cod}" '
        f'Mensaje="{mensaje}" IdSolicitud=""/>'
        "</SolicitaDescargaEmitidosResponse></s:Body></s:Envelope>"
    ).encode("utf-8")


class TestIntegracionConElParser:
    def test_5002_sigue_disparando_el_reintento(self):
        """El reintento del rango agotado ramifica por el string del error."""
        from sat_descarga.webservice.solicitud import _parse_request_id

        resp = _respuesta_soap("5002", "Se han agotado las solicitudes de por vida")
        with pytest.raises(RuntimeError) as ei:
            _parse_request_id(resp, "SolicitaDescargaEmitidosResult")
        assert "5002" in str(ei.value)

    def test_305_llega_traducido_desde_la_respuesta_soap(self):
        from sat_descarga.webservice.solicitud import _parse_request_id

        resp = _respuesta_soap("305", "Certificado Inválido")
        with pytest.raises(RuntimeError, match="Descarga rápida"):
            _parse_request_id(resp, "SolicitaDescargaEmitidosResult")

    def test_404_sigue_siendo_transitorio_no_rechazo(self):
        # No romper el camino del 503: el 404 del SAT no es un rechazo.
        from sat_descarga.webservice.errores import ErrorTransitorioSAT
        from sat_descarga.webservice.solicitud import _parse_request_id

        resp = _respuesta_soap("404", "Error no Controlado")
        with pytest.raises(ErrorTransitorioSAT):
            _parse_request_id(resp, "SolicitaDescargaEmitidosResult")

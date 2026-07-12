"""El SAT caído/lento en los endpoints WS se traduce a 503 (no 500).

TODOCONTA-DESKTOP-13: los ReadTimeout de VerificaSolicitudDescarga subían como
`requests.ConnectionError` sin atrapar (hereda de IOError, no de RuntimeError)
→ 500 «unhandled» → un evento de Sentry por cada tormenta del SAT. El decorador
`@_sat_disponible` los convierte en HTTPException(503), que la UI trata como
transitorio y la telemetría excluye (failed_request_status_codes sin 503).
"""

import pytest

pytest.importorskip("fastapi")
import requests  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from sat_descarga.api import server  # noqa: E402
from sat_descarga.api.routers import webservice  # noqa: E402


class _FielFalsa:
    rfc = "XAXX010101000"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(webservice, "_get_fiel", lambda: _FielFalsa())
    monkeypatch.setattr(webservice, "_renovar_token", lambda: "token")
    return TestClient(server.app)


def _lanza(exc):
    def _fn(*args, **kwargs):
        raise exc
    return _fn


def test_verificar_sat_caido_es_503(client, monkeypatch):
    # El caso real del issue: ConnectionError envolviendo el ReadTimeout
    # agotado de urllib3 (Max retries exceeded ... Read timed out).
    monkeypatch.setattr(
        webservice, "consultar_solicitud",
        _lanza(requests.exceptions.ConnectionError("Max retries exceeded: Read timed out. (read timeout=60)")),
    )
    r = client.post("/verificar", json={"id_solicitud": "abc-123", "poll": False})
    assert r.status_code == 503
    assert "SAT no respondió" in r.json()["detail"]


def test_verificar_token_sat_caido_es_503(client, monkeypatch):
    # _renovar_token también golpea al SAT y corre FUERA del try del endpoint:
    # el decorador debe cubrirlo igual.
    monkeypatch.setattr(
        webservice, "_renovar_token",
        _lanza(requests.exceptions.ReadTimeout("Read timed out")),
    )
    r = client.post("/verificar", json={"id_solicitud": "abc-123", "poll": False})
    assert r.status_code == 503


def test_verificar_error_de_negocio_sigue_siendo_400(client, monkeypatch):
    # Los RuntimeError (SOAP Fault, rechazos del SAT) conservan su contrato 400.
    monkeypatch.setattr(
        webservice, "consultar_solicitud",
        _lanza(RuntimeError("SOAP Fault a:InternalServiceFault")),
    )
    r = client.post("/verificar", json={"id_solicitud": "abc-123", "poll": False})
    assert r.status_code == 400


def test_solicitar_sat_caido_es_503(client, monkeypatch):
    monkeypatch.setattr(
        webservice, "solicitar_descarga",
        _lanza(requests.exceptions.SSLError("EOF occurred in violation of protocol")),
    )
    r = client.post("/solicitar", json={
        "fecha_inicio": "2026-06-01",
        "fecha_fin": "2026-06-30",
    })
    assert r.status_code == 503


def test_solicitar_error_interno_del_sat_es_503(client, monkeypatch):
    # CodEstatus=404 «Error no controlado»: el SAT respondió (no es fallo de
    # red) pero con su error interno genérico. Visto en vivo 2026-07-12: falla
    # idéntico desde cualquier red y se resuelve solo — transitorio, NO un
    # rechazo de la solicitud (antes se mostraba como 400 definitivo).
    from sat_descarga.webservice.errores import ErrorTransitorioSAT

    monkeypatch.setattr(
        webservice, "solicitar_descarga",
        _lanza(ErrorTransitorioSAT(
            "El SAT está fallando internamente (CodEstatus=404, Error no controlado). "
            "No es un problema de tu solicitud; reintenta en unos minutos."
        )),
    )
    r = client.post("/solicitar", json={
        "fecha_inicio": "2026-06-01",
        "fecha_fin": "2026-06-30",
    })
    assert r.status_code == 503
    assert "reintenta" in r.json()["detail"]


def test_solicitar_rechazo_real_sigue_siendo_400(client, monkeypatch):
    # Un rechazo genuino (p. ej. 5002 límite agotado) conserva el contrato 400.
    monkeypatch.setattr(
        webservice, "solicitar_descarga",
        _lanza(RuntimeError("SAT rechazó la solicitud. CodEstatus=5002, Mensaje=...")),
    )
    r = client.post("/solicitar", json={
        "fecha_inicio": "2026-06-01",
        "fecha_fin": "2026-06-30",
    })
    assert r.status_code == 400


def test_parse_request_id_distingue_404_de_rechazos():
    # A nivel parser: 404 → ErrorTransitorioSAT; otros códigos → RuntimeError.
    from sat_descarga.webservice.errores import ErrorTransitorioSAT
    from sat_descarga.webservice.solicitud import _parse_request_id

    def _respuesta(cod, mensaje, id_solicitud=""):
        return (
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            "<s:Body>"
            '<SolicitaDescargaEmitidosResponse xmlns="http://DescargaMasivaTerceros.sat.gob.mx">'
            f'<SolicitaDescargaEmitidosResult CodEstatus="{cod}" Mensaje="{mensaje}"'
            + (f' IdSolicitud="{id_solicitud}"' if id_solicitud else "")
            + "/></SolicitaDescargaEmitidosResponse></s:Body></s:Envelope>"
        ).encode()

    with pytest.raises(ErrorTransitorioSAT, match="reintenta"):
        _parse_request_id(
            _respuesta("404", "Error no controlado"), "SolicitaDescargaEmitidosResult"
        )

    with pytest.raises(RuntimeError, match="rechazó"):
        _parse_request_id(
            _respuesta("5002", "Se agotó las solicitudes"), "SolicitaDescargaEmitidosResult"
        )

    assert (
        _parse_request_id(
            _respuesta("5000", "Solicitud aceptada", id_solicitud="abc-123"),
            "SolicitaDescargaEmitidosResult",
        )
        == "abc-123"
    )

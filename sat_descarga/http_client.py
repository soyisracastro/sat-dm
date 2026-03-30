"""
Cliente HTTP con reintentos para los endpoints del SAT.

El SAT tiene ~25% de fallos SSL/TLS. Se usan 6 reintentos con
backoff exponencial para alcanzar 100% de éxito.
"""

import ssl
import logging
from typing import Optional

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .config import HTTP_RETRIES, HTTP_BACKOFF_FACTOR, HTTP_TIMEOUT

logger = logging.getLogger(__name__)


class SATTLSAdapter(HTTPAdapter):
    """
    Adaptador TLS para los servidores del SAT.

    Los servidores del SAT son inestables (~25% de fallos SSL). La solución
    es usar TLS 1.2 con check_hostname=False y verify=False, más reintentos.

    Nota: TLSv1.0 forzado era la solución original pero Python 3.12+ y
    macOS/OpenSSL modernos lo tienen deshabilitado a nivel del SO.
    Los servidores del SAT soportan TLS 1.2 sin problema.
    """

    def _make_ssl_context(self) -> ssl.SSLContext:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx

    def init_poolmanager(self, *args, **kwargs):
        kwargs["ssl_context"] = self._make_ssl_context()
        super().init_poolmanager(*args, **kwargs)

    def proxy_manager_for(self, proxy, **proxy_kwargs):
        proxy_kwargs["ssl_context"] = self._make_ssl_context()
        return super().proxy_manager_for(proxy, **proxy_kwargs)


def _build_session() -> requests.Session:
    """Construye una sesión con reintentos y TLS compatible con el SAT."""
    session = requests.Session()

    retry = Retry(
        total=HTTP_RETRIES,
        backoff_factor=HTTP_BACKOFF_FACTOR,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["POST"],
        raise_on_status=False,
    )

    adapter = SATTLSAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", HTTPAdapter(max_retries=retry))

    return session


def make_request(
    url: str,
    body: bytes,
    headers: dict,
    operation: str = "SOAP",
    session: Optional[requests.Session] = None,
) -> bytes:
    """
    Realiza una llamada POST al endpoint del SAT con reintentos.

    Args:
        url: Endpoint del Web Service.
        body: Cuerpo SOAP en bytes.
        headers: Headers HTTP incluyendo SOAPAction y Content-Type.
        operation: Nombre descriptivo para el log.
        session: Sesión reutilizable (se crea una nueva si no se proporciona).

    Returns:
        Cuerpo de la respuesta en bytes.

    Raises:
        requests.HTTPError: Si el servidor devuelve un error HTTP no recuperable.
        RuntimeError: Si el SOAP Fault contiene un error de negocio.
    """
    if session is None:
        session = _build_session()

    logger.info("[%s] POST %s", operation, url)
    logger.debug("[%s] REQUEST BODY:\n%s", operation, body.decode(errors="replace"))

    # Suprimir warnings de SSL no verificado (el SAT tiene certs problemáticos)
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    resp = session.post(
        url,
        data=body,
        headers=headers,
        timeout=HTTP_TIMEOUT,
        verify=False,  # Los certs del SAT suelen ser problemáticos
    )

    logger.info("[%s] Status: %d", operation, resp.status_code)
    logger.debug("[%s] RESPONSE BODY:\n%s", operation, resp.content.decode(errors="replace"))

    # El SAT devuelve 500 para SOAP Faults (comportamiento estándar SOAP)
    if resp.status_code not in (200, 500):
        resp.raise_for_status()

    # Verificar si hay SOAP Fault
    _check_soap_fault(resp.content, operation)

    return resp.content


def _check_soap_fault(content: bytes, operation: str) -> None:
    """Lanza RuntimeError si la respuesta contiene un SOAP Fault."""
    try:
        from lxml import etree
        root = etree.fromstring(content)
        fault = root.find(".//{http://schemas.xmlsoap.org/soap/envelope/}Fault")
        if fault is not None:
            code_el = fault.find("faultcode")
            msg_el = fault.find("faultstring")
            code = code_el.text if code_el is not None else "Unknown"
            msg = msg_el.text if msg_el is not None else "Error desconocido"
            raise RuntimeError(f"[{operation}] SOAP Fault {code}: {msg}")
    except RuntimeError:
        raise
    except Exception:
        # Si no podemos parsear el XML, no bloqueamos
        pass

"""Tests del flujo CIEC captcha-only.

Cubren la lógica pura, sin red/browser/GUI:
- decodificación del data-URI de la imagen del captcha (`bytes_de_data_uri`),
- política de reintentos (`_login_ciec_con_reintentos`): 1 + 2 reintentos, éxito en
  un intento intermedio, cancelación por el usuario y cancelación al agotar intentos.
"""

import base64

import pytest

from sat_descarga.portal.captcha import bytes_de_data_uri
from sat_descarga.portal.login import (
    _login_ciec_con_reintentos,
    _es_error_credenciales,
    CredencialCIECInvalida,
)


# --- bytes_de_data_uri -----------------------------------------------------

def test_data_uri_decodifica_con_prefijo():
    crudo = b"\xff\xd8\xff\xe0captcha-bytes"
    uri = "data:image/jpeg;base64," + base64.b64encode(crudo).decode()
    assert bytes_de_data_uri(uri) == crudo


def test_data_uri_sin_prefijo():
    crudo = b"abc123"
    assert bytes_de_data_uri(base64.b64encode(crudo).decode()) == crudo


def test_data_uri_vacio_lanza():
    with pytest.raises(ValueError):
        bytes_de_data_uri("")


# --- política de reintentos ------------------------------------------------

class _Espia:
    """Registra llamadas y simula los pasos del login para probar la política."""

    def __init__(self, exitos, captchas=None):
        # exitos: lista de bool que devolverá enviar() en cada intento.
        # captchas: lista de textos que devolverá pedir_captcha() (None = cancelar).
        self.exitos = list(exitos)
        self.captchas = captchas
        self.rellenos = 0
        self.lecturas = 0
        self.enviados = []
        self.intentos_pedidos = []

    def rellenar(self):
        self.rellenos += 1

    def leer_img(self):
        self.lecturas += 1
        return b"img"

    def pedir(self, img, intento, maximo):
        self.intentos_pedidos.append((intento, maximo))
        if self.captchas is not None:
            return self.captchas[intento - 1]
        return f"CAP{intento}"

    def enviar(self, texto):
        self.enviados.append(texto)
        return self.exitos[len(self.enviados) - 1]


def test_exito_primer_intento():
    e = _Espia(exitos=[True])
    _login_ciec_con_reintentos(e.rellenar, e.leer_img, e.pedir, e.enviar, max_intentos=3)
    assert e.rellenos == 1 and e.lecturas == 1 and e.enviados == ["CAP1"]


def test_exito_segundo_intento():
    e = _Espia(exitos=[False, True])
    _login_ciec_con_reintentos(e.rellenar, e.leer_img, e.pedir, e.enviar, max_intentos=3)
    # Reintenta: rellena/lee/pide 2 veces y envía 2 veces.
    assert e.rellenos == 2 and e.lecturas == 2
    assert e.enviados == ["CAP1", "CAP2"]
    assert e.intentos_pedidos == [(1, 3), (2, 3)]


def test_cancela_tras_agotar_intentos():
    e = _Espia(exitos=[False, False, False])
    with pytest.raises(RuntimeError, match="3 intentos"):
        _login_ciec_con_reintentos(e.rellenar, e.leer_img, e.pedir, e.enviar, max_intentos=3)
    assert len(e.enviados) == 3  # exactamente 3 intentos, no más


def test_usuario_cancela_no_envia():
    # pedir_captcha devuelve None (el usuario cerró la ventana) → aborta sin enviar.
    e = _Espia(exitos=[True], captchas=[None])
    with pytest.raises(RuntimeError, match="cancelad"):
        _login_ciec_con_reintentos(e.rellenar, e.leer_img, e.pedir, e.enviar, max_intentos=3)
    assert e.enviados == []


# --- fail-fast: error de credenciales -------------------------------------

@pytest.mark.parametrize("msg", [
    "El RFC o la contraseña son incorrectos",
    "Contraseña incorrecta",
    "Usuario o clave inválidos",
    "Los datos no son válidos",
])
def test_clasifica_error_de_credenciales(msg):
    assert _es_error_credenciales(msg) is True


@pytest.mark.parametrize("msg", [
    "El texto de la imagen es incorrecto",
    "El captcha no coincide",
    "Captcha incorrecto",
    "",
])
def test_clasifica_error_de_captcha_o_vacio(msg):
    assert _es_error_credenciales(msg) is False


def test_fail_fast_aborta_sin_reintentar_captcha():
    # Si enviar() lanza CredencialCIECInvalida (RFC/contraseña mal), el loop NO
    # reintenta el captcha: se propaga y la operación aborta en el primer intento.
    e = _Espia(exitos=[True, True, True])

    def enviar_credencial_mala(texto):
        e.enviados.append(texto)
        raise CredencialCIECInvalida("El SAT rechazó el acceso: «Contraseña incorrecta».")

    with pytest.raises(CredencialCIECInvalida, match="Contraseña"):
        _login_ciec_con_reintentos(
            e.rellenar, e.leer_img, e.pedir, enviar_credencial_mala, max_intentos=3
        )
    assert len(e.enviados) == 1  # un solo intento; no se pidió captcha de nuevo
    assert e.intentos_pedidos == [(1, 3)]

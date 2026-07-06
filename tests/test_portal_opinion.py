"""Tests de las constantes/flujo de la Opinión de Cumplimiento 32-D.

Verifican decisiones clave del flujo (entrada por el SPA que genera el OAuth2/PKCE
fresco, predicado de aterrizaje que distingue entrada de landing pese a compartir
host, captura del PDF al aterrizar), sin tocar red/browser.
"""

from sat_descarga.portal import opinion as O


def test_entrada_es_el_enlace_ingresa_sin_pkce():
    # No se reusa la URL NIDP literal (sus params PKCE/state/nonce son efímeros): se
    # entra por el enlace «Ingresa» del SPA, que genera el flujo OAuth2 fresco.
    assert O.OPINION_URL_ENTRADA == (
        "https://ptsc32d.clouda.sat.gob.mx/?/reporteOpinion32DContribuyente"
    )
    assert "code_challenge" not in O.OPINION_URL_ENTRADA
    # e.firma entra por la misma URL; cambia a e.firma una vez en el NIDP.
    assert O.OPINION_URL_ENTRADA_FIEL == O.OPINION_URL_ENTRADA


def test_landing_es_ptsc32d():
    assert O.OPINION_LANDING == "ptsc32d.clouda.sat.gob.mx"


def test_predicado_landing_distingue_entrada_de_aterrizaje():
    # Entrada y landing comparten host; el predicado NO debe disparar en la entrada
    # (lleva `?/`) ni en el login NIDP ni en el callback OAuth transitorio.
    assert not O._es_landing_opinion(O.OPINION_URL_ENTRADA)
    assert not O._es_landing_opinion(
        "https://loginda.siat.sat.gob.mx/nidp/app/login?id=ciec&sid=0"
    )
    assert not O._es_landing_opinion(
        "https://ptsc32d.clouda.sat.gob.mx:443/oauth2/callback"
    )
    # Sí debe disparar en el aterrizaje real (hash route del SPA).
    assert O._es_landing_opinion(
        "https://ptsc32d.clouda.sat.gob.mx/#/reporteOpinion32DContribuyente"
    )


def test_predicado_landing_no_dispara_en_login_con_target_codificado():
    # Regresión de la corrida real (jul 2026, Sentry TODOCONTA-DESKTOP-Z): la página
    # de login de loginda lleva `target=` con la URL authz codificada, donde el
    # hostname de ptsc32d aparece LITERAL y `/oauth` va como `%2Foauth`. Un predicado
    # por substring disparaba "login exitoso" sin salir del login. Se compara el
    # host parseado, no la URL completa.
    login_con_target = (
        "https://loginda.siat.sat.gob.mx/nidp/app/login?id=fiel&sid=0"
        "&option=credential&sid=0"
        "&target=https%3A%2F%2Floginda.siat.sat.gob.mx%2Fnidp%2Foauth%2Fnam%2Fauthz"
        "%3Fclient_id%3D40397829-65e9-43dc-8e8b-f0515afce784"
        "%26redirect_uri%3Dhttps%3A%2F%2Fptsc32d.clouda.sat.gob.mx%3A443"
        "%2Foauth2%2Fcallback%26response_type%3Dcode%26response_mode%3Dform_post"
    )
    assert not O._es_landing_opinion(login_con_target)
    # El endpoint authz (donde la corrida real quedó atorada) tampoco es landing.
    authz = (
        "https://loginda.siat.sat.gob.mx/nidp/oauth/nam/authz?client_id=40397829"
        "&redirect_uri=https%3A%2F%2Fptsc32d.clouda.sat.gob.mx%3A443%2Foauth2%2Fcallback"
        "&response_type=code&response_mode=form_post"
    )
    assert not O._es_landing_opinion(authz)


def test_api_publica_opinion():
    assert callable(O.descargar_opinion_ciec)
    assert callable(O.descargar_opinion_fiel)

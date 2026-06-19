"""Tests de sat_descarga/portal/setup.py (aprovisionamiento de Chromium).

Cubren la causa raíz del "Executable doesn't exist" en producción: la
verificación debe ser por REVISIÓN exacta (browsers.json) e incluir el
binario headless shell — una carpeta de una versión anterior de Playwright
no cuenta como instalado. Nada aquí descarga browsers reales: la instalación
se monkeypatchea.
"""

import json
from types import SimpleNamespace

import pytest

from sat_descarga.portal import setup


@pytest.fixture(autouse=True)
def estado_limpio(monkeypatch):
    """Revierte el flag global del conftest y arranca cada test en frío."""
    monkeypatch.setattr(setup, "_install_checked", False)
    monkeypatch.setattr(setup, "_estado", {"estado": "pendiente", "detalle": None})
    monkeypatch.setattr(setup, "_path_externo", False)


def _browsers_json(tmp_path, revision="1223"):
    """Escribe un browsers.json fake y apunta el módulo a él."""
    path = tmp_path / "browsers.json"
    path.write_text(json.dumps({
        "browsers": [
            {"name": "chromium", "revision": revision, "installByDefault": True},
            {"name": "chromium-headless-shell", "revision": revision},
            {"name": "firefox", "revision": "9999"},  # ruido: no es requerido
        ]
    }), encoding="utf-8")
    return path


def _instalar_browser(browsers_path, nombre, revision, completo=True):
    """Simula una carpeta de browser descargada (con o sin marker)."""
    d = browsers_path / f"{nombre.replace('-', '_')}-{revision}"
    d.mkdir(parents=True, exist_ok=True)
    if completo:
        (d / "INSTALLATION_COMPLETE").write_text("")
    return d


# ---------------------------------------------------------------------------
# _navegadores_instalados — verificación por revisión exacta
# ---------------------------------------------------------------------------


def test_instalados_con_revision_correcta(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: _browsers_json(tmp_path))
    browsers = tmp_path / "browsers"
    _instalar_browser(browsers, "chromium", "1223")
    _instalar_browser(browsers, "chromium-headless-shell", "1223")
    assert setup._navegadores_instalados(browsers) is True


def test_revision_vieja_no_cuenta(tmp_path, monkeypatch):
    """El bug original: tras actualizar la app, la carpeta vieja pasaba el check."""
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: _browsers_json(tmp_path))
    browsers = tmp_path / "browsers"
    _instalar_browser(browsers, "chromium", "1187")
    _instalar_browser(browsers, "chromium-headless-shell", "1187")
    assert setup._navegadores_instalados(browsers) is False


def test_falta_headless_shell(tmp_path, monkeypatch):
    """Chromium completo pero sin el headless shell (el binario del error real)."""
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: _browsers_json(tmp_path))
    browsers = tmp_path / "browsers"
    _instalar_browser(browsers, "chromium", "1223")
    assert setup._navegadores_instalados(browsers) is False


def test_descarga_interrumpida_no_cuenta(tmp_path, monkeypatch):
    """Carpeta presente pero sin INSTALLATION_COMPLETE (descarga a medias)."""
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: _browsers_json(tmp_path))
    browsers = tmp_path / "browsers"
    _instalar_browser(browsers, "chromium", "1223")
    _instalar_browser(browsers, "chromium-headless-shell", "1223", completo=False)
    assert setup._navegadores_instalados(browsers) is False


def test_carpeta_inexistente(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: _browsers_json(tmp_path))
    assert setup._navegadores_instalados(tmp_path / "no-existe") is False


def test_fallback_sin_browsers_json(tmp_path, monkeypatch):
    """Sin browsers.json: pide AMBOS binarios completos, sin validar revisión."""
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: None)
    browsers = tmp_path / "browsers"
    _instalar_browser(browsers, "chromium", "1100")
    assert setup._navegadores_instalados(browsers) is False  # falta headless shell
    _instalar_browser(browsers, "chromium-headless-shell", "1100")
    assert setup._navegadores_instalados(browsers) is True


def test_browsers_json_corrupto_cae_al_fallback(tmp_path, monkeypatch):
    roto = tmp_path / "browsers.json"
    roto.write_text("{esto no es json", encoding="utf-8")
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: roto)
    assert setup._revisiones_requeridas() is None


# ---------------------------------------------------------------------------
# asegurar_chromium — instalación on-demand y transiciones de estado
# ---------------------------------------------------------------------------


@pytest.fixture
def entorno_instalacion(tmp_path, monkeypatch):
    """Aísla asegurar_chromium(): paths en tmp + instalador fake registrable."""
    browsers = tmp_path / "browsers"
    browsers.mkdir()
    monkeypatch.setattr(setup, "_browsers_json_path", lambda: _browsers_json(tmp_path))
    monkeypatch.setattr(setup, "configurar_playwright_browsers_path", lambda: browsers)

    llamadas = []

    def instalador_fake():
        llamadas.append(True)
        _instalar_browser(browsers, "chromium", "1223")
        _instalar_browser(browsers, "chromium-headless-shell", "1223")

    monkeypatch.setattr(setup, "_instalar_chromium", instalador_fake)
    return SimpleNamespace(browsers=browsers, llamadas=llamadas)


def test_asegurar_instala_si_falta(entorno_instalacion):
    assert setup.estado_navegador()["estado"] == "pendiente"
    setup.asegurar_chromium()
    assert len(entorno_instalacion.llamadas) == 1
    assert setup.estado_navegador()["estado"] == "listo"
    assert setup.navegador_listo() is True


def test_asegurar_instala_con_revision_vieja(entorno_instalacion):
    """El fix del bug: una revisión anterior en disco dispara la reinstalación."""
    _instalar_browser(entorno_instalacion.browsers, "chromium", "1187")
    _instalar_browser(entorno_instalacion.browsers, "chromium-headless-shell", "1187")
    setup.asegurar_chromium()
    assert len(entorno_instalacion.llamadas) == 1


def test_asegurar_noop_si_ya_instalado(entorno_instalacion):
    _instalar_browser(entorno_instalacion.browsers, "chromium", "1223")
    _instalar_browser(entorno_instalacion.browsers, "chromium-headless-shell", "1223")
    setup.asegurar_chromium()
    assert entorno_instalacion.llamadas == []
    assert setup.estado_navegador()["estado"] == "listo"
    # Segunda llamada: cortocircuito por _install_checked.
    setup.asegurar_chromium()
    assert entorno_instalacion.llamadas == []


def test_asegurar_force_reverifica(entorno_instalacion):
    setup.asegurar_chromium()
    assert len(entorno_instalacion.llamadas) == 1
    # Alguien borró el cache con el proceso vivo:
    for d in entorno_instalacion.browsers.iterdir():
        (d / "INSTALLATION_COMPLETE").unlink()
    setup.asegurar_chromium()  # sin force: no nota nada
    assert len(entorno_instalacion.llamadas) == 1
    setup.asegurar_chromium(force=True)
    assert len(entorno_instalacion.llamadas) == 2


def test_asegurar_propaga_error_y_deja_estado(entorno_instalacion, monkeypatch):
    def instalador_roto():
        raise RuntimeError("La descarga de Chromium falló")

    monkeypatch.setattr(setup, "_instalar_chromium", instalador_roto)
    with pytest.raises(RuntimeError, match="descarga de Chromium"):
        setup.asegurar_chromium()
    assert setup.estado_navegador()["estado"] == "error"
    # El flag NO queda marcado: el siguiente intento reintenta.
    assert setup._install_checked is False


# ---------------------------------------------------------------------------
# lanzar_chromium — auto-reparación al lanzar
# ---------------------------------------------------------------------------


def _fake_playwright(launch):
    return SimpleNamespace(chromium=SimpleNamespace(launch=launch))


def test_lanzar_reintenta_si_falta_binario(monkeypatch):
    fuerzas = []
    monkeypatch.setattr(
        setup, "asegurar_chromium", lambda force=False: fuerzas.append(force)
    )
    intentos = []

    def launch(**kwargs):
        intentos.append(kwargs)
        if len(intentos) == 1:
            raise Exception(
                "BrowserType.launch: Executable doesn't exist at .../headless_shell"
            )
        return "browser"

    assert setup.lanzar_chromium(_fake_playwright(launch), headless=True) == "browser"
    assert len(intentos) == 2
    assert fuerzas == [False, True]  # check normal + reinstalación forzada


def test_lanzar_no_reintenta_otros_errores(monkeypatch):
    monkeypatch.setattr(setup, "asegurar_chromium", lambda force=False: None)

    def launch(**kwargs):
        raise Exception("BrowserType.launch: Timeout 30000ms exceeded")

    with pytest.raises(Exception, match="Timeout"):
        setup.lanzar_chromium(_fake_playwright(launch))


def test_lanzar_doble_fallo_da_mensaje_en_espanol(monkeypatch):
    monkeypatch.setattr(setup, "asegurar_chromium", lambda force=False: None)

    def launch(**kwargs):
        raise Exception("Executable doesn't exist at /x")

    with pytest.raises(RuntimeError, match="navegador de descargas"):
        setup.lanzar_chromium(_fake_playwright(launch))


# ---------------------------------------------------------------------------
# warmup_async
# ---------------------------------------------------------------------------


def test_warmup_respeta_skip(monkeypatch):
    monkeypatch.setenv("SAT_AGENT_SKIP_BROWSER_WARMUP", "1")
    assert setup.warmup_async() is None


def test_warmup_corre_asegurar(monkeypatch):
    monkeypatch.delenv("SAT_AGENT_SKIP_BROWSER_WARMUP", raising=False)
    llamado = []
    monkeypatch.setattr(setup, "asegurar_chromium", lambda: llamado.append(True))
    t = setup.warmup_async()
    assert t is not None
    t.join(timeout=5)
    assert llamado == [True]


def test_warmup_no_propaga_errores(monkeypatch):
    monkeypatch.delenv("SAT_AGENT_SKIP_BROWSER_WARMUP", raising=False)

    def truena():
        raise RuntimeError("sin internet")

    monkeypatch.setattr(setup, "asegurar_chromium", truena)
    t = setup.warmup_async()
    t.join(timeout=5)  # no debe matar nada; el error queda en el log/estado


# ---------------------------------------------------------------------------
# _instalar_chromium — TMPDIR propio (anti-EACCES) + reintento
# ---------------------------------------------------------------------------


def test_instalar_redirige_tmpdir_a_carpeta_propia(tmp_path, monkeypatch):
    """El temp de la descarga apunta a una carpeta nuestra escribible (no al del
    sistema, que da EACCES en apps en cuarentena de macOS)."""
    cache = tmp_path / "TodoConta"
    monkeypatch.setattr(setup, "_browsers_dir", lambda: cache / "playwright-browsers")
    monkeypatch.setattr(
        setup, "_comando_install_chromium", lambda: ["node", "cli.js", "install", "chromium"]
    )
    capturado = {}

    def fake_run(cmd, **kwargs):
        capturado["env"] = kwargs["env"]
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(setup.subprocess, "run", fake_run)
    setup._instalar_chromium()

    env = capturado["env"]
    assert env["TMPDIR"] == env["TEMP"] == env["TMP"]
    assert env["TMPDIR"].endswith("download-tmp")
    assert (cache / "download-tmp").is_dir()  # se creó


def test_instalar_reintenta_y_da_mensaje_util(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "_browsers_dir", lambda: tmp_path / "playwright-browsers")
    monkeypatch.setattr(setup, "_comando_install_chromium", lambda: ["node", "x"])
    intentos = []

    def fake_run(cmd, **kwargs):
        intentos.append(1)
        return SimpleNamespace(returncode=1, stdout="out", stderr="EACCES")

    monkeypatch.setattr(setup.subprocess, "run", fake_run)
    with pytest.raises(RuntimeError, match="Aplicaciones"):
        setup._instalar_chromium()
    assert len(intentos) == 2  # un reintento


def test_instalar_exito_no_reintenta(tmp_path, monkeypatch):
    monkeypatch.setattr(setup, "_browsers_dir", lambda: tmp_path / "playwright-browsers")
    monkeypatch.setattr(setup, "_comando_install_chromium", lambda: ["node", "x"])
    intentos = []

    def fake_run(cmd, **kwargs):
        intentos.append(1)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(setup.subprocess, "run", fake_run)
    setup._instalar_chromium()  # no debe lanzar
    assert len(intentos) == 1

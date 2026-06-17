"""Regresión: la copia de trabajo de la e.firma vive en una ruta ABSOLUTA bajo
~/.sat-descarga, nunca relativa al cwd.

Bug original (WinError 5 en Windows): `EFIRMA_DIR = Path("efirma")` era relativa.
Bajo Electron empaquetado el agente arranca con cwd en el directorio de instalación
(solo-lectura por UAC), así que `mkdir("efirma")` / copiar ahí reventaba con
"[WinError 5] Acceso denegado". Anclar EFIRMA_DIR a CONFIG_DIR (absoluta y siempre
escribible) lo cura y, de paso, hace que las rutas guardadas en empresas.json sean
absolutas (antes quedaban relativas y solo resolvían si el cwd coincidía).

Este módulo NO usa el fixture autouse `temp_config` de test_config_store.py (que
parchea EFIRMA_DIR), justo para validar el valor por defecto real del módulo.
"""

from pathlib import Path

from sat_descarga.cli import config_store


def test_efirma_dir_es_absoluta_bajo_config_dir():
    # El default del módulo nunca debe volver a ser relativo (regresión WinError 5).
    assert config_store.EFIRMA_DIR.is_absolute()
    assert config_store.EFIRMA_DIR == config_store.CONFIG_DIR / "efirma"
    assert config_store.CONFIG_DIR == Path.home() / ".sat-descarga"


def test_registro_ignora_el_cwd(tmp_path, monkeypatch, test_cer, test_key, test_password):
    """Con EFIRMA_DIR absoluta, los .cer/.key se copian a la ruta anclada aunque el
    cwd sea otro; y empresas.json guarda rutas ABSOLUTAS."""
    config_dir = tmp_path / ".sat-descarga"
    monkeypatch.setattr(config_store, "CONFIG_DIR", config_dir)
    monkeypatch.setattr(config_store, "EFIRMA_DIR", config_dir / "efirma")
    # Aísla el respaldo visible para que no escriba en el ~/Documents real.
    monkeypatch.setattr(
        config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta")
    )

    otro_cwd = tmp_path / "otro_cwd"
    otro_cwd.mkdir()
    monkeypatch.chdir(otro_cwd)

    rfc = config_store.add_empresa("Test", test_cer, test_key, test_password)

    # Aterriza en la ruta absoluta anclada, NO en el cwd.
    assert (config_dir / "efirma" / rfc / "fiel.cer").exists()
    assert (config_dir / "efirma" / rfc / "fiel.key").exists()
    assert not (otro_cwd / "efirma").exists()

    empresa = config_store.get_empresa(rfc)
    assert Path(empresa["cer_path"]).is_absolute()
    assert Path(empresa["key_path"]).is_absolute()

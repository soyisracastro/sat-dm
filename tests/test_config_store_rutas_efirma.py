"""Migración de rutas relativas de la e.firma en empresas.json.

Los catálogos viejos guardaban `efirma/{RFC}/fiel.cer` — relativo al cwd del
proceso. Funcionaba solo por accidente en dev (el agente arranca en la raíz del
repo, que tiene una carpeta `efirma/`); en la app empacada el cwd es la carpeta
del binario y la carga truena con `[Errno 2] No such file or directory`.
"""

import json

import pytest

from sat_descarga.cli import config_store


@pytest.fixture
def catalogo_aislado(tmp_path, monkeypatch):
    """Apunta CONFIG_DIR/EFIRMA_DIR a un tmp para no tocar ~/.sat-descarga."""
    config = tmp_path / "config"
    config.mkdir()
    monkeypatch.setattr(config_store, "CONFIG_DIR", config)
    monkeypatch.setattr(config_store, "EFIRMA_DIR", config / "efirma")
    monkeypatch.setattr(config_store, "_empresas_path", lambda: config / "empresas.json")
    return config


def _escribir_catalogo(config, cer, key, rfc="SSA980330HU1"):
    (config / "empresas.json").write_text(
        json.dumps({
            "empresas": {rfc: {"nombre": "PRUEBA", "metodos": ["fiel"],
                               "cer_path": cer, "key_path": key}},
            "default_rfc": rfc,
        }),
        encoding="utf-8",
    )


class TestMigracionRutasRelativas:
    def test_resuelve_contra_config_dir(self, catalogo_aislado):
        # Caso normal: el archivo ya vive en ~/.sat-descarga/efirma/{RFC}/.
        destino = catalogo_aislado / "efirma" / "SSA980330HU1"
        destino.mkdir(parents=True)
        (destino / "fiel.cer").write_bytes(b"cer")
        (destino / "fiel.key").write_bytes(b"key")
        _escribir_catalogo(
            catalogo_aislado,
            "efirma/SSA980330HU1/fiel.cer", "efirma/SSA980330HU1/fiel.key",
        )

        emp = config_store.load_empresas()["empresas"]["SSA980330HU1"]
        assert emp["cer_path"] == str(destino / "fiel.cer")
        assert emp["key_path"] == str(destino / "fiel.key")

    def test_copia_desde_el_cwd_legacy(self, catalogo_aislado, tmp_path, monkeypatch):
        # El archivo solo existe donde lo resolvía la versión vieja (cwd).
        cwd = tmp_path / "repo"
        (cwd / "efirma" / "SSA980330HU1").mkdir(parents=True)
        (cwd / "efirma" / "SSA980330HU1" / "fiel.cer").write_bytes(b"contenido-cer")
        (cwd / "efirma" / "SSA980330HU1" / "fiel.key").write_bytes(b"contenido-key")
        monkeypatch.chdir(cwd)
        _escribir_catalogo(
            catalogo_aislado,
            "efirma/SSA980330HU1/fiel.cer", "efirma/SSA980330HU1/fiel.key",
        )

        emp = config_store.load_empresas()["empresas"]["SSA980330HU1"]
        canonico = catalogo_aislado / "efirma" / "SSA980330HU1"
        assert emp["cer_path"] == str(canonico / "fiel.cer")
        # Se COPIÓ, no solo se reapuntó: debe seguir sirviendo desde otro cwd.
        assert (canonico / "fiel.cer").read_bytes() == b"contenido-cer"
        assert (canonico / "fiel.key").read_bytes() == b"contenido-key"

    def test_sin_archivo_igual_queda_absoluta(self, catalogo_aislado, tmp_path, monkeypatch):
        # No hay nada que copiar; aun así se normaliza para que el error nombre
        # una ruta real y la migración no reintente en cada lectura.
        monkeypatch.chdir(tmp_path)
        _escribir_catalogo(
            catalogo_aislado, "efirma/XXX010101XXX/fiel.cer", "efirma/XXX010101XXX/fiel.key",
        )

        emp = config_store.load_empresas()["empresas"]["SSA980330HU1"]
        from pathlib import Path

        assert Path(emp["cer_path"]).is_absolute()
        assert "efirma" in emp["cer_path"]

    def test_persiste_en_disco(self, catalogo_aislado):
        destino = catalogo_aislado / "efirma" / "SSA980330HU1"
        destino.mkdir(parents=True)
        (destino / "fiel.cer").write_bytes(b"cer")
        (destino / "fiel.key").write_bytes(b"key")
        _escribir_catalogo(
            catalogo_aislado,
            "efirma/SSA980330HU1/fiel.cer", "efirma/SSA980330HU1/fiel.key",
        )

        config_store.load_empresas()
        crudo = json.loads((catalogo_aislado / "empresas.json").read_text(encoding="utf-8"))
        assert crudo["empresas"]["SSA980330HU1"]["cer_path"] == str(destino / "fiel.cer")

    def test_no_toca_rutas_absolutas(self, catalogo_aislado):
        abs_cer = str(catalogo_aislado / "otro" / "fiel.cer")
        abs_key = str(catalogo_aislado / "otro" / "fiel.key")
        _escribir_catalogo(catalogo_aislado, abs_cer, abs_key)

        emp = config_store.load_empresas()["empresas"]["SSA980330HU1"]
        assert emp["cer_path"] == abs_cer
        assert emp["key_path"] == abs_key

    def test_empresa_solo_ciec_no_estorba(self, catalogo_aislado):
        (catalogo_aislado / "empresas.json").write_text(
            json.dumps({
                "empresas": {"CACS6008103K4": {"nombre": "X", "metodos": ["ciec"],
                                               "cer_path": None, "key_path": None}},
                "default_rfc": "CACS6008103K4",
            }),
            encoding="utf-8",
        )
        emp = config_store.load_empresas()["empresas"]["CACS6008103K4"]
        assert emp["cer_path"] is None

    def test_es_idempotente(self, catalogo_aislado):
        destino = catalogo_aislado / "efirma" / "SSA980330HU1"
        destino.mkdir(parents=True)
        (destino / "fiel.cer").write_bytes(b"cer")
        (destino / "fiel.key").write_bytes(b"key")
        _escribir_catalogo(
            catalogo_aislado,
            "efirma/SSA980330HU1/fiel.cer", "efirma/SSA980330HU1/fiel.key",
        )

        primera = config_store.load_empresas()
        # Segunda pasada: ya está todo absoluto, no debe reportar cambios.
        assert config_store._migrar_rutas_efirma(primera) is False

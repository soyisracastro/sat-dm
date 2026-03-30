"""Tests para cli.config_store — catálogo de empresas y tracking de solicitudes."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch

from cli import config_store


@pytest.fixture(autouse=True)
def temp_config(tmp_path, monkeypatch):
    """Redirige CONFIG_DIR y EFIRMA_DIR a directorios temporales."""
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")


# ---------------------------------------------------------------------------
# Empresas
# ---------------------------------------------------------------------------

class TestEmpresas:

    def test_list_vacia_inicial(self):
        assert config_store.list_empresas() == []

    def test_add_empresa(self, test_cer, test_key, test_password, test_rfc):
        rfc = config_store.add_empresa("Mi Empresa", test_cer, test_key, test_password)
        assert rfc == test_rfc

    def test_add_copia_archivos(self, test_cer, test_key, test_password, tmp_path):
        rfc = config_store.add_empresa("Test", test_cer, test_key, test_password)
        efirma_dir = tmp_path / "efirma" / rfc
        assert (efirma_dir / "fiel.cer").exists()
        assert (efirma_dir / "fiel.key").exists()
        assert (efirma_dir / "fiel.txt").exists()

    def test_add_guarda_vencimiento(self, test_cer, test_key, test_password):
        config_store.add_empresa("Test", test_cer, test_key, test_password)
        empresas = config_store.list_empresas()
        assert empresas[0]["vencimiento"] != ""

    def test_primera_empresa_es_default(self, test_cer, test_key, test_password, test_rfc):
        config_store.add_empresa("Test", test_cer, test_key, test_password)
        assert config_store.get_default() == test_rfc

    def test_list_retorna_empresa(self, test_cer, test_key, test_password, test_rfc):
        config_store.add_empresa("Mi Empresa", test_cer, test_key, test_password)
        empresas = config_store.list_empresas()
        assert len(empresas) == 1
        assert empresas[0]["rfc"] == test_rfc
        assert empresas[0]["nombre"] == "Mi Empresa"
        assert empresas[0]["default"] is True

    def test_get_empresa(self, test_cer, test_key, test_password, test_rfc):
        config_store.add_empresa("Test", test_cer, test_key, test_password)
        empresa = config_store.get_empresa(test_rfc)
        assert empresa["rfc"] == test_rfc
        assert "cer_path" in empresa
        assert "password" in empresa

    def test_get_empresa_inexistente(self):
        with pytest.raises(KeyError):
            config_store.get_empresa("RFC_QUE_NO_EXISTE")

    def test_remove_empresa(self, test_cer, test_key, test_password, test_rfc):
        config_store.add_empresa("Test", test_cer, test_key, test_password)
        config_store.remove_empresa(test_rfc)
        assert config_store.list_empresas() == []

    def test_remove_default_asigna_otro(self, test_cer, test_key, test_password, test_rfc):
        config_store.add_empresa("Test", test_cer, test_key, test_password)
        config_store.remove_empresa(test_rfc)
        assert config_store.get_default() is None

    def test_set_default(self, test_cer, test_key, test_password, test_rfc):
        config_store.add_empresa("Test", test_cer, test_key, test_password)
        config_store.set_default(test_rfc)
        assert config_store.get_default() == test_rfc

    def test_set_default_inexistente(self):
        with pytest.raises(KeyError):
            config_store.set_default("NO_EXISTE")


# ---------------------------------------------------------------------------
# Solicitudes
# ---------------------------------------------------------------------------

class TestSolicitudes:

    def test_sin_solicitudes(self, test_rfc):
        assert config_store.get_solicitudes_pendientes(test_rfc) == []

    def test_save_solicitud(self, test_rfc):
        config_store.save_solicitud(
            rfc=test_rfc,
            id_solicitud="abc-123",
            fecha_inicio="2025-01-01",
            fecha_fin="2025-12-31",
            tipo="E",
        )
        pendientes = config_store.get_solicitudes_pendientes(test_rfc)
        assert len(pendientes) == 1
        assert pendientes[0]["id_solicitud"] == "abc-123"

    def test_get_solicitud(self, test_rfc):
        config_store.save_solicitud(
            rfc=test_rfc, id_solicitud="xyz-789",
            fecha_inicio="2025-01-01", fecha_fin="2025-06-30", tipo="R",
        )
        sol = config_store.get_solicitud(test_rfc, "xyz-789")
        assert sol is not None
        assert sol["tipo"] == "R"

    def test_get_solicitud_inexistente(self, test_rfc):
        assert config_store.get_solicitud(test_rfc, "no-existe") is None

    def test_update_solicitud(self, test_rfc):
        config_store.save_solicitud(
            rfc=test_rfc, id_solicitud="upd-001",
            fecha_inicio="2025-01-01", fecha_fin="2025-12-31", tipo="E",
        )
        config_store.update_solicitud(test_rfc, "upd-001", "terminada", ["pkg1", "pkg2"])
        sol = config_store.get_solicitud(test_rfc, "upd-001")
        assert sol["estado"] == "terminada"
        assert sol["package_ids"] == ["pkg1", "pkg2"]

    def test_pendientes_excluye_terminadas(self, test_rfc):
        config_store.save_solicitud(
            rfc=test_rfc, id_solicitud="s1",
            fecha_inicio="2025-01-01", fecha_fin="2025-12-31", tipo="E",
        )
        config_store.save_solicitud(
            rfc=test_rfc, id_solicitud="s2",
            fecha_inicio="2025-01-01", fecha_fin="2025-12-31", tipo="R",
        )
        config_store.update_solicitud(test_rfc, "s1", "terminada")
        pendientes = config_store.get_solicitudes_pendientes(test_rfc)
        assert len(pendientes) == 1
        assert pendientes[0]["id_solicitud"] == "s2"

"""Sync de catálogo de empresas (F5): stamping, push shape y merge LWW."""

import pytest

from sat_descarga.cli import config_store


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")
    monkeypatch.setattr(config_store, "EFIRMA_DIR", tmp_path / "efirma")
    monkeypatch.setattr(
        config_store, "descargas_dir_default", lambda: str(tmp_path / "TodoConta")
    )


def test_mutadores_estampan_updated_at():
    config_store.add_empresa_ciec("XAXX010101000", "Prueba SA", "ciec123")
    e = config_store.load_empresas()["empresas"]["XAXX010101000"]
    assert e.get("updated_at"), "add_empresa_ciec debe estampar updated_at"
    t1 = e["updated_at"]

    config_store.archive_empresa("XAXX010101000")
    e = config_store.load_empresas()["empresas"]["XAXX010101000"]
    assert e["updated_at"] >= t1 and e["archived_at"]


def test_catalogo_para_sync_shape_y_union_de_metodos():
    config_store.add_empresa_ciec("XAXX010101000", "Prueba SA", "ciec123")
    # Simula que la otra instalación reportó fiel (metodos_sync).
    with config_store._catalogo_lock:
        data = config_store.load_empresas()
        data["empresas"]["XAXX010101000"]["metodos_sync"] = ["fiel"]
        config_store.save_empresas(data)

    cat = config_store.catalogo_para_sync()
    assert len(cat) == 1
    fila = cat[0]
    assert fila["rfc"] == "XAXX010101000"
    # Unión local+remoto: informativo, no pisa lo que reportó el otro lado.
    assert fila["metodos"] == ["ciec", "fiel"]
    assert fila["updated_at"]
    # Las credenciales JAMÁS viajan.
    assert "cer_path" not in fila and "key_path" not in fila


def test_catalogo_para_sync_estampa_legacy_una_vez():
    # Empresa previa al sync (sin updated_at) se estampa al primer push.
    with config_store._catalogo_lock:
        data = config_store.load_empresas()
        data["empresas"]["ABC010101AAA"] = {"nombre": "Legacy", "metodos": ["ciec"]}
        config_store.save_empresas(data)
    cat = config_store.catalogo_para_sync()
    assert cat[0]["updated_at"]
    e = config_store.load_empresas()["empresas"]["ABC010101AAA"]
    assert e.get("updated_at")


class TestAplicarSyncRemoto:
    def _remota(self, **extra):
        base = {
            "rfc": "NUE010101AAA",
            "nombre": "Nueva Desde Nube",
            "metodos": ["fiel"],
            "vencimiento": "2027-01-01",
            "archived_at": None,
            "csf_descargada_en": "2026-07-01T12:00:00+00:00",
            "opinion_descargada_en": None,
            "updated_at": "2026-07-10T12:00:00+00:00",
        }
        base.update(extra)
        return base

    def test_importa_empresa_nueva_sin_credenciales(self):
        n = config_store.aplicar_sync_remoto([self._remota()])
        assert n == 1
        e = config_store.load_empresas()["empresas"]["NUE010101AAA"]
        assert e["nombre"] == "Nueva Desde Nube"
        assert e["metodos"] == []           # sin credenciales locales
        assert e["metodos_sync"] == ["fiel"]  # badge "requiere credenciales aquí"
        assert e["vencimiento"] == "2027-01-01"
        assert e["csf_descargada_en"] == "2026-07-01T12:00:00+00:00"
        assert "cer_path" not in e

        # Y aparece en list_empresas con los campos del badge.
        fila = next(x for x in config_store.list_empresas() if x["rfc"] == "NUE010101AAA")
        assert fila["metodos"] == [] and fila["metodos_sync"] == ["fiel"]

    def test_lww_no_pisa_local_mas_nuevo(self):
        config_store.add_empresa_ciec("NUE010101AAA", "Nombre Local Reciente", "c")
        # La fila remota es más vieja que el alta local de recién.
        n = config_store.aplicar_sync_remoto([self._remota()])
        assert n == 0
        e = config_store.load_empresas()["empresas"]["NUE010101AAA"]
        assert e["nombre"] == "Nombre Local Reciente"
        assert e["metodos"] == ["ciec"]

    def test_remoto_mas_nuevo_actualiza_sin_tocar_credenciales(self):
        config_store.add_empresa_ciec("NUE010101AAA", "Vieja", "c")
        n = config_store.aplicar_sync_remoto(
            [self._remota(nombre="Renombrada", updated_at="2099-01-01T00:00:00+00:00")]
        )
        assert n == 1
        e = config_store.load_empresas()["empresas"]["NUE010101AAA"]
        assert e["nombre"] == "Renombrada"
        assert e["metodos"] == ["ciec"]       # los métodos LOCALES no se tocan
        assert e["metodos_sync"] == ["fiel"]

    def test_vencimiento_no_pisa_cert_local(self):
        # Empresa con e.firma local (cer_path presente): el vencimiento remoto
        # no debe pisar el del certificado real.
        with config_store._catalogo_lock:
            data = config_store.load_empresas()
            data["empresas"]["NUE010101AAA"] = {
                "nombre": "Con FIEL",
                "metodos": ["fiel"],
                "cer_path": "/x/fiel.cer",
                "vencimiento": "2026-12-31",
                "updated_at": "2020-01-01T00:00:00+00:00",
            }
            config_store.save_empresas(data)
        config_store.aplicar_sync_remoto(
            [self._remota(updated_at="2099-01-01T00:00:00+00:00")]
        )
        e = config_store.load_empresas()["empresas"]["NUE010101AAA"]
        assert e["vencimiento"] == "2026-12-31"

    def test_tracking_documentos_solo_hacia_adelante(self):
        with config_store._catalogo_lock:
            data = config_store.load_empresas()
            data["empresas"]["NUE010101AAA"] = {
                "nombre": "X",
                "metodos": [],
                "csf_descargada_en": "2026-07-05T00:00:00+00:00",
                "updated_at": "2020-01-01T00:00:00+00:00",
            }
            config_store.save_empresas(data)
        # Fila remota más nueva pero con CSF más VIEJA: no debe retroceder.
        config_store.aplicar_sync_remoto(
            [self._remota(updated_at="2099-01-01T00:00:00+00:00")]
        )
        e = config_store.load_empresas()["empresas"]["NUE010101AAA"]
        assert e["csf_descargada_en"] == "2026-07-05T00:00:00+00:00"

    def test_importa_metadata_fiscal_parseada(self):
        regimenes = [{"clave": "601", "descripcion": "General de Ley PM"}]
        actividades = [{"descripcion": "Gasolina", "principal": True, "porcentaje": 99}]
        motivos = [{"titulo": "Créditos fiscales", "descripcion": "…", "detalles": ["123"]}]
        config_store.aplicar_sync_remoto([self._remota(
            regimenes_fiscales=regimenes,
            actividades_economicas=actividades,
            presenta_diot=True,
            opinion_status="negativa",
            opinion_motivos=motivos,
        )])
        e = config_store.get_empresa("NUE010101AAA")
        assert e["regimenes_fiscales"] == regimenes
        assert e["actividades_economicas"] == actividades
        assert e["presenta_diot"] is True
        assert e["opinion_status"] == "negativa"
        assert e["opinion_motivos"] == motivos

    def test_fila_remota_mas_nueva_no_borra_metadata_local(self):
        # Guarda anti-wipe: una descarga de opinión (fila remota más nueva, pero
        # SIN régimen) no debe borrar el régimen que este lado sí parseó.
        with config_store._catalogo_lock:
            data = config_store.load_empresas()
            data["empresas"]["NUE010101AAA"] = {
                "nombre": "X", "metodos": [],
                "regimenes_fiscales": [{"clave": "626", "descripcion": "RESICO"}],
                "updated_at": "2020-01-01T00:00:00+00:00",
            }
            config_store.save_empresas(data)
        config_store.aplicar_sync_remoto([self._remota(
            updated_at="2099-01-01T00:00:00+00:00",
            regimenes_fiscales=[],  # la fila nueva no trae régimen
            opinion_status="positiva",
        )])
        e = config_store.get_empresa("NUE010101AAA")
        assert e["regimenes_fiscales"] == [{"clave": "626", "descripcion": "RESICO"}]
        assert e["opinion_status"] == "positiva"  # sí aplica lo que sí viene

    def test_push_incluye_metadata_fiscal(self):
        config_store.add_empresa_ciec("XAXX010101000", "Prueba", "ciec")
        config_store.update_empresa("XAXX010101000", {
            "regimenes_fiscales": [{"clave": "626", "descripcion": "RESICO"}],
        })
        fila = next(f for f in config_store.catalogo_para_sync()
                    if f["rfc"] == "XAXX010101000")
        assert fila["regimenes_fiscales"] == [{"clave": "626", "descripcion": "RESICO"}]
        assert "opinion_status" in fila and "presenta_diot" in fila


def test_sincronizar_catalogo_sin_sesion_no_hace_nada(monkeypatch, tmp_path):
    from sat_descarga.api import license_client as lc
    from sat_descarga.api import sync_empresas

    monkeypatch.setattr(lc, "LICENSE_CACHE_PATH", tmp_path / "license-cache.json")
    assert sync_empresas.sincronizar_catalogo() is None

"""Sync de tareas: stamping, tombstones, push shape y merge LWW."""

import pytest

from sat_descarga.cli import config_store
from sat_descarga.tareas import store


@pytest.fixture(autouse=True)
def aislar(tmp_path, monkeypatch):
    monkeypatch.setattr(config_store, "CONFIG_DIR", tmp_path / ".sat-descarga")


def test_mutadores_estampan_updated_at():
    t = store.crear("Presentar DIOT de junio")
    assert t["updated_at"], "crear debe estampar updated_at"

    editada = store.actualizar(t["id"], {"estado": "curso"})
    assert editada["updated_at"] >= t["updated_at"]


def test_eliminar_deja_tombstone_oculto():
    t = store.crear("Borrarme")
    assert store.eliminar(t["id"]) is True
    assert store.eliminar(t["id"]) is False           # ya no está viva
    assert store.listar()["tareas"] == []             # oculta en la UI
    assert store.actualizar(t["id"], {"estado": "hecho"}) is None  # PATCH → 404

    # Pero el tombstone SÍ viaja en el sync (con eliminada_en y updated_at).
    fila = next(f for f in store.tareas_para_sync()["tareas"] if f["id"] == t["id"])
    assert fila["eliminada_en"] and fila["updated_at"]


def test_para_sync_shape_y_backfill_legacy():
    t = store.crear("Legacy")
    # Simula una tarea previa al sync (sin updated_at).
    with store._tareas_lock:
        data = store._load()
        data["tareas"][0].pop("updated_at")
        store._write_json_atomico(store._path(), data)

    filas = store.tareas_para_sync()["tareas"]
    assert filas[0]["id"] == t["id"]
    # Backfill una sola vez, desde actualizado_en, y queda persistido.
    assert filas[0]["updated_at"] == t["actualizado_en"]
    assert store._load()["tareas"][0]["updated_at"]
    # El vínculo con Google Calendar es local: no viaja.
    assert "gcal_event_id" not in filas[0]


class TestAplicarSyncRemoto:
    def _remota(self, **extra):
        base = {
            "id": "abc123abc123",
            "titulo": "Desde la nube",
            "rfc": None,
            "tipo": "manual",
            "estado": "pendiente",
            "prioridad": "media",
            "fecha": None,
            "origen": "manual",
            "sugerencia_id": None,
            "creado_en": "2026-07-10T09:00:00",
            "actualizado_en": "2026-07-10T09:00:00",
            "completado_en": None,
            "eliminada_en": None,
            "updated_at": "2026-07-10T12:00:00+00:00",
        }
        base.update(extra)
        return base

    def test_importa_tarea_nueva(self):
        n = store.aplicar_sync_remoto([self._remota()], [])
        assert n == 1
        tareas = store.listar()["tareas"]
        assert len(tareas) == 1
        assert tareas[0]["titulo"] == "Desde la nube"
        assert tareas[0]["gcal_event_id"] is None

    def test_lww_no_pisa_local_mas_nuevo(self):
        t = store.crear("Local reciente")
        n = store.aplicar_sync_remoto(
            [self._remota(id=t["id"], titulo="Vieja de la nube")], []
        )
        assert n == 0
        assert store.listar()["tareas"][0]["titulo"] == "Local reciente"

    def test_tombstone_remoto_borra_local(self):
        t = store.crear("Se borró en la otra instalación")
        n = store.aplicar_sync_remoto([self._remota(
            id=t["id"],
            eliminada_en="2099-01-01T00:00:00",
            updated_at="2099-01-01T00:00:00+00:00",
        )], [])
        assert n == 1
        assert store.listar()["tareas"] == []

    def test_remoto_mas_nuevo_preserva_gcal_event_id(self):
        t = store.crear("Con vínculo GCal")
        with store._tareas_lock:
            data = store._load()
            data["tareas"][0]["gcal_event_id"] = "evt-123"
            store._write_json_atomico(store._path(), data)

        store.aplicar_sync_remoto([self._remota(
            id=t["id"],
            titulo="Renombrada allá",
            updated_at="2099-01-01T00:00:00+00:00",
        )], [])
        tarea = store.listar()["tareas"][0]
        assert tarea["titulo"] == "Renombrada allá"
        assert tarea["gcal_event_id"] == "evt-123"

    def test_orden_estable_mas_reciente_primero(self):
        store.crear("Local de hoy")
        store.aplicar_sync_remoto([self._remota(creado_en="2020-01-01T00:00:00")], [])
        titulos = [t["titulo"] for t in store.listar()["tareas"]]
        assert titulos == ["Local de hoy", "Desde la nube"]

    def test_descartes_se_unen_sin_duplicar(self):
        store.descartar_sugerencia("diot-2026-06")
        store.aplicar_sync_remoto([], ["diot-2026-06", "efirma-XAXX-2026-08"])
        assert store.listar()["sugerencias_descartadas"] == [
            "diot-2026-06", "efirma-XAXX-2026-08",
        ]

    def test_fila_invalida_se_ignora(self):
        n = store.aplicar_sync_remoto(
            [None, {}, {"id": "x1y2z3"}, self._remota(updated_at="no-es-fecha")], []
        )
        assert n == 0
        assert store.listar()["tareas"] == []


def test_sincronizar_tareas_sin_sesion_no_hace_nada(monkeypatch, tmp_path):
    from sat_descarga.api import license_client as lc
    from sat_descarga.api import sync_tareas

    monkeypatch.setattr(lc, "LICENSE_CACHE_PATH", tmp_path / "license-cache.json")
    assert sync_tareas.sincronizar_tareas() is None

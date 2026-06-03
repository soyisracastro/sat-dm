"""Tests para sat_descarga/utils/listas_negras.py + persistencia en procesador.

El endpoint Next se mockea siempre; estos tests no pegan a red.
"""

from __future__ import annotations

import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from sat_descarga.utils.listas_negras import (
    MatchListaNegra,
    ListasMetadata,
    _normalizar_rfcs,
    _parse_match,
    clasificar,
    consultar_rfcs,
    consultar_metadata,
    detectar_edos,
    match_to_json_dict,
)
from sat_descarga.api import license_client
from sat_descarga.api.license_client import Session


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sesion_activa():
    """Guarda una sesión Bearer fake en el keyring de memoria."""
    license_client.save_session(Session(
        access_token="fake-bearer-token",
        refresh_token="fake-refresh",
        user_id="user-1",
        email="test@todoconta.com",
    ))
    yield
    license_client.clear_session()


def _mock_response(status: int, payload: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = payload or {}
    resp.text = json.dumps(payload or {})
    return resp


def _payload_listas(
    rfc: str,
    en_69b: bool = False,
    situacion_69b: str | None = None,
    supuestos_69: list[str] | None = None,
    risk: str = "limpio",
) -> dict:
    return {
        "rfc": rfc,
        "lista_69b": (
            [{"rfc": rfc, "nombre": "Test SA", "situacion": situacion_69b,
              "fecha_publicacion": "2025-01-15"}]
            if en_69b else []
        ),
        "lista_69": (
            [{"rfc": rfc, "supuesto": s, "fecha_primera_publicacion": "2024-06-01",
              "entidad_federativa": "CDMX", "tipo_persona": "M", "monto": None}
             for s in supuestos_69]
            if supuestos_69 else []
        ),
        "risk_level": risk,
    }


def _meta_default() -> dict:
    return {
        "lista_69b_updated_at": "2026-06-05T06:00:00Z",
        "lista_69_updated_at": "2026-06-05T06:45:00Z",
        "record_count_69b": 14000,
        "record_count_69": 486000,
    }


# ---------------------------------------------------------------------------
# Normalización
# ---------------------------------------------------------------------------


class TestNormalizarRfcs:
    def test_uppercase_y_trim(self):
        assert _normalizar_rfcs(["  abc010101aaa "]) == ["ABC010101AAA"]

    def test_deduplica_preservando_orden(self):
        result = _normalizar_rfcs(["AAA", "BBB", "aaa", "  bbb  ", "CCC"])
        assert result == ["AAA", "BBB", "CCC"]

    def test_descarta_vacios(self):
        assert _normalizar_rfcs(["", None, "   ", "XAXX"]) == ["XAXX"]


# ---------------------------------------------------------------------------
# Parser de respuesta
# ---------------------------------------------------------------------------


class TestParseMatch:
    def test_efos_definitivo(self):
        m = _parse_match("EFOS010101AAA", _payload_listas(
            "EFOS010101AAA", en_69b=True, situacion_69b="Definitivo", risk="alto",
        ))
        assert m.en_lista_69b is True
        assert m.situacion_69b == "Definitivo"
        assert m.es_efos is True
        assert m.risk_level == "alto"

    def test_presunto(self):
        m = _parse_match("PRES010101AAA", _payload_listas(
            "PRES010101AAA", en_69b=True, situacion_69b="Presunto", risk="alto",
        ))
        assert m.es_efos is True

    def test_aclarado_no_es_efos(self):
        m = _parse_match("ACLA010101AAA", _payload_listas(
            "ACLA010101AAA", en_69b=True, situacion_69b="Desvirtuado", risk="medio",
        ))
        assert m.en_lista_69b is True
        assert m.es_efos is False
        assert m.risk_level == "medio"

    def test_limpio(self):
        m = _parse_match("LIMP010101AAA", _payload_listas("LIMP010101AAA"))
        assert m.en_lista_69b is False
        assert m.en_lista_69 is False
        assert m.es_efos is False

    def test_supuestos_69_deduplica(self):
        # El endpoint puede devolver el mismo supuesto N veces (varios créditos firmes).
        payload = _payload_listas("X", supuestos_69=["firmes", "firmes", "exigibles"])
        m = _parse_match("X", payload)
        assert m.supuestos_69 == ["firmes", "exigibles"]


# ---------------------------------------------------------------------------
# Clasificación
# ---------------------------------------------------------------------------


class TestClasificar:
    def _mk(self, **kw) -> MatchListaNegra:
        defaults = dict(
            rfc="X", en_lista_69b=False, situacion_69b=None,
            fecha_publicacion_69b=None, en_lista_69=False, supuestos_69=[],
            risk_level="limpio",
        )
        defaults.update(kw)
        return MatchListaNegra(**defaults)

    def test_efos_definitivo(self):
        m = self._mk(en_lista_69b=True, situacion_69b="Definitivo")
        assert clasificar(m) == "EFOS"

    def test_efos_presunto(self):
        m = self._mk(en_lista_69b=True, situacion_69b="Presunto")
        assert clasificar(m) == "EFOS"

    def test_aclarado(self):
        m = self._mk(en_lista_69b=True, situacion_69b="Desvirtuado")
        assert clasificar(m) == "Aclarado"

    def test_sentencia_favorable(self):
        m = self._mk(en_lista_69b=True, situacion_69b="Sentencia Favorable")
        assert clasificar(m) == "Aclarado"

    def test_solo_69(self):
        m = self._mk(en_lista_69=True, supuestos_69=["firmes"])
        assert clasificar(m) == "69"

    def test_limpio(self):
        assert clasificar(self._mk()) == "Limpio"


# ---------------------------------------------------------------------------
# Cliente HTTP
# ---------------------------------------------------------------------------


class TestConsultarRfcs:
    def test_sin_sesion_lanza_runtime_error(self):
        # No se inicia sesion_activa → el keyring está vacío
        with pytest.raises(RuntimeError, match="(?i)sesi[óo]n"):
            consultar_rfcs(["XAXX010101000"])

    def test_lista_vacia_retorna_vacio(self, sesion_activa):
        matches, meta = consultar_rfcs([])
        assert matches == []
        assert meta.lista_69b_updated_at is None

    @patch("sat_descarga.utils.listas_negras.requests.post")
    def test_caso_feliz(self, mock_post, sesion_activa):
        mock_post.return_value = _mock_response(200, {
            "results": {
                "EFOS010101AAA": _payload_listas(
                    "EFOS010101AAA", en_69b=True,
                    situacion_69b="Definitivo", risk="alto",
                ),
                "LIMP010101BBB": _payload_listas("LIMP010101BBB"),
            },
            "metadata": _meta_default(),
        })
        matches, meta = consultar_rfcs(["EFOS010101AAA", "limp010101bbb"])
        assert len(matches) == 2
        assert matches[0].rfc == "EFOS010101AAA"
        assert matches[0].es_efos is True
        assert matches[1].rfc == "LIMP010101BBB"  # upcased
        assert matches[1].en_lista_69b is False
        assert meta.lista_69b_updated_at == "2026-06-05T06:00:00Z"

    @patch("sat_descarga.utils.listas_negras.requests.post")
    def test_rfc_no_devuelto_se_marca_limpio(self, mock_post, sesion_activa):
        # El endpoint solo devuelve los RFCs que matchearon — los limpios los
        # omite. El cliente debe rellenar con limpios.
        mock_post.return_value = _mock_response(200, {
            "results": {}, "metadata": _meta_default(),
        })
        matches, _ = consultar_rfcs(["AAA010101AAA", "BBB020202BBB"])
        assert len(matches) == 2
        assert all(m.en_lista_69b is False and m.en_lista_69 is False for m in matches)
        assert all(m.risk_level == "limpio" for m in matches)

    @patch("sat_descarga.utils.listas_negras.requests.post")
    def test_loteo_mayor_a_200(self, mock_post, sesion_activa):
        mock_post.return_value = _mock_response(200, {
            "results": {}, "metadata": _meta_default(),
        })
        rfcs = [f"RFC{i:09d}" for i in range(450)]
        consultar_rfcs(rfcs)
        # 450 → ceil(450/200) = 3 calls
        assert mock_post.call_count == 3
        # Tamaño del primer lote
        primer_call = mock_post.call_args_list[0]
        assert len(primer_call.kwargs["json"]["rfcs"]) == 200
        # Tamaño del último lote
        ultimo_call = mock_post.call_args_list[-1]
        assert len(ultimo_call.kwargs["json"]["rfcs"]) == 50

    @patch("sat_descarga.utils.listas_negras.requests.post")
    def test_401_limpia_sesion_y_lanza(self, mock_post, sesion_activa):
        mock_post.return_value = _mock_response(401, {"error": "expired"})
        with pytest.raises(RuntimeError, match="(?i)sesi[óo]n"):
            consultar_rfcs(["XAXX010101000"])
        # La sesión debe estar limpia tras el 401
        assert license_client.load_session() is None

    @patch("sat_descarga.utils.listas_negras.requests.post")
    def test_500_lanza_runtime(self, mock_post, sesion_activa):
        mock_post.return_value = _mock_response(500, {"error": "internal"})
        with pytest.raises(RuntimeError, match="500"):
            consultar_rfcs(["XAXX010101000"])

    @patch("sat_descarga.utils.listas_negras.requests.post")
    def test_bearer_va_en_header(self, mock_post, sesion_activa):
        mock_post.return_value = _mock_response(200, {
            "results": {}, "metadata": _meta_default(),
        })
        consultar_rfcs(["XAXX010101000"])
        headers = mock_post.call_args.kwargs["headers"]
        assert headers["Authorization"] == "Bearer fake-bearer-token"


# ---------------------------------------------------------------------------
# Detección de EDOS
# ---------------------------------------------------------------------------


class TestDetectarEdos:
    @patch("sat_descarga.utils.listas_negras.requests.post")
    def test_solo_emisores_efos_se_cuentan(self, mock_post, sesion_activa):
        mock_post.return_value = _mock_response(200, {
            "results": {
                "EFOS010101AAA": _payload_listas(
                    "EFOS010101AAA", en_69b=True, situacion_69b="Definitivo",
                ),
                "ACLA010101BBB": _payload_listas(
                    "ACLA010101BBB", en_69b=True, situacion_69b="Desvirtuado",
                ),
            },
            "metadata": _meta_default(),
        })
        cfdis = [
            ("uuid-1", "EFOS010101AAA"),   # EDOS
            ("uuid-2", "ACLA010101BBB"),   # no es EDOS (aclarado)
            ("uuid-3", "LIMP010101CCC"),   # limpio
            ("uuid-4", "EFOS010101AAA"),   # EDOS (segundo CFDI del mismo emisor)
        ]
        edos, _ = detectar_edos(cfdis)
        assert len(edos) == 2
        assert {e.cfdi_uuid for e in edos} == {"uuid-1", "uuid-4"}
        assert all(e.emisor_rfc == "EFOS010101AAA" for e in edos)


# ---------------------------------------------------------------------------
# Persistencia en procesador
# ---------------------------------------------------------------------------


@pytest.fixture
def db_con_cfdis(tmp_path):
    """ProcesadorDB temporal con 3 CFDIs precargados."""
    from sat_descarga.procesador.db import ProcesadorDB
    db = ProcesadorDB(tmp_path / "test.db")

    # Insert directo (saltamos el parser para simplificar el setup).
    with db._conn:
        db._conn.executemany(
            "INSERT INTO cfdis (uuid, emisor_rfc, receptor_rfc, total, fecha, cargado_en) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [
                ("uuid-1", "EFOS010101AAA", "MIRFC010101XYZ", 1000.0, "2026-05-01T10:00:00", "2026-05-01T10:00:00"),
                ("uuid-2", "EFOS010101AAA", "MIRFC010101XYZ", 500.0, "2026-05-15T10:00:00", "2026-05-15T10:00:00"),
                ("uuid-3", "LIMP010101CCC", "MIRFC010101XYZ", 2000.0, "2026-06-01T10:00:00", "2026-06-01T10:00:00"),
            ],
        )
    return db


class TestPersistencia:
    def test_actualizar_lista_negra_emisor_y_receptor(self, db_con_cfdis):
        db = db_con_cfdis
        # MIRFC010101XYZ es receptor de los 3 CFDIs
        n = db.actualizar_lista_negra_rfc("MIRFC010101XYZ", "Limpio", "{}")
        # 0 filas en emisor (no aparece como emisor) + 3 en receptor = 3
        assert n == 3

        cur = db._conn.execute(
            "SELECT COUNT(*) FROM cfdis WHERE receptor_en_lista_negra = 'Limpio'"
        )
        assert cur.fetchone()[0] == 3

    def test_actualizar_marca_efos_emisor(self, db_con_cfdis):
        db = db_con_cfdis
        match_json = json.dumps({
            "situacion_69b": "Definitivo",
            "supuestos_69": [],
        })
        n = db.actualizar_lista_negra_rfc("EFOS010101AAA", "EFOS", match_json)
        # 2 filas en emisor + 0 en receptor = 2
        assert n == 2

        cur = db._conn.execute(
            "SELECT emisor_en_lista_negra, emisor_listas_match "
            "FROM cfdis WHERE uuid = 'uuid-1'"
        )
        etiqueta, match = cur.fetchone()
        assert etiqueta == "EFOS"
        assert json.loads(match)["situacion_69b"] == "Definitivo"

    def test_rfcs_sin_validar_devuelve_unicos(self, db_con_cfdis):
        db = db_con_cfdis
        rfcs = set(db.rfcs_sin_validar_listas())
        assert rfcs == {"EFOS010101AAA", "LIMP010101CCC", "MIRFC010101XYZ"}

    def test_ttl_omite_recientes(self, db_con_cfdis):
        db = db_con_cfdis
        # Marca el emisor EFOS como validado AHORA
        db.actualizar_lista_negra_rfc("EFOS010101AAA", "EFOS", "{}")
        rfcs = set(db.rfcs_sin_validar_listas(ttl_days=30))
        # EFOS010101AAA tiene timestamp fresh → no debe estar
        assert "EFOS010101AAA" not in rfcs
        # MIRFC tampoco, porque actualizar_lista_negra_rfc también tocó las
        # filas donde aparece como receptor de uuid-1 y uuid-2 (mismos RFCs
        # EFOS010101AAA actualizados). Pero uuid-3 quedó sin validar — MIRFC
        # sigue en la lista de pendientes.
        assert "MIRFC010101XYZ" in rfcs
        assert "LIMP010101CCC" in rfcs

    def test_force_refresh_devuelve_todos(self, db_con_cfdis):
        db = db_con_cfdis
        db.actualizar_lista_negra_rfc("EFOS010101AAA", "EFOS", "{}")
        rfcs = set(db.rfcs_sin_validar_listas(force_refresh=True))
        assert rfcs == {"EFOS010101AAA", "LIMP010101CCC", "MIRFC010101XYZ"}

    def test_stats_listas_negras(self, db_con_cfdis):
        db = db_con_cfdis
        db.actualizar_lista_negra_rfc("EFOS010101AAA", "EFOS", "{}")
        db.actualizar_lista_negra_rfc("LIMP010101CCC", "Limpio", "{}")
        db.actualizar_lista_negra_rfc("MIRFC010101XYZ", "Limpio", "{}")

        stats = db.stats_listas_negras({})
        assert stats["cfdis_edos"] == 2     # uuid-1 + uuid-2
        assert stats["efos_emisores_unicos"] == 1
        assert stats["cfdis_sin_validar"] == 0
        # uuid-3 tiene emisor Limpio y receptor Limpio
        assert stats["cfdis_limpios"] == 1


# ---------------------------------------------------------------------------
# Serialización (match_to_json_dict)
# ---------------------------------------------------------------------------


def test_match_to_json_dict_minimal():
    m = MatchListaNegra(
        rfc="X", en_lista_69b=True, situacion_69b="Definitivo",
        fecha_publicacion_69b="2025-01-15", en_lista_69=False,
        supuestos_69=[], risk_level="alto",
    )
    d = match_to_json_dict(m)
    assert d == {
        "situacion_69b": "Definitivo",
        "fecha_publicacion_69b": "2025-01-15",
        "supuestos_69": [],
        "risk_level": "alto",
    }

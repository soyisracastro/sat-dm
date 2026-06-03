"""
Capa de persistencia del procesador con SQLite.

Mantiene un único `~/.sat-descarga/procesador.db` compartido por los tres
procesadores futuros (CFDI, Pagos, Nómina). Este PR introduce las tablas
`cfdis`, `conceptos`, `filtros` y `_meta`. PRs siguientes agregarán
`pagos_relaciones` y `nomina_conceptos` con migraciones versionadas.

Decisión arquitectónica (ver plan): SQLite desde el inicio en lugar de JSON,
porque los filtros + agregaciones + persistencia mediante queries son ordenes
de magnitud más rápidos y simples que iterar listas en Python.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Optional

from ..cli import config_store
from .cfdi_parser import CfdiData, ConceptoCfdi, DatosNomina

logger = logging.getLogger(__name__)


# Directorio con las migraciones SQL (NNN_descripcion.sql). La versión actual
# es la del archivo con número más alto.
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

DEFAULT_DB_PATH = config_store.CONFIG_DIR / "procesador.db"


# ---------------------------------------------------------------------------
# Migraciones
# ---------------------------------------------------------------------------

_MIGRATION_RE = re.compile(r"^(\d{3})_.*\.sql$")


def _listar_migraciones() -> list[tuple[int, Path]]:
    """Devuelve `[(version, path), ...]` ordenado ascendente."""
    if not MIGRATIONS_DIR.exists():
        return []
    out: list[tuple[int, Path]] = []
    for p in MIGRATIONS_DIR.iterdir():
        m = _MIGRATION_RE.match(p.name)
        if m:
            out.append((int(m.group(1)), p))
    out.sort(key=lambda t: t[0])
    return out


def schema_version_actual() -> int:
    """Versión target (la del archivo con número más alto)."""
    migraciones = _listar_migraciones()
    return migraciones[-1][0] if migraciones else 0


# ---------------------------------------------------------------------------
# Filtros (estructura compartida con la UI)
# ---------------------------------------------------------------------------


CfdiFiltros = dict  # alias documental: {desde, hasta, tipo, busqueda, ...}


def filtros_vacios() -> CfdiFiltros:
    return {
        "desde": None,
        "hasta": None,
        "tipo": None,           # 'I' | 'P' | 'E' | 'T' | 'N' o None
        "direccion": None,      # 'E' (emitidos) | 'R' (recibidos) o None
        "busqueda": None,
        "solo_con_errores": False,
        "monto_min": None,
        "monto_max": None,
    }


# ---------------------------------------------------------------------------
# Conexión
# ---------------------------------------------------------------------------


class ProcesadorDB:
    """
    Wrapper sobre `sqlite3.Connection` con métodos de alto nivel.

    Una sola instancia por proceso (singleton resuelto vía `abrir_db()`).
    El lock interno protege escrituras concurrentes desde threads del worker
    FastAPI.
    """

    def __init__(self, db_path: Path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(
            str(self.path),
            check_same_thread=False,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._lock = threading.RLock()
        self._inicializar_schema()

    # ------------------------------------------------------------------
    # Bootstrap
    # ------------------------------------------------------------------

    def _inicializar_schema(self) -> None:
        """
        Aplica las migraciones pendientes desde `migrations/`.

        - Crea la tabla `_meta` si no existe (la migración `001_init` la
          define, pero la leemos antes para saber qué aplicar).
        - Lee la versión actual (0 si la DB es nueva).
        - Aplica las migraciones con `version > actual` en orden, cada una en
          su propia transacción atómica, actualizando `schema_version` al
          final.
        """
        with self._lock, self._conn:
            # `_meta` siempre existe tras la primera migración. Si la DB es
            # nueva, la tabla no existe — la primera migración la creará.
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS _meta (key TEXT PRIMARY KEY, value TEXT)"
            )
            cur = self._conn.execute(
                "SELECT value FROM _meta WHERE key = 'schema_version'"
            )
            row = cur.fetchone()
            version_actual = int(row[0]) if row else 0

        migraciones = _listar_migraciones()
        target = migraciones[-1][0] if migraciones else 0

        if version_actual > target:
            raise RuntimeError(
                f"DB del procesador tiene versión {version_actual}, "
                f"superior a la última migración disponible ({target}). "
                "Actualiza el agente."
            )

        pendientes = [(v, p) for (v, p) in migraciones if v > version_actual]
        if not pendientes:
            return

        for version, path in pendientes:
            logger.info("[procesador] aplicando migración %s", path.name)
            sql = path.read_text(encoding="utf-8")
            with self._lock, self._conn:
                self._conn.executescript(sql)
                self._conn.execute(
                    """
                    INSERT INTO _meta (key, value) VALUES ('schema_version', ?)
                    ON CONFLICT(key) DO UPDATE SET value = excluded.value
                    """,
                    (str(version),),
                )
            # Hooks post-migración con código Python (cuando el SQL puro no
            # alcanza para la transformación).
            if version == 4:
                self._repoblar_pagos_relaciones()
            if version == 5:
                self._repoblar_nomina()

    def _repoblar_pagos_relaciones(self) -> None:
        """
        Tras la migración 004, lee los CFDIs tipo P existentes (con `datos_pago`
        en `raw_json`) e inserta sus `DoctoRelacionado` en la nueva tabla
        `pagos_relaciones`. Idempotente: usa INSERT OR IGNORE indirecto al
        verificar duplicados por (cfdi_pago_uuid, docto_uuid, docto_num_parcialidad).
        """
        with self._lock, self._conn:
            cur = self._conn.execute(
                "SELECT uuid, raw_json FROM cfdis WHERE tipo = 'P'"
            )
            filas_p = cur.fetchall()

            insertadas = 0
            for row in filas_p:
                uuid_p = row["uuid"]
                try:
                    raw = json.loads(row["raw_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue
                dp = raw.get("datos_pago")
                if not dp:
                    continue

                # ¿Ya hay relaciones para este CFDI? Si sí, lo saltamos.
                check = self._conn.execute(
                    "SELECT 1 FROM pagos_relaciones WHERE cfdi_pago_uuid = ? LIMIT 1",
                    (uuid_p,),
                )
                if check.fetchone():
                    continue

                count = self._insertar_pagos_relaciones(uuid_p, dp)
                insertadas += count

            if insertadas:
                logger.info(
                    "[procesador] migración 004: %d relaciones repobladas desde raw_json",
                    insertadas,
                )

    def _repoblar_nomina(self) -> None:
        """
        Tras la migración 005, lee los CFDIs tipo N existentes (con `datos_nomina`
        en `raw_json`) e inserta sus filas en `nomina_recibos` y `nomina_conceptos`.
        Idempotente: salta CFDIs que ya tengan recibo en la tabla.

        NOTA: CFDIs cargados antes de mergear este PR no tienen `datos_nomina`
        en `raw_json` (porque el parser de entonces no lo extraía), y se skipean.
        El usuario tendrá que recargarlos para verlos en la vista de nómina.
        """
        with self._lock, self._conn:
            cur = self._conn.execute(
                "SELECT uuid, raw_json FROM cfdis WHERE tipo = 'N'"
            )
            filas_n = cur.fetchall()

            insertadas = 0
            for row in filas_n:
                uuid_n = row["uuid"]
                try:
                    raw = json.loads(row["raw_json"] or "{}")
                except (json.JSONDecodeError, TypeError):
                    continue
                dn = raw.get("datos_nomina")
                if not dn:
                    continue

                # ¿Ya hay recibo para este CFDI? Idempotencia.
                check = self._conn.execute(
                    "SELECT 1 FROM nomina_recibos WHERE cfdi_uuid = ? LIMIT 1",
                    (uuid_n,),
                )
                if check.fetchone():
                    continue

                self._insertar_nomina(uuid_n, dn)
                insertadas += 1

            if insertadas:
                logger.info(
                    "[procesador] migración 005: %d recibos de nómina repoblados desde raw_json",
                    insertadas,
                )

    def _insertar_nomina(self, cfdi_uuid: str, datos: "DatosNomina | dict") -> None:
        """
        Inserta una fila en `nomina_recibos` y N filas en `nomina_conceptos`
        a partir del dict o dataclass `datos`. Espejo de `_insertar_pagos_relaciones`.
        """
        if isinstance(datos, dict):
            d = datos
        else:
            d = datos.__dict__

        # Conceptos pueden venir como dataclasses o ya como dicts (raw_json).
        conceptos_raw = d.get("conceptos") or []
        conceptos = [c if isinstance(c, dict) else c.__dict__ for c in conceptos_raw]

        self._conn.execute(
            """
            INSERT INTO nomina_recibos (
                cfdi_uuid, registro_patronal, curp, nss, num_empleado, puesto,
                departamento, tipo_contrato, tipo_regimen, tipo_jornada,
                periodicidad_pago, fecha_inicio_rel_laboral, antiguedad,
                salario_base_cot_apor, salario_diario_integrado, riesgo_trabajo,
                banco, cuenta_bancaria, sindicalizado, clave_ent_fed,
                tipo_nomina, fecha_pago, fecha_inicial_pago, fecha_final_pago,
                num_dias_pagados, total_percepciones, total_deducciones, total_otros_pagos
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                      ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                cfdi_uuid,
                d.get("registro_patronal") or "",
                d.get("curp") or "",
                d.get("nss") or "",
                d.get("num_empleado") or "",
                d.get("puesto") or "",
                d.get("departamento") or "",
                d.get("tipo_contrato") or "",
                d.get("tipo_regimen") or "",
                d.get("tipo_jornada") or "",
                d.get("periodicidad_pago") or "",
                d.get("fecha_inicio_rel_laboral") or "",
                d.get("antiguedad") or "",
                float(d.get("salario_base_cot_apor") or 0.0),
                float(d.get("salario_diario_integrado") or 0.0),
                d.get("riesgo_trabajo") or "",
                d.get("banco") or "",
                d.get("cuenta_bancaria") or "",
                d.get("sindicalizado") or "",
                d.get("clave_ent_fed") or "",
                d.get("tipo_nomina") or "",
                d.get("fecha_pago") or "",
                d.get("fecha_inicial_pago") or "",
                d.get("fecha_final_pago") or "",
                float(d.get("num_dias_pagados") or 0.0),
                float(d.get("total_percepciones") or 0.0),
                float(d.get("total_deducciones") or 0.0),
                float(d.get("total_otros_pagos") or 0.0),
            ),
        )

        for c in conceptos:
            self._conn.execute(
                """
                INSERT INTO nomina_conceptos (
                    cfdi_uuid, clase, tipo_concepto, clave_interna, concepto,
                    importe_gravado, importe_exento, importe, subsidio_causado
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cfdi_uuid,
                    c.get("clase") or "",
                    c.get("tipo_concepto") or "",
                    c.get("clave_interna") or "",
                    c.get("concepto") or "",
                    float(c.get("importe_gravado") or 0.0),
                    float(c.get("importe_exento") or 0.0),
                    float(c.get("importe") or 0.0),
                    float(c.get("subsidio_causado") or 0.0),
                ),
            )

    def _insertar_pagos_relaciones(self, cfdi_pago_uuid: str, datos_pago: dict) -> int:
        """
        Inserta filas en `pagos_relaciones` a partir del dict `datos_pago`
        (forma serializada de `DatosPago`). Devuelve el conteo insertado.
        """
        docs = datos_pago.get("documentos_relacionados") or []
        if not docs:
            return 0

        count = 0
        for d in docs:
            self._conn.execute(
                """
                INSERT INTO pagos_relaciones (
                    cfdi_pago_uuid, cfdi_pago_fecha_pago, cfdi_pago_monto,
                    cfdi_pago_forma, cfdi_pago_moneda,
                    docto_uuid, docto_serie, docto_folio,
                    docto_metodo_pago, docto_num_parcialidad,
                    docto_imp_saldo_ant, docto_imp_pagado, docto_imp_saldo_insoluto,
                    docto_moneda
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    cfdi_pago_uuid,
                    datos_pago.get("fecha_pago") or "",
                    float(datos_pago.get("monto_pago") or 0.0),
                    datos_pago.get("forma_de_pago") or "",
                    datos_pago.get("moneda_pago") or "",
                    d.get("id_documento") or "",
                    d.get("serie") or "",
                    d.get("folio") or "",
                    d.get("metodo_de_pago_dr") or "",
                    int(d.get("num_parcialidad") or 0),
                    float(d.get("imp_saldo_ant") or 0.0),
                    float(d.get("imp_pagado") or 0.0),
                    float(d.get("imp_saldo_insoluto") or 0.0),
                    d.get("moneda_dr") or "",
                ),
            )
            count += 1
        return count

    # ------------------------------------------------------------------
    # CFDIs
    # ------------------------------------------------------------------

    def agregar(
        self,
        cfdis: list[CfdiData],
        mi_rfc: Optional[str] = None,
        direccion_fija: Optional[str] = None,
    ) -> dict[str, int]:
        """
        Inserta CFDIs con `INSERT OR IGNORE` (deduplicación por UUID).

        Calcula la columna `direccion`:
        - Si `direccion_fija` se da ('E' o 'R'), se aplica a todos los CFDIs
          (caso "cargar desde empresa" donde ya sabemos la subcarpeta).
        - Si no, y se da `mi_rfc`, compara emisor/receptor para inferir.
        - Si nada, queda NULL.
        """
        agregados = 0
        duplicados = 0
        ahora = datetime.now(timezone.utc).isoformat()

        with self._lock, self._conn:
            for cfdi in cfdis:
                if not cfdi.uuid:
                    duplicados += 1
                    continue

                # ¿Ya existe? `INSERT OR IGNORE` no nos da forma simple de saberlo
                # post-hoc en sqlite3, así que verificamos antes.
                cur = self._conn.execute(
                    "SELECT 1 FROM cfdis WHERE uuid = ?", (cfdi.uuid,)
                )
                if cur.fetchone() is not None:
                    duplicados += 1
                    continue

                # Calcular `direccion`: explícita > inferida (vs mi_rfc) > NULL.
                direccion: Optional[str] = None
                if direccion_fija in ("E", "R"):
                    direccion = direccion_fija
                elif mi_rfc:
                    if cfdi.emisor_rfc and cfdi.emisor_rfc.upper() == mi_rfc.upper():
                        direccion = "E"
                    elif cfdi.receptor_rfc and cfdi.receptor_rfc.upper() == mi_rfc.upper():
                        direccion = "R"

                self._conn.execute(
                    """
                    INSERT INTO cfdis (
                        uuid, file_name, version, tipo, fecha, fecha_timbrado,
                        serie, folio,
                        emisor_rfc, emisor_nombre, emisor_regimen_fiscal,
                        receptor_rfc, receptor_nombre, receptor_uso_cfdi,
                        sub_total, descuento, total,
                        iva_trasladado, ieps_trasladado, iva_retenido, isr_retenido,
                        forma_pago, metodo_pago, moneda, tipo_cambio, lugar_expedicion,
                        direccion, estado_sat, validado_en,
                        raw_json, warnings_json, cargado_en
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                              ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        cfdi.uuid, cfdi.file_name, cfdi.version, cfdi.tipo_comprobante,
                        cfdi.fecha_emision, cfdi.fecha_timbrado,
                        cfdi.serie, cfdi.folio,
                        cfdi.emisor_rfc, cfdi.emisor_nombre, cfdi.emisor_regimen_fiscal,
                        cfdi.receptor_rfc, cfdi.receptor_nombre, cfdi.receptor_uso_cfdi,
                        cfdi.sub_total, cfdi.descuento, cfdi.total,
                        cfdi.iva_trasladado, cfdi.ieps_trasladado,
                        cfdi.iva_retenido, cfdi.isr_retenido,
                        cfdi.forma_pago, cfdi.metodo_pago, cfdi.moneda,
                        cfdi.tipo_cambio, cfdi.lugar_expedicion,
                        direccion, cfdi.estado_sat, cfdi.validado_en,
                        json.dumps(cfdi.to_dict(), ensure_ascii=False),
                        json.dumps(cfdi.warnings, ensure_ascii=False),
                        ahora,
                    ),
                )

                for concepto in cfdi.conceptos:
                    self._conn.execute(
                        """
                        INSERT INTO conceptos (
                            cfdi_uuid, clave_prod_serv, descripcion, cantidad,
                            clave_unidad, unidad, valor_unitario, importe, descuento
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            cfdi.uuid,
                            concepto.clave_prod_serv, concepto.descripcion,
                            concepto.cantidad, concepto.clave_unidad, concepto.unidad,
                            concepto.valor_unitario, concepto.importe, concepto.descuento,
                        ),
                    )

                # Si es CFDI tipo N con datos_nomina, hidrata las tablas
                # `nomina_recibos` y `nomina_conceptos` para que los reportes
                # del procesador de Nómina sean SQL puro.
                if cfdi.tipo_comprobante == "N" and cfdi.datos_nomina is not None:
                    self._insertar_nomina(cfdi.uuid, cfdi.datos_nomina)

                # Si es CFDI tipo P con datos_pago, además normaliza sus
                # DoctoRelacionado a la tabla `pagos_relaciones` para que el
                # procesador de Pagos pueda hacer queries SQL puras sin tocar
                # `raw_json`.
                if cfdi.tipo_comprobante == "P" and cfdi.datos_pago is not None:
                    dp_dict = (
                        cfdi.datos_pago
                        if isinstance(cfdi.datos_pago, dict)
                        else cfdi.datos_pago.__dict__
                    )
                    # `documentos_relacionados` puede venir como lista de
                    # objetos dataclass o ya como lista de dicts (raw_json).
                    docs = dp_dict.get("documentos_relacionados") or []
                    docs_dict = [
                        d if isinstance(d, dict) else d.__dict__ for d in docs
                    ]
                    self._insertar_pagos_relaciones(
                        cfdi.uuid,
                        {
                            "fecha_pago": dp_dict.get("fecha_pago", ""),
                            "monto_pago": dp_dict.get("monto_pago", 0.0),
                            "forma_de_pago": dp_dict.get("forma_de_pago", ""),
                            "moneda_pago": dp_dict.get("moneda_pago", ""),
                            "documentos_relacionados": docs_dict,
                        },
                    )

                agregados += 1

        return {"agregados": agregados, "duplicados": duplicados}

    def borrar(self) -> None:
        """Vacía todas las tablas del procesador."""
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM conceptos")
            self._conn.execute("DELETE FROM pagos_relaciones")
            self._conn.execute("DELETE FROM nomina_conceptos")
            self._conn.execute("DELETE FROM nomina_recibos")
            self._conn.execute("DELETE FROM cfdis")
            self._conn.execute("DELETE FROM filtros")

    def count(self, filtros: Optional[CfdiFiltros] = None) -> int:
        sql, params = _construir_where(filtros)
        with self._lock:
            cur = self._conn.execute(f"SELECT COUNT(*) FROM cfdis {sql}", params)
            return cur.fetchone()[0]

    def listar(
        self,
        filtros: Optional[CfdiFiltros] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> dict[str, Any]:
        """Devuelve `{total, items: list[dict]}` con paginación."""
        sql, params = _construir_where(filtros)
        offset = max(0, (page - 1) * page_size)
        with self._lock:
            cur_total = self._conn.execute(f"SELECT COUNT(*) FROM cfdis {sql}", params)
            total = cur_total.fetchone()[0]
            cur = self._conn.execute(
                f"SELECT * FROM cfdis {sql} ORDER BY fecha DESC, uuid LIMIT ? OFFSET ?",
                (*params, page_size, offset),
            )
            items = [_row_to_dict(r) for r in cur.fetchall()]
        return {"total": total, "page": page, "page_size": page_size, "items": items}

    def iter_all(self, filtros: Optional[CfdiFiltros] = None) -> Iterator[dict]:
        """Itera todos los CFDIs (sin paginación). Útil para export streaming."""
        sql, params = _construir_where(filtros)
        with self._lock:
            cur = self._conn.execute(
                f"SELECT * FROM cfdis {sql} ORDER BY fecha DESC, uuid", params
            )
            while True:
                rows = cur.fetchmany(500)
                if not rows:
                    break
                for r in rows:
                    yield _row_to_dict(r)

    def conceptos_de(self, cfdi_uuid: str) -> list[dict]:
        with self._lock:
            cur = self._conn.execute(
                """
                SELECT clave_prod_serv, descripcion, cantidad, clave_unidad, unidad,
                       valor_unitario, importe, descuento
                FROM conceptos WHERE cfdi_uuid = ?
                """,
                (cfdi_uuid,),
            )
            return [dict(r) for r in cur.fetchall()]

    # ------------------------------------------------------------------
    # Estado SAT (lo escribe el endpoint /validar-sat)
    # ------------------------------------------------------------------

    def actualizar_estado_sat(self, uuid: str, estado: str) -> None:
        ahora = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            self._conn.execute(
                "UPDATE cfdis SET estado_sat = ?, validado_en = ? WHERE uuid = ?",
                (estado, ahora, uuid),
            )

    def uuids_sin_validar(self, limit: Optional[int] = None) -> list[str]:
        sql = "SELECT uuid FROM cfdis WHERE estado_sat IS NULL"
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
        with self._lock:
            return [r[0] for r in self._conn.execute(sql).fetchall()]

    # ------------------------------------------------------------------
    # Listas negras del SAT (Art. 69 y 69-B)
    # ------------------------------------------------------------------

    def rfcs_sin_validar_listas(
        self,
        ttl_days: int = 30,
        force_refresh: bool = False,
    ) -> list[str]:
        """RFCs únicos (emisor + receptor) que necesitan revalidación.

        Las listas del SAT se actualizan mensualmente (cron del día 5); un TTL
        de 30 días evita pegarle al endpoint sin valor agregado. Si
        `force_refresh` es True, devuelve todos los RFCs del buffer.
        """
        if force_refresh:
            sql = (
                "SELECT DISTINCT rfc FROM ("
                "  SELECT emisor_rfc AS rfc FROM cfdis WHERE emisor_rfc IS NOT NULL AND emisor_rfc != ''"
                "  UNION"
                "  SELECT receptor_rfc AS rfc FROM cfdis WHERE receptor_rfc IS NOT NULL AND receptor_rfc != ''"
                ")"
            )
            params: tuple = ()
        else:
            # Un RFC necesita revalidación si CUALQUIER CFDI donde aparece
            # tiene `validado_listas_en` NULL o más viejo que el TTL. Usamos
            # MIN sobre COALESCE→'' para que NULL gane (cadena vacía < cualquier
            # ISO timestamp).
            from datetime import timedelta
            limite = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
            sql = """
                SELECT DISTINCT rfc FROM (
                  SELECT emisor_rfc AS rfc, validado_listas_en AS validado
                  FROM cfdis WHERE emisor_rfc IS NOT NULL AND emisor_rfc != ''
                  UNION ALL
                  SELECT receptor_rfc AS rfc, validado_listas_en AS validado
                  FROM cfdis WHERE receptor_rfc IS NOT NULL AND receptor_rfc != ''
                )
                GROUP BY rfc
                HAVING MIN(COALESCE(validado, '')) < ?
            """
            params = (limite,)
        with self._lock:
            return [r[0] for r in self._conn.execute(sql, params).fetchall()]

    def actualizar_lista_negra_rfc(
        self,
        rfc: str,
        etiqueta: str,
        match_json: str,
    ) -> int:
        """Aplica el resultado de un RFC a todas las filas de `cfdis` donde
        ese RFC aparezca como emisor y/o receptor. Devuelve filas tocadas
        (puede ser > total de CFDIs porque un CFDI cuyo emisor y receptor
        son el mismo RFC se actualiza una vez por lado).
        """
        ahora = datetime.now(timezone.utc).isoformat()
        with self._lock, self._conn:
            cur_e = self._conn.execute(
                """
                UPDATE cfdis
                SET emisor_en_lista_negra = ?,
                    emisor_listas_match = ?,
                    validado_listas_en = ?
                WHERE emisor_rfc = ?
                """,
                (etiqueta, match_json, ahora, rfc),
            )
            cur_r = self._conn.execute(
                """
                UPDATE cfdis
                SET receptor_en_lista_negra = ?,
                    receptor_listas_match = ?,
                    validado_listas_en = ?
                WHERE receptor_rfc = ?
                """,
                (etiqueta, match_json, ahora, rfc),
            )
            return (cur_e.rowcount or 0) + (cur_r.rowcount or 0)

    def stats_listas_negras(
        self,
        filtros: Optional[CfdiFiltros] = None,
    ) -> dict:
        """Conteos para los cards de la página de listas negras.

        - `efos_emisores_unicos`: RFCs únicos en `emisor_en_lista_negra='EFOS'`.
        - `cfdis_edos`: CFDIs cuyo emisor es EFOS (alta exposición fiscal).
        - `cfdis_emisor_aclarado`: emisor con antecedente desvirtuado/sentencia.
        - `cfdis_emisor_69`: emisor en lista 69 (créditos firmes, no localizado, etc.).
        - `cfdis_limpios`: ambos lados marcados limpios.
        - `cfdis_sin_validar`: filas con `validado_listas_en IS NULL`.
        """
        where_sql, params = _construir_where(filtros)
        prefix = f"SELECT COUNT(*) FROM cfdis {where_sql}"

        def _count_extra(extra: str, *extra_params) -> int:
            sep = " AND " if where_sql else " WHERE "
            sql = f"{prefix}{sep}{extra}"
            cur = self._conn.execute(sql, (*params, *extra_params))
            return cur.fetchone()[0]

        with self._lock:
            sep = " AND " if where_sql else " WHERE "
            efos_emisores = self._conn.execute(
                f"SELECT COUNT(DISTINCT emisor_rfc) FROM cfdis {where_sql}"
                f"{sep}emisor_en_lista_negra = 'EFOS'",
                params,
            ).fetchone()[0]

            return {
                "efos_emisores_unicos": efos_emisores,
                "cfdis_edos": _count_extra("emisor_en_lista_negra = 'EFOS'"),
                "cfdis_emisor_aclarado": _count_extra("emisor_en_lista_negra = 'Aclarado'"),
                "cfdis_emisor_69": _count_extra("emisor_en_lista_negra = '69'"),
                "cfdis_limpios": _count_extra(
                    "emisor_en_lista_negra = 'Limpio' "
                    "AND (receptor_en_lista_negra IS NULL "
                    "     OR receptor_en_lista_negra = 'Limpio')"
                ),
                "cfdis_sin_validar": _count_extra("validado_listas_en IS NULL"),
            }

    # ------------------------------------------------------------------
    # Filtros persistidos
    # ------------------------------------------------------------------

    def filtros_get(self, key: str = "actuales") -> dict:
        """
        Lee los filtros persistidos para un procesador. `key` distingue cada
        uno: 'actuales' (CFDI), 'pagos_actuales' (Pagos), etc.
        Si no hay nada guardado o el JSON es inválido devuelve `filtros_vacios()`
        para el de CFDI; para otros procesadores devuelve `{}` (el caller hace
        merge con su propio default).
        """
        with self._lock:
            cur = self._conn.execute(
                "SELECT value FROM filtros WHERE key = ?", (key,)
            )
            row = cur.fetchone()
        if row is None:
            return filtros_vacios() if key == "actuales" else {}
        try:
            return json.loads(row[0])
        except (json.JSONDecodeError, TypeError):
            return filtros_vacios() if key == "actuales" else {}

    def filtros_set(self, filtros: dict, key: str = "actuales") -> None:
        payload = json.dumps(filtros, ensure_ascii=False)
        with self._lock, self._conn:
            self._conn.execute(
                """
                INSERT INTO filtros (key, value) VALUES (?, ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (key, payload),
            )

    # ------------------------------------------------------------------
    # Acceso bajo nivel (para reportes_cfdi)
    # ------------------------------------------------------------------

    @contextmanager
    def cursor(self):
        """Context manager que retorna un cursor bajo lock."""
        with self._lock:
            cur = self._conn.cursor()
            try:
                yield cur
            finally:
                cur.close()

    def close(self) -> None:
        with self._lock:
            self._conn.close()


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_singleton: Optional[ProcesadorDB] = None
_singleton_lock = threading.Lock()


def abrir_db(path: Optional[Path] = None) -> ProcesadorDB:
    """Devuelve la instancia singleton del procesador DB."""
    global _singleton
    with _singleton_lock:
        if _singleton is None:
            _singleton = ProcesadorDB(path or DEFAULT_DB_PATH)
        return _singleton


def resetear_singleton_para_tests() -> None:
    """Llamado por los tests para forzar una DB en `:memory:` o tmp."""
    global _singleton
    with _singleton_lock:
        if _singleton is not None:
            _singleton.close()
        _singleton = None


# ---------------------------------------------------------------------------
# Helpers de construcción de queries
# ---------------------------------------------------------------------------


def _construir_where(filtros: Optional[CfdiFiltros]) -> tuple[str, tuple]:
    """Construye la cláusula WHERE con bind params a partir de un dict de filtros."""
    if not filtros:
        return "", ()

    clauses: list[str] = []
    params: list[Any] = []

    desde = filtros.get("desde")
    hasta = filtros.get("hasta")
    if desde:
        clauses.append("fecha >= ?")
        params.append(desde)
    if hasta:
        # `hasta` inclusive — añadimos el día completo
        clauses.append("fecha <= ?")
        params.append(f"{hasta}T23:59:59")

    tipo = filtros.get("tipo")
    if tipo:
        if isinstance(tipo, (list, tuple)):
            placeholders = ",".join("?" for _ in tipo)
            clauses.append(f"tipo IN ({placeholders})")
            params.extend(tipo)
        else:
            clauses.append("tipo = ?")
            params.append(tipo)

    direccion = filtros.get("direccion")
    if direccion in ("E", "R"):
        clauses.append("direccion = ?")
        params.append(direccion)

    busqueda = filtros.get("busqueda")
    if busqueda:
        like = f"%{busqueda.lower()}%"
        clauses.append(
            "(LOWER(emisor_nombre) LIKE ? OR LOWER(receptor_nombre) LIKE ? "
            "OR LOWER(emisor_rfc) LIKE ? OR LOWER(receptor_rfc) LIKE ? "
            "OR LOWER(uuid) LIKE ? OR LOWER(folio) LIKE ?)"
        )
        params.extend([like] * 6)

    monto_min = filtros.get("monto_min")
    if monto_min is not None:
        clauses.append("total >= ?")
        params.append(float(monto_min))
    monto_max = filtros.get("monto_max")
    if monto_max is not None:
        clauses.append("total <= ?")
        params.append(float(monto_max))

    if filtros.get("solo_con_errores"):
        clauses.append("warnings_json != '[]' AND warnings_json IS NOT NULL")

    # Filtros de listas negras: 'EFOS' | 'Aclarado' | '69' | 'Limpio' | 'SinValidar'
    emisor_lista = filtros.get("emisor_lista_negra")
    if emisor_lista:
        if emisor_lista == "SinValidar":
            clauses.append("emisor_en_lista_negra IS NULL")
        else:
            clauses.append("emisor_en_lista_negra = ?")
            params.append(emisor_lista)

    if not clauses:
        return "", ()
    return "WHERE " + " AND ".join(clauses), tuple(params)


def _row_to_dict(row: sqlite3.Row) -> dict:
    """Convierte un Row al shape que devuelve el endpoint."""
    d = dict(row)
    if d.get("raw_json"):
        try:
            d["raw"] = json.loads(d["raw_json"])
        except (json.JSONDecodeError, TypeError):
            d["raw"] = None
    d.pop("raw_json", None)
    if d.get("warnings_json"):
        try:
            d["warnings"] = json.loads(d["warnings_json"])
        except (json.JSONDecodeError, TypeError):
            d["warnings"] = []
    else:
        d["warnings"] = []
    d.pop("warnings_json", None)
    return d

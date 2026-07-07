"""Prellenado de renglones DIOT desde el buffer del procesador.

Criterio v1 (el mismo de la plantilla Excel de TodoConta, ver docs/diot-2025.md):
CFDIs **recibidos** (receptor = empresa activa, emisor ≠ empresa activa) de
tipo I y E, del periodo por **fecha de emisión**, agrupados por RFC del emisor.
Las notas de crédito (E) no se restan con negativos: van a los campos de
"Devoluciones, descuentos y bonificaciones" que el layout 2025 trae por tasa.
El flujo de efectivo (PUE/PPD + complemento de pagos) es mejora futura.
"""

from __future__ import annotations

import calendar
import re

from ..procesador import abrir_db
from . import store
from .catalogos import OPERACION_DEFAULT, RFC_EXTRANJERO, RFC_GLOBAL
from .layout import fila_vacia
from .store import validar_periodo

_RFC_RE = re.compile(r"^[A-ZÑ&0-9]{12,13}$")


def _redondear(x: float) -> int:
    # int(round()) usa banker's rounding, igual que el CLng de la plantilla VBA:
    # el usuario puede cotejar 1:1 contra su Excel.
    return int(round(x))


def _acreditable(iva_neto: float, valor: int, dev: int, tasa: float) -> int:
    """IVA acreditable de una categoría: neto, piso en 0 y capado al tope del SAT.

    La aplicación DIOT valida acreditable ≤ round((valor − dev) × tasa) sobre
    los ENTEROS declarados; ver "Validaciones de la aplicación" en
    docs/diot-2025.md.
    """
    tope = _redondear(max(0, valor - dev) * tasa)
    return min(max(0, _redondear(iva_neto)), tope)


def _rango_del_periodo(periodo: str) -> tuple[str, str]:
    anio, mes = int(periodo[:4]), int(periodo[5:7])
    ultimo_dia = calendar.monthrange(anio, mes)[1]
    # Mismo truco que _construir_where del procesador: fecha ISO completa.
    return f"{periodo}-01T00:00:00", f"{periodo}-{ultimo_dia:02d}T23:59:59"


def _tipo_tercero_para(rfc: str) -> str:
    if rfc == RFC_GLOBAL:
        return "15"
    if rfc == RFC_EXTRANJERO or not _RFC_RE.match(rfc):
        return "05"
    return "04"


class _Acumulado:
    __slots__ = (
        "nombre", "num_cfdis", "sin_desglose",
        "base16_i", "base16_e", "base8_i", "base8_e",
        "iva16_i", "iva16_e", "iva8_i", "iva8_e",
        "base0_i", "base0_e", "exento_i", "exento_e",
        "retenido_i", "retenido_e",
    )

    def __init__(self) -> None:
        self.nombre = ""
        self.num_cfdis = 0
        self.sin_desglose = 0
        for slot in self.__slots__[3:]:
            setattr(self, slot, 0.0)


def prellenar_desde_procesador(mi_rfc: str, periodo: str, db=None) -> dict:
    """Agrega los CFDIs recibidos del periodo y devuelve renglones DIOT.

    Returns:
        {"filas": [fila, ...], "resumen": {"cfdis_considerados": int,
         "cfdis_sin_desglose": int, "proveedores": int}}

    Las filas llevan metadatos que NO se exportan al TXT: `nombre` (para la
    UI), `origen` ("cfdi"), `estimado` (bases derivadas de iva/0.16 en filas
    cargadas antes de la migración 008) y `num_cfdis`.
    """
    validar_periodo(periodo)
    mi_rfc = mi_rfc.strip().upper()
    desde, hasta = _rango_del_periodo(periodo)

    if db is None:
        db = abrir_db()
    with db.cursor() as cur:
        cur.execute(
            """
            SELECT tipo, emisor_rfc, emisor_nombre,
                   iva_trasladado, iva_retenido,
                   base_iva_16, base_iva_8, iva_trasladado_8,
                   base_iva_0, base_exento
            FROM cfdis
            WHERE mi_rfc = ?
              AND tipo IN ('I', 'E')
              AND UPPER(TRIM(receptor_rfc)) = ?
              AND UPPER(TRIM(emisor_rfc)) != ?
              AND fecha >= ? AND fecha <= ?
            """,
            (mi_rfc, mi_rfc, mi_rfc, desde, hasta),
        )
        filas_db = cur.fetchall()

    acumulados: dict[str, _Acumulado] = {}
    for row in filas_db:
        rfc = (row["emisor_rfc"] or "").strip().upper()
        acc = acumulados.setdefault(rfc, _Acumulado())
        acc.num_cfdis += 1
        if not acc.nombre and row["emisor_nombre"]:
            acc.nombre = row["emisor_nombre"]

        base16 = row["base_iva_16"]
        iva16 = row["iva_trasladado"] or 0.0
        if base16 is None:
            # Fila cargada antes de la migración 008: el desglose no existe.
            # Estimamos la base 16% desde el IVA; 8%/0%/exento no son recuperables.
            acc.sin_desglose += 1
            base16 = iva16 / 0.16 if iva16 else 0.0
            base8 = iva8 = base0 = exento = 0.0
        else:
            base8 = row["base_iva_8"] or 0.0
            iva8 = row["iva_trasladado_8"] or 0.0
            base0 = row["base_iva_0"] or 0.0
            exento = row["base_exento"] or 0.0
        retenido = row["iva_retenido"] or 0.0

        sufijo = "i" if row["tipo"] == "I" else "e"
        for slot, valor in (
            ("base16", base16), ("iva16", iva16), ("base8", base8), ("iva8", iva8),
            ("base0", base0), ("exento", exento), ("retenido", retenido),
        ):
            attr = f"{slot}_{sufijo}"
            setattr(acc, attr, getattr(acc, attr) + valor)

    filas: list[dict] = []
    total_sin_desglose = 0
    for rfc in sorted(acumulados):
        acc = acumulados[rfc]
        total_sin_desglose += acc.sin_desglose
        tercero = _tipo_tercero_para(rfc)

        # Valores de actos por tasa. Asunción v1: todo el 8% va a región
        # fronteriza NORTE (el CFDI no distingue norte/sur); editable.
        valor_16 = _redondear(acc.base16_i)
        dev_16 = _redondear(acc.base16_e)
        valor_rf_norte = _redondear(acc.base8_i)
        dev_rf_norte = _redondear(acc.base8_e)

        fila = fila_vacia()
        fila.update(
            tipo_tercero=tercero,
            tipo_operacion=OPERACION_DEFAULT[tercero],
            rfc=rfc if tercero != "05" or _RFC_RE.match(rfc) else "",
            valor_16=valor_16,
            dev_16=dev_16,
            valor_rf_norte=valor_rf_norte,
            dev_rf_norte=dev_rf_norte,
            # IVA acreditable: neto de notas de crédito, piso en 0 y CAPADO al
            # "IVA pagado" que la aplicación del SAT deriva de los enteros
            # declarados — round((valor − dev) × tasa). Sin el cap, redondear
            # bases e IVA por separado puede quedar 1 peso arriba y el SAT
            # rechaza la carga (confirmado con un archivo real, docs/diot-2025.md).
            acred_excl_16=_acreditable(acc.iva16_i - acc.iva16_e, valor_16, dev_16, 0.16),
            acred_excl_rf_norte=_acreditable(
                acc.iva8_i - acc.iva8_e, valor_rf_norte, dev_rf_norte, 0.08
            ),
            # Adicionales (netos, piso en 0).
            tasa_0=max(0, _redondear(acc.base0_i - acc.base0_e)),
            exentos=max(0, _redondear(acc.exento_i - acc.exento_e)),
            iva_retenido=max(0, _redondear(acc.retenido_i - acc.retenido_e)),
        )
        # Metadatos para la UI/estado — exportar.py los ignora.
        fila.update(
            nombre=acc.nombre,
            origen="cfdi",
            estimado=acc.sin_desglose > 0,
            num_cfdis=acc.num_cfdis,
        )
        filas.append(fila)

    return {
        "filas": filas,
        "resumen": {
            "cfdis_considerados": len(filas_db),
            "cfdis_sin_desglose": total_sin_desglose,
            "proveedores": len(filas),
        },
    }


def prellenar_y_guardar(mi_rfc: str, periodo: str, db=None) -> dict:
    """Prellena el periodo y lo persiste, conservando los renglones manuales.

    Los renglones con ``origen == "manual"`` (agregados a mano por el usuario)
    sobreviven al re-prellenado; los renglones ``cfdi`` se regeneran completos.
    """
    resultado = prellenar_desde_procesador(mi_rfc, periodo, db=db)
    previo = store.get_periodo(mi_rfc, periodo)
    manuales = [
        f for f in (previo or {}).get("filas", []) if f.get("origen") == "manual"
    ]
    filas = resultado["filas"] + manuales
    estado = store.set_periodo(mi_rfc, periodo, filas, origen="prellenado")
    estado["resumen"] = resultado["resumen"]
    return estado

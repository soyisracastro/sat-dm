"""Layout oficial del archivo de carga masiva de la DIOT (ejercicios 2025+).

Los 54 campos, su orden y sus reglas vienen del "Instructivo para el armado
del archivo de carga masiva" (SAT, Enero 2025) — la referencia completa, con
las citas textuales y los ejemplos oficiales, está en docs/diot-2025.md.

El layout es DATO, no código: si la validación contra el SAT obliga a corregir
algo, se ajusta la tupla `CAMPOS_DIOT` (y el golden file de tests) sin tocar
la agregación ni la UI.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TipoCampo = Literal["catalogo", "texto", "entero"]


@dataclass(frozen=True)
class CampoDiot:
    clave: str
    etiqueta: str
    tipo: TipoCampo
    # Longitud máxima (posiciones) según el instructivo; None = sin límite práctico.
    max_len: int | None = None
    # Sección del instructivo, para agrupar en la UI:
    #   tercero | valores | iva_acreditable | iva_no_acreditable | adicionales
    seccion: str = "valores"


def _entero(clave: str, etiqueta: str, seccion: str) -> CampoDiot:
    # Todos los montos: "Numérico máximo 14 posiciones. No permite decimales. Acepta cero."
    return CampoDiot(clave, etiqueta, "entero", max_len=14, seccion=seccion)


# Los 54 campos EN ORDEN. No reordenar sin actualizar docs/diot-2025.md.
CAMPOS_DIOT: tuple[CampoDiot, ...] = (
    # 3.1 Datos del tercero declarado (1–7)
    CampoDiot("tipo_tercero", "Tipo de tercero", "catalogo", 2, "tercero"),
    CampoDiot("tipo_operacion", "Tipo de operación", "catalogo", 2, "tercero"),
    CampoDiot("rfc", "RFC", "texto", 13, "tercero"),
    CampoDiot("id_fiscal", "Número de identificación fiscal", "texto", 40, "tercero"),
    CampoDiot("nombre_extranjero", "Nombre del extranjero", "texto", 300, "tercero"),
    CampoDiot("pais", "País o jurisdicción de residencia fiscal", "catalogo", 3, "tercero"),
    CampoDiot("lugar_jurisdiccion", "Especificar lugar de jurisdicción fiscal", "texto", 300, "tercero"),
    # 3.2 Valor de los actos o actividades (8–17): pares (valor total, devoluciones)
    _entero("valor_rf_norte", "Actos pagados en la región fronteriza norte", "valores"),
    _entero("dev_rf_norte", "Devoluciones, descuentos y bonificaciones — RF norte", "valores"),
    _entero("valor_rf_sur", "Actos pagados en la región fronteriza sur", "valores"),
    _entero("dev_rf_sur", "Devoluciones, descuentos y bonificaciones — RF sur", "valores"),
    _entero("valor_16", "Actos totales pagados a la tasa del 16% de IVA", "valores"),
    _entero("dev_16", "Devoluciones, descuentos y bonificaciones — 16%", "valores"),
    _entero("valor_imp_aduana_16", "Importación por aduana de bienes tangibles al 16%", "valores"),
    _entero("dev_imp_aduana_16", "Devoluciones — importación por aduana", "valores"),
    _entero("valor_imp_intang_16", "Importación de bienes intangibles y servicios al 16%", "valores"),
    _entero("dev_imp_intang_16", "Devoluciones — importación de intangibles/servicios", "valores"),
    # 3.3 IVA acreditable (18–27): pares (exclusivamente gravadas, proporción)
    _entero("acred_excl_rf_norte", "IVA acreditable exclusivo de gravadas — RF norte", "iva_acreditable"),
    _entero("acred_prop_rf_norte", "IVA acreditable con proporción — RF norte", "iva_acreditable"),
    _entero("acred_excl_rf_sur", "IVA acreditable exclusivo de gravadas — RF sur", "iva_acreditable"),
    _entero("acred_prop_rf_sur", "IVA acreditable con proporción — RF sur", "iva_acreditable"),
    _entero("acred_excl_16", "IVA acreditable exclusivo de gravadas — 16%", "iva_acreditable"),
    _entero("acred_prop_16", "IVA acreditable con proporción — 16%", "iva_acreditable"),
    _entero("acred_excl_imp_aduana", "IVA acreditable exclusivo — importación aduana", "iva_acreditable"),
    _entero("acred_prop_imp_aduana", "IVA acreditable con proporción — importación aduana", "iva_acreditable"),
    _entero("acred_excl_imp_intang", "IVA acreditable exclusivo — importación intangibles", "iva_acreditable"),
    _entero("acred_prop_imp_intang", "IVA acreditable con proporción — importación intangibles", "iva_acreditable"),
    # 3.4 IVA no acreditable (28–47): por categoría (proporción, sin requisitos, exentas, no objeto)
    _entero("noacred_prop_rf_norte", "IVA no acreditable con proporción — RF norte", "iva_no_acreditable"),
    _entero("noacred_sinreq_rf_norte", "IVA no acreditable sin requisitos — RF norte", "iva_no_acreditable"),
    _entero("noacred_exentas_rf_norte", "IVA no acreditable de exentas — RF norte", "iva_no_acreditable"),
    _entero("noacred_noobj_rf_norte", "IVA no acreditable de no objeto — RF norte", "iva_no_acreditable"),
    _entero("noacred_prop_rf_sur", "IVA no acreditable con proporción — RF sur", "iva_no_acreditable"),
    _entero("noacred_sinreq_rf_sur", "IVA no acreditable sin requisitos — RF sur", "iva_no_acreditable"),
    _entero("noacred_exentas_rf_sur", "IVA no acreditable de exentas — RF sur", "iva_no_acreditable"),
    _entero("noacred_noobj_rf_sur", "IVA no acreditable de no objeto — RF sur", "iva_no_acreditable"),
    _entero("noacred_prop_16", "IVA no acreditable con proporción — 16%", "iva_no_acreditable"),
    _entero("noacred_sinreq_16", "IVA no acreditable sin requisitos — 16%", "iva_no_acreditable"),
    _entero("noacred_exentas_16", "IVA no acreditable de exentas — 16%", "iva_no_acreditable"),
    _entero("noacred_noobj_16", "IVA no acreditable de no objeto — 16%", "iva_no_acreditable"),
    _entero("noacred_prop_imp_aduana", "IVA no acreditable con proporción — imp. aduana", "iva_no_acreditable"),
    _entero("noacred_sinreq_imp_aduana", "IVA no acreditable sin requisitos — imp. aduana", "iva_no_acreditable"),
    _entero("noacred_exentas_imp_aduana", "IVA no acreditable de exentas — imp. aduana", "iva_no_acreditable"),
    _entero("noacred_noobj_imp_aduana", "IVA no acreditable de no objeto — imp. aduana", "iva_no_acreditable"),
    _entero("noacred_prop_imp_intang", "IVA no acreditable con proporción — imp. intangibles", "iva_no_acreditable"),
    _entero("noacred_sinreq_imp_intang", "IVA no acreditable sin requisitos — imp. intangibles", "iva_no_acreditable"),
    _entero("noacred_exentas_imp_intang", "IVA no acreditable de exentas — imp. intangibles", "iva_no_acreditable"),
    _entero("noacred_noobj_imp_intang", "IVA no acreditable de no objeto — imp. intangibles", "iva_no_acreditable"),
    # 3.5 Datos adicionales (48–54)
    _entero("iva_retenido", "IVA retenido por el contribuyente", "adicionales"),
    _entero("imp_exentos", "Importación por la que no se pagará el IVA (exentos)", "adicionales"),
    _entero("exentos", "Actos pagados por los que no se pagará el IVA (exentos)", "adicionales"),
    _entero("tasa_0", "Demás actos pagados a la tasa del 0% de IVA", "adicionales"),
    _entero("noobj_territorio", "Actos no objeto del IVA en territorio nacional", "adicionales"),
    _entero("noobj_sin_establecimiento", "Actos no objeto del IVA sin establecimiento", "adicionales"),
    CampoDiot("manifiesto", "Manifiesto de efectos fiscales a los comprobantes", "catalogo", 2, "adicionales"),
)

assert len(CAMPOS_DIOT) == 54, "El layout oficial DIOT 2025 tiene exactamente 54 campos"

CLAVES_CAMPOS: tuple[str, ...] = tuple(c.clave for c in CAMPOS_DIOT)
CAMPOS_ENTEROS: tuple[str, ...] = tuple(c.clave for c in CAMPOS_DIOT if c.tipo == "entero")

# Campos del tercero que DEBEN ir vacíos salvo para proveedor extranjero (05).
_CAMPOS_SOLO_EXTRANJERO = ("id_fiscal", "nombre_extranjero", "pais", "lugar_jurisdiccion")


def fila_vacia() -> dict:
    """Renglón nuevo con defaults capturables (proveedor nacional, manifiesto Sí)."""
    fila: dict = {clave: 0 for clave in CAMPOS_ENTEROS}
    fila.update(
        tipo_tercero="04",
        tipo_operacion="85",
        rfc="",
        id_fiscal="",
        nombre_extranjero="",
        pais="",
        lugar_jurisdiccion="",
        manifiesto="01",
    )
    return fila


def formatear_linea(fila: dict) -> str:
    """Serializa un renglón a la línea pipe-delimited del archivo del SAT.

    Determinista con la fila ya validada: enteros en cero se emiten como "0"
    (como la primera línea del ejemplo oficial) y los campos exclusivos del
    tercero extranjero se fuerzan a vacío para 04/15 aunque la fila traiga
    basura, para que el TXT nunca salga inconsistente.
    """
    tipo_tercero = str(fila.get("tipo_tercero", "")).strip()
    pais = str(fila.get("pais", "")).strip().upper()

    valores: list[str] = []
    for campo in CAMPOS_DIOT:
        crudo = fila.get(campo.clave, "")
        if campo.tipo == "entero":
            valores.append(str(int(round(float(crudo or 0)))))
            continue
        texto = str(crudo or "").strip()
        if campo.clave in _CAMPOS_SOLO_EXTRANJERO and tipo_tercero != "05":
            texto = ""
        if campo.clave == "lugar_jurisdiccion" and pais != "ZZZ":
            texto = ""
        if campo.clave in ("rfc", "pais"):
            texto = texto.upper()
        # El pipe es el separador del formato: no puede viajar dentro de un valor.
        valores.append(texto.replace("|", " "))
    return "|".join(valores)

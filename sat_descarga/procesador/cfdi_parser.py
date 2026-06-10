"""
Parser completo de CFDI para el procesador.

Extrae todos los campos necesarios para reportes fiscales: cabecera, emisor,
receptor, montos, impuestos, conceptos y (para tipo P) datos del complemento
de pagos.

Soporta CFDI 3.3 y 4.0. Es namespace-agnóstico (usa `local-name()` vía xpath)
para tolerar XMLs con o sin prefijo `cfdi:`/`tfd:`/`pago:`.

Portado de todoconta-apps `lib/procesador-cfdi/xml-parser.ts` (DOMParser browser
→ lxml Python). La estructura de campos en `CfdiData` es paralela a la TS
para que el frontend reuse el shape sin transformaciones.
"""

from __future__ import annotations

import logging
from dataclasses import asdict, dataclass, field
from typing import Optional, Union

from lxml import etree

from ..core.xml_seguro import fromstring_seguro

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Estructuras de datos
# ---------------------------------------------------------------------------


@dataclass
class ConceptoCfdi:
    """Un concepto (fila dentro de `cfdi:Conceptos`)."""
    clave_prod_serv: str = ""
    descripcion: str = ""
    cantidad: float = 0.0
    clave_unidad: str = ""
    unidad: str = ""
    valor_unitario: float = 0.0
    importe: float = 0.0
    descuento: float = 0.0


@dataclass
class DocumentoRelacionado:
    """Documento relacionado dentro del complemento de Pagos."""
    id_documento: str = ""     # UUID del CFDI relacionado
    serie: str = ""
    folio: str = ""
    moneda_dr: str = ""
    metodo_de_pago_dr: str = ""
    num_parcialidad: int = 0
    imp_saldo_ant: float = 0.0
    imp_pagado: float = 0.0
    imp_saldo_insoluto: float = 0.0


@dataclass
class DatosPago:
    """Datos del complemento de Pagos (CFDI tipo P)."""
    fecha_pago: str = ""
    forma_de_pago: str = ""
    moneda_pago: str = ""
    monto_pago: float = 0.0
    documentos_relacionados: list[DocumentoRelacionado] = field(default_factory=list)


@dataclass
class ConceptoNomina:
    """Un concepto dentro de Percepciones / Deducciones / OtrosPagos."""
    clase: str = ""                  # 'Percepcion' | 'Deduccion' | 'OtroPago'
    tipo_concepto: str = ""          # clave SAT (TipoPercepcion / TipoDeduccion / TipoOtroPago)
    clave_interna: str = ""
    concepto: str = ""
    importe_gravado: float = 0.0
    importe_exento: float = 0.0
    importe: float = 0.0
    subsidio_causado: float = 0.0    # solo para OtroPago tipo 002 (Subsidio al Empleo)


@dataclass
class DatosNomina:
    """Datos del complemento de Nómina 1.2 (CFDI tipo N)."""
    # Emisor del complemento (patrón)
    registro_patronal: str = ""
    # Trabajador
    curp: str = ""
    nss: str = ""
    num_empleado: str = ""
    puesto: str = ""
    departamento: str = ""
    tipo_contrato: str = ""
    tipo_regimen: str = ""
    tipo_jornada: str = ""
    periodicidad_pago: str = ""
    fecha_inicio_rel_laboral: str = ""
    antiguedad: str = ""
    salario_base_cot_apor: float = 0.0
    salario_diario_integrado: float = 0.0
    riesgo_trabajo: str = ""
    banco: str = ""
    cuenta_bancaria: str = ""
    sindicalizado: str = ""
    clave_ent_fed: str = ""
    # Recibo
    tipo_nomina: str = ""            # 'O' | 'E'
    fecha_pago: str = ""
    fecha_inicial_pago: str = ""
    fecha_final_pago: str = ""
    num_dias_pagados: float = 0.0
    total_percepciones: float = 0.0
    total_deducciones: float = 0.0
    total_otros_pagos: float = 0.0
    # Conceptos (Percepciones + Deducciones + OtrosPagos)
    conceptos: list[ConceptoNomina] = field(default_factory=list)


@dataclass
class CfdiData:
    """
    Vista plana de un CFDI extraído del XML. Los nombres siguen snake_case y
    son paralelos a la interfaz `CfdiData` del frontend (camelCase en TS) —
    convertimos en el endpoint si hace falta.
    """
    # Metadata
    file_name: str = ""
    version: str = ""               # "3.3" | "4.0"
    tipo_comprobante: str = ""      # I | E | T | N | P

    # Timbrado
    uuid: str = ""
    fecha_emision: str = ""         # ISO YYYY-MM-DDTHH:MM:SS
    fecha_timbrado: str = ""        # ISO

    serie: str = ""
    folio: str = ""

    # Emisor
    emisor_nombre: str = ""
    emisor_rfc: str = ""
    emisor_regimen_fiscal: str = ""

    # Receptor
    receptor_nombre: str = ""
    receptor_rfc: str = ""
    receptor_uso_cfdi: str = ""

    # Montos
    sub_total: float = 0.0
    descuento: float = 0.0
    total: float = 0.0

    # Impuestos:
    #   - iva_trasladado:  suma de Traslado código 002 (IVA) — solo al 16%.
    #   - ieps_trasladado: suma de Traslado código 003 (IEPS) en cualquier tasa.
    #   - iva_retenido:    suma de Retencion código 002.
    #   - isr_retenido:    suma de Retencion código 001.
    iva_trasladado: float = 0.0
    ieps_trasladado: float = 0.0
    iva_retenido: float = 0.0
    isr_retenido: float = 0.0

    # Forma/método/moneda
    forma_pago: str = ""
    metodo_pago: str = ""
    moneda: str = "MXN"
    tipo_cambio: float = 1.0
    lugar_expedicion: str = ""

    # Conceptos
    conceptos: list[ConceptoCfdi] = field(default_factory=list)

    # Específico de Pagos (tipo P)
    datos_pago: Optional[DatosPago] = None

    # Específico de Nómina (tipo N)
    datos_nomina: Optional[DatosNomina] = None

    # Validación (poblada por procesador.validaciones)
    warnings: list[str] = field(default_factory=list)

    # Estado SAT (poblada por procesador.validaciones / validar-sat)
    estado_sat: Optional[str] = None      # "Vigente" | "Cancelado" | "No encontrado" | None
    validado_en: Optional[str] = None     # ISO timestamp

    def to_dict(self) -> dict:
        """Serialización plana para JSON / SQLite raw_json."""
        d = asdict(self)
        # `datos_pago` ya queda como dict anidado vía asdict.
        return d


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _local(elem) -> str:
    return etree.QName(elem).localname if elem is not None else ""


def _find_local(parent, local_name: str):
    """Primer descendiente (cualquier profundidad) con local-name = local_name."""
    if parent is None:
        return None
    results = parent.xpath(f".//*[local-name()=$n]", n=local_name)
    return results[0] if results else None


def _findall_local(parent, local_name: str) -> list:
    """Todos los descendientes con local-name = local_name."""
    if parent is None:
        return []
    return parent.xpath(f".//*[local-name()=$n]", n=local_name)


def _attr(elem, name: str, default: str = "") -> str:
    """Lee un atributo del elemento (vacío si elem es None o no existe)."""
    if elem is None:
        return default
    return elem.get(name, default) or default


def _to_float(val: Optional[str], default: float = 0.0) -> float:
    if not val:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _to_int(val: Optional[str], default: int = 0) -> int:
    if not val:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


# ---------------------------------------------------------------------------
# Sub-extractores
# ---------------------------------------------------------------------------


def _extraer_timbre_fiscal(root) -> tuple[str, str]:
    """Devuelve (uuid, fecha_timbrado) del nodo `TimbreFiscalDigital`."""
    tfd = _find_local(root, "TimbreFiscalDigital")
    if tfd is None:
        return "", ""
    return _attr(tfd, "UUID"), _attr(tfd, "FechaTimbrado")


def _extraer_impuestos(comprobante) -> tuple[float, float, float, float]:
    """
    Extrae IVA 16% trasladado, IEPS trasladado, IVA retenido e ISR retenido
    del nodo `Impuestos` hijo directo del Comprobante.

    Códigos SAT:
      - 001 = ISR
      - 002 = IVA
      - 003 = IEPS (Impuesto Especial sobre Producción y Servicios)
    """
    iva_trasladado = 0.0
    ieps_trasladado = 0.0
    iva_retenido = 0.0
    isr_retenido = 0.0

    # `Impuestos` puede aparecer también dentro de los conceptos — necesitamos
    # solo el `Impuestos` global, hijo directo del Comprobante.
    impuestos_global = None
    for child in comprobante:
        if _local(child) == "Impuestos":
            impuestos_global = child
            break
    if impuestos_global is None:
        return 0.0, 0.0, 0.0, 0.0

    # Traslados:
    #   - 002 (IVA) solo al 16% (espeja la lógica de todoconta).
    #   - 003 (IEPS) en cualquier tasa (las tasas son muy variadas:
    #     telecomunicaciones 3%, bebidas saborizadas 8%, combustibles, etc.).
    for traslado in _findall_local(impuestos_global, "Traslado"):
        impuesto = _attr(traslado, "Impuesto")
        importe = _to_float(_attr(traslado, "Importe"))
        if impuesto == "002":
            tasa = _attr(traslado, "TasaOCuota")
            if tasa in ("0.160000", "0.16"):
                iva_trasladado += importe
        elif impuesto == "003":
            ieps_trasladado += importe

    # Retenciones (IVA 002, ISR 001).
    for retencion in _findall_local(impuestos_global, "Retencion"):
        impuesto = _attr(retencion, "Impuesto")
        importe = _to_float(_attr(retencion, "Importe"))
        if impuesto == "002":
            iva_retenido += importe
        elif impuesto == "001":
            isr_retenido += importe

    return iva_trasladado, ieps_trasladado, iva_retenido, isr_retenido


def _extraer_conceptos(root) -> list[ConceptoCfdi]:
    out = []
    for c in _findall_local(root, "Concepto"):
        out.append(
            ConceptoCfdi(
                clave_prod_serv=_attr(c, "ClaveProdServ"),
                descripcion=_attr(c, "Descripcion"),
                cantidad=_to_float(_attr(c, "Cantidad")),
                clave_unidad=_attr(c, "ClaveUnidad"),
                unidad=_attr(c, "Unidad"),
                valor_unitario=_to_float(_attr(c, "ValorUnitario")),
                importe=_to_float(_attr(c, "Importe")),
                descuento=_to_float(_attr(c, "Descuento")),
            )
        )
    return out


def _extraer_pagos(root) -> Optional[DatosPago]:
    """Si hay complemento `pago:Pagos`/`Pagos`, extrae el primer `Pago`."""
    pagos_root = _find_local(root, "Pagos")
    if pagos_root is None:
        return None
    pago = _find_local(pagos_root, "Pago")
    if pago is None:
        return None

    docs = []
    for dr in _findall_local(pago, "DoctoRelacionado"):
        docs.append(
            DocumentoRelacionado(
                id_documento=_attr(dr, "IdDocumento"),
                serie=_attr(dr, "Serie"),
                folio=_attr(dr, "Folio"),
                moneda_dr=_attr(dr, "MonedaDR"),
                metodo_de_pago_dr=_attr(dr, "MetodoDePagoDR"),
                num_parcialidad=_to_int(_attr(dr, "NumParcialidad")),
                imp_saldo_ant=_to_float(_attr(dr, "ImpSaldoAnt")),
                imp_pagado=_to_float(_attr(dr, "ImpPagado")),
                imp_saldo_insoluto=_to_float(_attr(dr, "ImpSaldoInsoluto")),
            )
        )

    return DatosPago(
        fecha_pago=_attr(pago, "FechaPago"),
        forma_de_pago=_attr(pago, "FormaDePagoP"),
        moneda_pago=_attr(pago, "MonedaP"),
        monto_pago=_to_float(_attr(pago, "Monto")),
        documentos_relacionados=docs,
    )


def _find_child_local(parent, local_name: str):
    """Primer hijo directo (no descendiente) con local-name = local_name."""
    if parent is None:
        return None
    for child in parent:
        if etree.QName(child).localname == local_name:
            return child
    return None


def _findall_child_local(parent, local_name: str) -> list:
    """Hijos directos con local-name = local_name."""
    if parent is None:
        return []
    return [c for c in parent if etree.QName(c).localname == local_name]


def _extraer_trabajador_nomina(nomina) -> dict:
    """Receptor del complemento (datos del trabajador)."""
    receptor = _find_child_local(nomina, "Receptor")
    if receptor is None:
        return {}
    return {
        "curp": _attr(receptor, "Curp"),
        "nss": _attr(receptor, "NumSeguridadSocial"),
        "num_empleado": _attr(receptor, "NumEmpleado"),
        "puesto": _attr(receptor, "Puesto"),
        "departamento": _attr(receptor, "Departamento"),
        "tipo_contrato": _attr(receptor, "TipoContrato"),
        "tipo_regimen": _attr(receptor, "TipoRegimen"),
        "tipo_jornada": _attr(receptor, "TipoJornada"),
        "periodicidad_pago": _attr(receptor, "PeriodicidadPago"),
        "fecha_inicio_rel_laboral": _attr(receptor, "FechaInicioRelLaboral"),
        "antiguedad": _attr(receptor, "Antigüedad") or _attr(receptor, "Antiguedad"),
        "salario_base_cot_apor": _to_float(_attr(receptor, "SalarioBaseCotApor")),
        "salario_diario_integrado": _to_float(_attr(receptor, "SalarioDiarioIntegrado")),
        "riesgo_trabajo": _attr(receptor, "RiesgoTrabajo"),
        "banco": _attr(receptor, "Banco"),
        "cuenta_bancaria": _attr(receptor, "CuentaBancaria"),
        "sindicalizado": _attr(receptor, "Sindicalizado"),
        "clave_ent_fed": _attr(receptor, "ClaveEntFed"),
    }


def _extraer_emisor_complemento(nomina) -> dict:
    """Emisor del complemento (patrón)."""
    emisor = _find_child_local(nomina, "Emisor")
    if emisor is None:
        return {}
    return {"registro_patronal": _attr(emisor, "RegistroPatronal")}


def _extraer_percepciones(nomina) -> list[ConceptoNomina]:
    nodo = _find_child_local(nomina, "Percepciones")
    if nodo is None:
        return []
    out: list[ConceptoNomina] = []
    for item in _findall_child_local(nodo, "Percepcion"):
        out.append(
            ConceptoNomina(
                clase="Percepcion",
                tipo_concepto=_attr(item, "TipoPercepcion"),
                clave_interna=_attr(item, "Clave"),
                concepto=_attr(item, "Concepto"),
                importe_gravado=_to_float(_attr(item, "ImporteGravado")),
                importe_exento=_to_float(_attr(item, "ImporteExento")),
                importe=0.0,
                subsidio_causado=0.0,
            )
        )
    return out


def _extraer_deducciones(nomina) -> list[ConceptoNomina]:
    nodo = _find_child_local(nomina, "Deducciones")
    if nodo is None:
        return []
    out: list[ConceptoNomina] = []
    for item in _findall_child_local(nodo, "Deduccion"):
        out.append(
            ConceptoNomina(
                clase="Deduccion",
                tipo_concepto=_attr(item, "TipoDeduccion"),
                clave_interna=_attr(item, "Clave"),
                concepto=_attr(item, "Concepto"),
                importe_gravado=0.0,
                importe_exento=0.0,
                importe=_to_float(_attr(item, "Importe")),
                subsidio_causado=0.0,
            )
        )
    return out


def _extraer_otros_pagos(nomina) -> list[ConceptoNomina]:
    nodo = _find_child_local(nomina, "OtrosPagos")
    if nodo is None:
        return []
    out: list[ConceptoNomina] = []
    for item in _findall_child_local(nodo, "OtroPago"):
        tipo = _attr(item, "TipoOtroPago")
        subsidio = 0.0
        # Subsidio al Empleo (tipo 002) tiene sub-elemento `SubsidioAlEmpleo`
        # con atributo `SubsidioCausado`.
        if tipo == "002":
            sub = _find_child_local(item, "SubsidioAlEmpleo")
            if sub is not None:
                subsidio = _to_float(_attr(sub, "SubsidioCausado"))
        out.append(
            ConceptoNomina(
                clase="OtroPago",
                tipo_concepto=tipo,
                clave_interna=_attr(item, "Clave"),
                concepto=_attr(item, "Concepto"),
                importe_gravado=0.0,
                importe_exento=0.0,
                importe=_to_float(_attr(item, "Importe")),
                subsidio_causado=subsidio,
            )
        )
    return out


def _extraer_nomina(root) -> Optional[DatosNomina]:
    """Si hay complemento `nomina12:Nomina`/`Nomina`, extrae todos sus campos."""
    nomina = _find_local(root, "Nomina")
    if nomina is None:
        return None

    trabajador = _extraer_trabajador_nomina(nomina)
    emisor = _extraer_emisor_complemento(nomina)

    conceptos: list[ConceptoNomina] = []
    conceptos.extend(_extraer_percepciones(nomina))
    conceptos.extend(_extraer_deducciones(nomina))
    conceptos.extend(_extraer_otros_pagos(nomina))

    return DatosNomina(
        registro_patronal=emisor.get("registro_patronal", ""),
        curp=trabajador.get("curp", ""),
        nss=trabajador.get("nss", ""),
        num_empleado=trabajador.get("num_empleado", ""),
        puesto=trabajador.get("puesto", ""),
        departamento=trabajador.get("departamento", ""),
        tipo_contrato=trabajador.get("tipo_contrato", ""),
        tipo_regimen=trabajador.get("tipo_regimen", ""),
        tipo_jornada=trabajador.get("tipo_jornada", ""),
        periodicidad_pago=trabajador.get("periodicidad_pago", ""),
        fecha_inicio_rel_laboral=trabajador.get("fecha_inicio_rel_laboral", ""),
        antiguedad=trabajador.get("antiguedad", ""),
        salario_base_cot_apor=trabajador.get("salario_base_cot_apor", 0.0),
        salario_diario_integrado=trabajador.get("salario_diario_integrado", 0.0),
        riesgo_trabajo=trabajador.get("riesgo_trabajo", ""),
        banco=trabajador.get("banco", ""),
        cuenta_bancaria=trabajador.get("cuenta_bancaria", ""),
        sindicalizado=trabajador.get("sindicalizado", ""),
        clave_ent_fed=trabajador.get("clave_ent_fed", ""),
        tipo_nomina=_attr(nomina, "TipoNomina"),
        fecha_pago=_attr(nomina, "FechaPago"),
        fecha_inicial_pago=_attr(nomina, "FechaInicialPago"),
        fecha_final_pago=_attr(nomina, "FechaFinalPago"),
        num_dias_pagados=_to_float(_attr(nomina, "NumDiasPagados")),
        total_percepciones=_to_float(_attr(nomina, "TotalPercepciones")),
        total_deducciones=_to_float(_attr(nomina, "TotalDeducciones")),
        total_otros_pagos=_to_float(_attr(nomina, "TotalOtrosPagos")),
        conceptos=conceptos,
    )


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


class CfdiParseError(ValueError):
    """Indica que el XML no es un CFDI válido."""


def parse_cfdi(xml_content: Union[str, bytes], file_name: str = "") -> CfdiData:
    """
    Parsea un CFDI desde string o bytes y devuelve un `CfdiData` con todos los
    campos extraídos. Lanza `CfdiParseError` si el XML no es válido.
    """
    if isinstance(xml_content, str):
        xml_content = xml_content.encode("utf-8")

    try:
        root = fromstring_seguro(xml_content)
    except etree.XMLSyntaxError as e:
        raise CfdiParseError(f"XML inválido: {e}") from e

    if _local(root) != "Comprobante":
        raise CfdiParseError(
            f"No es un CFDI: elemento raíz '{_local(root)}' (esperado 'Comprobante')"
        )

    # Cabecera del Comprobante
    data = CfdiData(file_name=file_name)
    data.version = _attr(root, "Version") or _attr(root, "version")
    data.tipo_comprobante = _attr(root, "TipoDeComprobante")
    data.fecha_emision = _attr(root, "Fecha")
    data.serie = _attr(root, "Serie")
    data.folio = _attr(root, "Folio")
    data.sub_total = _to_float(_attr(root, "SubTotal"))
    data.descuento = _to_float(_attr(root, "Descuento"))
    data.total = _to_float(_attr(root, "Total"))
    data.moneda = _attr(root, "Moneda") or "MXN"
    data.tipo_cambio = _to_float(_attr(root, "TipoCambio"), default=1.0)
    data.forma_pago = _attr(root, "FormaPago")
    data.metodo_pago = _attr(root, "MetodoPago")
    data.lugar_expedicion = _attr(root, "LugarExpedicion")

    # Emisor
    emisor = _find_local(root, "Emisor")
    if emisor is not None:
        data.emisor_rfc = _attr(emisor, "Rfc") or _attr(emisor, "rfc")
        data.emisor_nombre = _attr(emisor, "Nombre") or _attr(emisor, "nombre")
        data.emisor_regimen_fiscal = _attr(emisor, "RegimenFiscal")

    # Receptor
    receptor = _find_local(root, "Receptor")
    if receptor is not None:
        data.receptor_rfc = _attr(receptor, "Rfc") or _attr(receptor, "rfc")
        data.receptor_nombre = _attr(receptor, "Nombre") or _attr(receptor, "nombre")
        data.receptor_uso_cfdi = _attr(receptor, "UsoCFDI")

    # Timbre Fiscal
    uuid, fecha_timbrado = _extraer_timbre_fiscal(root)
    data.uuid = uuid
    data.fecha_timbrado = fecha_timbrado

    # Impuestos
    iva_trasladado, ieps_trasladado, iva_retenido, isr_retenido = _extraer_impuestos(root)
    data.iva_trasladado = iva_trasladado
    data.ieps_trasladado = ieps_trasladado
    data.iva_retenido = iva_retenido
    data.isr_retenido = isr_retenido

    # Conceptos
    data.conceptos = _extraer_conceptos(root)

    # Complemento Pagos (solo tipo P)
    if data.tipo_comprobante == "P":
        data.datos_pago = _extraer_pagos(root)

    # Complemento Nómina 1.2 (solo tipo N)
    if data.tipo_comprobante == "N":
        data.datos_nomina = _extraer_nomina(root)

    return data

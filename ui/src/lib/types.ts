// ---------------------------------------------------------------------------
// Types mirroring the Python Pydantic models in sat_descarga/server.py
// ---------------------------------------------------------------------------

// GET /health
export interface HealthResponse {
  status: string;
  rfc_cargado: string | null;
  efirma_lista: boolean;
  /** Vencimiento de la e.firma en sesión ("YYYY-MM-DD") o null si no hay. */
  efirma_vencimiento?: string | null;
  /** True/false si hay e.firma cargada; null si no hay. */
  efirma_vigente?: boolean | null;
}

// POST /auth/cargar-fiel
export interface CargarFielResponse {
  ok: boolean;
  rfc: string;
  numero_serie: string;
}

// DELETE /auth/fiel
export interface DescargarFielResponse {
  ok: boolean;
  mensaje: string;
}

// POST /solicitar — request body
export interface SolicitudRequest {
  fecha_inicio: string; // ISO date "YYYY-MM-DD"
  fecha_fin: string;
  tipo_solicitud: string; // "CFDI" | "Metadata"
  tipo_comprobante: string; // "E" | "R"
  rfc_emisor?: string;
  rfc_receptor?: string;
}

// POST /solicitar — response
export interface SolicitudResponse {
  ok: boolean;
  id_solicitud: string;
}

// POST /verificar — request body
export interface VerificarRequest {
  id_solicitud: string;
  poll: boolean;
}

// POST /verificar — response
export interface VerificarResponse {
  cod_estado: number;
  mensaje: string;
  numero_cfdis: number;
  package_ids: string[];
  terminada: boolean;
}

// POST /descargar — response
export interface DescargarResponse {
  ok: boolean;
  archivos: string[];
  total: number;
  mensaje?: string;
}

// POST /descarga-completa — request body
export interface DescargaCompletaRequest {
  fecha_inicio: string;
  fecha_fin: string;
  tipo_comprobante: string;
  directorio_salida: string;
  extraer: boolean;
}

// POST /solicitar-folio — request body
export interface SolicitudFolioRequest {
  uuids: string[];
  tipo_solicitud: string;
  directorio_salida: string;
  extraer: boolean;
}

// POST /organizar (planned endpoint — models match organizador.py)
export interface OrganizadorRequest {
  origen: string;
  destino: string;
  estructura: string;
  copiar: boolean;
}

export interface OrganizadorResult {
  archivos_procesados: number;
  archivos_movidos: number;
  archivos_omitidos: number;
  errores: string[];
}

// POST /renombrar (planned endpoint — models match organizador.py)
export interface RenombrarRequest {
  directorio: string;
  patron: string;
}

// POST /deduplicar (planned endpoint — models match organizador.py)
export interface DeduplicarRequest {
  directorio: string;
  dry_run: boolean;
}

export interface DeduplicarResult {
  archivos_analizados: number;
  duplicados_encontrados: number;
  duplicados_eliminados: number;
  errores: string[];
}

// CIEC (portal web scraping)
export interface CIECDescargaRequest {
  rfc: string;
  ciec: string;
  fecha_inicio: string;
  fecha_fin: string;
  tipo_comprobante: string;
  directorio_salida: string;
  max_registros: number;
}

// Descarga inteligente (auto-routing CIEC vs Web Service)
export interface DescargaInteligente {
  fecha_inicio: string;
  fecha_fin: string;
  tipo_comprobante: string;
  directorio_salida: string;
  ciec?: string;
  umbral_ciec?: number;
}

// ---------------------------------------------------------------------------
// Jobs CIEC (captcha in-app por SSE) — agente desktop
// ---------------------------------------------------------------------------

export type JobEstado =
  | 'pending'
  | 'running'
  | 'captcha'
  | 'done'
  | 'error'
  | 'cancelled';

// POST /ciec/cfdi (el agente computa el directorio de salida).
// `ciec` es opcional: si falta, el agente la toma del catálogo (keychain).
export interface CiecCfdiRequest {
  rfc: string;
  ciec?: string;
  fecha_inicio: string;
  fecha_fin: string;
  tipo_comprobante?: string;
  max_registros?: number;
}

// POST /ciec/constancia y /ciec/opinion (`ciec` opcional → del catálogo)
export interface CiecDocRequest {
  rfc: string;
  ciec?: string;
}

// POST /cfdi/fiel — descarga CFDIs vía portal con la e.firma en sesión.
// Sin rfc/credenciales: las toma de _get_fiel() del agente.
export interface CfdiFielRequest {
  fecha_inicio: string;
  fecha_fin: string;
  tipo_comprobante?: string;
  max_registros?: number;
}

// Respuesta al iniciar cualquier job (/ciec/*)
export interface JobIniciado {
  job_id: string;
}

// GET /jobs/{id}
export interface JobEstadoResponse {
  id: string;
  estado: JobEstado;
  resultado: unknown;
  error: string | null;
}

// Evento del stream SSE GET /events/{id}
export interface JobEvent {
  event:
    | 'estado'
    | 'captcha_required'
    | 'captcha_timeout'
    | 'done'
    | 'error'
    | 'cancelled'
    | string;
  estado?: string; // event=estado
  imagen?: string; // event=captcha_required (data:image/jpeg;base64,...)
  intento?: number;
  max?: number;
  resultado?: unknown; // event=done
  mensaje?: string; // event=error|cancelled
}

// ---------------------------------------------------------------------------
// Empresas (catálogo persistente del agente; credenciales en keychain del SO)
// ---------------------------------------------------------------------------

export type MetodoEmpresa = 'fiel' | 'ciec';

export interface RegimenFiscalConfig {
  clave: string;
  descripcion: string;
}

export interface ActividadEconomicaConfig {
  descripcion: string;
  principal?: boolean;
}

// GET /empresas → { empresas: Empresa[] }
export interface Empresa {
  rfc: string;
  nombre: string;
  /** Métodos de autenticación disponibles (una empresa puede tener ambos). */
  metodos: MetodoEmpresa[];
  cer_path?: string | null;
  vencimiento?: string;
  default: boolean;
  /** ISO timestamp si está archivada (soft-delete); null/undefined = activa. */
  archived_at?: string | null;
  /** Path local de la última Constancia de Situación Fiscal descargada. */
  csf_path?: string | null;
  csf_descargada_en?: string | null;
  /** Path local de la última Opinión de Cumplimiento 32-D descargada. */
  opinion_path?: string | null;
  opinion_descargada_en?: string | null;
  /** Régimen(es) fiscal(es) declarados. Por ahora se llenan a mano; eventualmente
   * desde el parser de CSF. */
  regimenes_fiscales?: RegimenFiscalConfig[];
  /** Actividades económicas — descripción libre + marca opcional de la principal. */
  actividades_economicas?: ActividadEconomicaConfig[];
}

export interface EmpresaUpdatePatch {
  regimenes_fiscales?: RegimenFiscalConfig[];
  actividades_economicas?: ActividadEconomicaConfig[];
}

export interface EmpresasResponse {
  empresas: Empresa[];
}

// POST /empresas/ciec
export interface EmpresaCiecRequest {
  rfc: string;
  nombre: string;
  ciec: string;
}

// POST /empresas/{rfc}/activar
export interface ActivarEmpresaResponse {
  ok: boolean;
  rfc: string;
  metodos: MetodoEmpresa[];
  efirma_lista: boolean;
}

// GET /empresas/{rfc}/solicitudes (Historial)
export interface Solicitud {
  id_solicitud: string;
  fecha_inicio: string;
  fecha_fin: string;
  tipo: string;            // Etiqueta humana "CFDI · emitidos" / "Metadata · recibidos"
  estado: string;          // "solicitada" / "1"-"5" (SAT) / "descargada"
  timestamp: string;       // Creada (ISO local)
  package_ids?: string[];  // Disponibles cuando estado="3"+
  tipo_comprobante?: string;  // "E" / "R" — usado por el agente para componer la carpeta de salida
  mensaje?: string;        // Mensaje del SAT en la última /verificar
  numero_cfdis?: number;   // CFDIs reportados por el SAT
}

export interface SolicitudesResponse {
  solicitudes: Solicitud[];
}

// ---------------------------------------------------------------------------
// Historial de descargas completadas (GET /historial y /empresas/{rfc}/historial)
// ---------------------------------------------------------------------------

export type CanalDescarga = 'ws' | 'ciec' | 'fiel';
export type TipoDescarga = 'cfdi' | 'metadata' | 'constancia' | 'opinion';

export interface HistorialItem {
  timestamp: string; // ISO datetime
  canal: CanalDescarga;
  tipo: TipoDescarga;
  descripcion: string;
  ruta: string;
  total: number | null; // nº de CFDIs cuando aplica
  estado: string; // "completada" | ...
  // Presentes en /historial (todas las empresas); ausentes en el por-empresa.
  rfc?: string;
  nombre?: string;
}

export interface HistorialResponse {
  descargas: HistorialItem[];
}

// {ok, archivo} — descarga de un PDF (constancia/opinión vía e.firma)
export interface DocumentoResponse {
  ok: boolean;
  archivo: string;
}

// Generic API error shape
export interface ApiErrorDetail {
  detail: string;
}

// ---------------------------------------------------------------------------
// Procesador de comprobantes — CFDI
// ---------------------------------------------------------------------------

export type CfdiTipo = 'I' | 'E' | 'T' | 'N' | 'P';

export interface CfdiFiltros {
  desde: string | null;
  hasta: string | null;
  tipo: CfdiTipo | null;
  /**
   * Dirección del CFDI relativa a la empresa activa:
   * - 'E' = "yo soy emisor"  (los receptores son mis clientes)
   * - 'R' = "yo soy receptor" (los emisores son mis proveedores)
   * - null = ambos
   * Se calcula al cargar comparando emisor/receptor con el RFC activo.
   */
  direccion: 'E' | 'R' | null;
  busqueda: string | null;
  solo_con_errores: boolean;
  monto_min: number | null;
  monto_max: number | null;
  /**
   * Filtro por estado del emisor en listas negras:
   * 'EFOS' | 'Aclarado' | '69' | 'Limpio' | 'SinValidar' | null
   * Espejo de la columna `cfdis.emisor_en_lista_negra` (migración 006).
   */
  emisor_lista_negra?: string | null;
}

export interface CfdiRecord {
  uuid: string;
  file_name: string | null;
  version: string | null;
  tipo: CfdiTipo | string;
  fecha: string;
  fecha_timbrado: string | null;
  serie: string | null;
  folio: string | null;
  emisor_rfc: string;
  emisor_nombre: string;
  emisor_regimen_fiscal: string | null;
  receptor_rfc: string;
  receptor_nombre: string;
  receptor_uso_cfdi: string | null;
  sub_total: number;
  descuento: number;
  total: number;
  iva_trasladado: number;
  ieps_trasladado: number;
  iva_retenido: number;
  isr_retenido: number;
  forma_pago: string | null;
  metodo_pago: string | null;
  moneda: string;
  tipo_cambio: number;
  lugar_expedicion: string | null;
  direccion: 'E' | 'R' | null;
  estado_sat: 'Vigente' | 'Cancelado' | 'No encontrado' | null;
  validado_en: string | null;
  /**
   * Etiqueta del emisor en listas negras del SAT (Art. 69 y 69-B).
   * 'EFOS' | 'Aclarado' | '69' | 'Limpio' | null (sin validar).
   * Espejo de la columna `cfdis.emisor_en_lista_negra` (migración 006).
   */
  emisor_en_lista_negra: string | null;
  /** JSON serializado con el detalle del match (situación, supuestos, fecha pub.). */
  emisor_listas_match: string | null;
  receptor_en_lista_negra: string | null;
  receptor_listas_match: string | null;
  validado_listas_en: string | null;
  warnings: string[];
  cargado_en: string;
}

export interface CfdiListResponse {
  total: number;
  page: number;
  page_size: number;
  items: CfdiRecord[];
}

export interface CfdiStats {
  total_comprobantes: number;        // respeta filtros activos
  total_global: number;              // count global SIN filtros — para detectar "buffer vacío"
  monto_total: number;
  iva_trasladado: number;
  ieps_trasladado: number;
  iva_retenido: number;
  isr_retenido: number;
  con_errores: number;
  por_tipo: Record<string, number>;
}

export interface ReporteTotalesMes {
  reporte: 'totales-mes';
  items: {
    mes: string;
    comprobantes: number;
    sub_total: number;
    iva_trasladado: number;
    ieps_trasladado: number;
    iva_retenido: number;
    isr_retenido: number;
    total: number;
  }[];
}

export interface TopContraparte {
  rfc: string;
  nombre: string;
  comprobantes: number;
  monto: number;
}

export interface ReporteTopContrapartes {
  reporte: 'top-contrapartes';
  emisores: TopContraparte[];
  receptores: TopContraparte[];
}

export interface ItemIntegridad {
  uuid: string;
  tipo: string;
  fecha: string;
  serie: string | null;
  folio: string | null;
  emisor_rfc: string;
  emisor_nombre: string;
  receptor_rfc: string;
  receptor_nombre: string;
  total: number;
  warnings: string[];
}

export interface ReporteIntegridad {
  reporte: 'integridad';
  items: ItemIntegridad[];
}

export interface ProcesadorCargarResponse {
  agregados: number;
  duplicados: number;
  errores: { filename: string; mensaje: string }[];
  archivos_encontrados?: number; // solo en cargar-desde-empresa
}

export interface CargarDesdeEmpresaRequest {
  rfc: string;
  desde?: string;
  hasta?: string;
  /** 'E' (emitidos) o 'R' (recibidos). Reservado para uso programático
   *  futuro (calculadoras IVA, etc.) omitirlo para escanear ambos. */
  tipo?: 'E' | 'R';
}

export interface ValidarSatResponse {
  validados: number;
  vigentes: number;
  cancelados: number;
  no_encontrados: number;
  errores: number;
}

// ---------------------------------------------------------------------------
// Listas negras del SAT (Art. 69 y 69-B)
// ---------------------------------------------------------------------------

export interface ListaNegraMatch {
  rfc: string;
  en_lista_69b: boolean;
  /** Definitivo | Presunto | Desvirtuado | Sentencia Favorable | null */
  situacion_69b: string | null;
  fecha_publicacion_69b: string | null;
  en_lista_69: boolean;
  /** firmes | exigibles | no_localizados | sentencias | cancelados | entes_publicos_omisos */
  supuestos_69: string[];
  /** alto | medio | limpio */
  risk_level: string;
  error: string | null;
}

export interface ListasNegrasMetadata {
  lista_69b_updated_at: string | null;
  lista_69_updated_at: string | null;
  record_count_69b: number | null;
  record_count_69: number | null;
}

export interface ListasNegrasConsultarResponse {
  matches: ListaNegraMatch[];
  metadata: ListasNegrasMetadata;
}

export interface ProcesadorValidarListasNegrasResponse {
  validados: number;
  efos: number;
  aclarados: number;
  lista_69: number;
  limpios: number;
  metadata: ListasNegrasMetadata;
}

export interface ProcesadorListasNegrasStats {
  efos_emisores_unicos: number;
  cfdis_edos: number;
  cfdis_emisor_aclarado: number;
  cfdis_emisor_69: number;
  cfdis_limpios: number;
  cfdis_sin_validar: number;
}

// ---------------------------------------------------------------------------
// Procesador de comprobantes — Pagos
// ---------------------------------------------------------------------------

export type PagoStatus = 'sin_complemento' | 'pago_parcial' | 'pagado_completo' | 'sobrante';

export interface PagosFiltros {
  desde: string | null;
  hasta: string | null;
  busqueda: string | null;
  status: PagoStatus[] | null;
  solo_extemporaneos: boolean;
}

export interface PagosStats {
  total_ingresos_ppd: number;       // respeta filtros
  total_global_ppd: number;         // sin filtros — para detectar buffer vacío
  sin_complemento: number;
  pagos_parciales: number;
  pagos_completos: number;
  sobrantes: number;
  monto_total_sin_pagar: number;
  total_pagos: number;              // total CFDIs tipo P
  pagos_huerfanos: number;
  incidencias_pue: number;
  porcentaje_conciliados: number;
  complementos_extemporaneos: number;
  monto_complementos_extemporaneos: number;
}

export interface FacturaPPD {
  uuid: string;
  fecha: string;
  serie: string | null;
  folio: string | null;
  emisor_rfc: string;
  emisor_nombre: string;
  receptor_rfc: string;
  receptor_nombre: string;
  total: number;
  total_pagado: number;
  saldo_pendiente: number;
  num_pagos: number;
  moneda: string;
  estado_sat: 'Vigente' | 'Cancelado' | 'No encontrado' | null;
  status: PagoStatus;
  warnings: string[];
}

export interface FacturasPPDResponse {
  total: number;
  page: number;
  page_size: number;
  items: FacturaPPD[];
}

export interface PagoRelacionadoDetalle {
  cfdi_pago_uuid: string;
  fecha_emision_complemento: string;
  cfdi_pago_fecha_pago: string;
  cfdi_pago_forma: string | null;
  docto_num_parcialidad: number;
  docto_imp_saldo_ant: number;
  docto_imp_pagado: number;
  docto_imp_saldo_insoluto: number;
  docto_moneda: string | null;
  pago_emisor_rfc: string;
  pago_emisor_nombre: string;
}

export interface ReporteAnalisisFechas {
  reporte: 'analisis-fechas';
  items: {
    cfdi_pago_uuid: string;
    fecha_emision_complemento: string;
    cfdi_pago_fecha_pago: string;
    emisor_rfc: string;
    emisor_nombre: string;
    monto_complemento: number;
    limite: string;
    dias_retraso: number;
    factura_uuid: string;
    factura_folio: string | null;
  }[];
}

export interface ReportePagosHuerfanos {
  reporte: 'huerfanos';
  items: {
    cfdi_pago_uuid: string;
    fecha_emision: string;
    emisor_rfc: string;
    emisor_nombre: string;
    monto: number;
    documentos_referenciados: string | null; // pipe-separated UUIDs
  }[];
}

export interface ReporteIncidenciasPue {
  reporte: 'incidencias-pue';
  items: {
    factura_uuid: string | null;
    factura_fecha: string | null;
    emisor_rfc: string | null;
    emisor_nombre: string | null;
    factura_total: number | null;
    factura_metodo_pago: string | null;
    complemento_uuid: string;
    cfdi_pago_fecha_pago: string;
    monto_pagado: number;
    docto_metodo_pago: string | null;
    descripcion_riesgo: string;
  }[];
}

// ---------------------------------------------------------------------------
// Procesador de comprobantes — Nómina
// ---------------------------------------------------------------------------

export type TipoNomina = 'O' | 'E';
export type ClaseConcepto = 'Percepcion' | 'Deduccion' | 'OtroPago';

export interface NominaFiltros {
  desde: string | null;
  hasta: string | null;
  busqueda: string | null;
  tipo_nomina: TipoNomina | null;
  periodicidad: string | null;
  solo_con_errores: boolean;
}

export interface NominaStats {
  total_recibos: number;           // respeta filtros
  total_global_recibos: number;    // sin filtros — empty state
  total_empleados: number;
  total_conceptos: number;
  nominas_ordinarias: number;
  nominas_extraordinarias: number;
  total_percepciones: number;
  total_deducciones: number;
  total_otros_pagos: number;
  neto_a_pagar: number;
  conceptos_con_errores: number;
}

export interface NominaRecibo {
  cfdi_uuid: string;
  fecha: string;                   // fecha del CFDI
  fecha_pago: string;
  fecha_inicial_pago: string;
  fecha_final_pago: string;
  emisor_rfc: string;
  emisor_nombre: string;
  receptor_rfc: string;
  receptor_nombre: string;
  registro_patronal: string | null;
  curp: string | null;
  nss: string | null;
  num_empleado: string | null;
  puesto: string | null;
  departamento: string | null;
  tipo_contrato: string | null;
  tipo_regimen: string | null;
  tipo_jornada: string | null;
  periodicidad_pago: string | null;
  fecha_inicio_rel_laboral: string | null;
  antiguedad: string | null;
  salario_base_cot_apor: number;
  salario_diario_integrado: number;
  riesgo_trabajo: string | null;
  banco: string | null;
  cuenta_bancaria: string | null;
  sindicalizado: string | null;
  clave_ent_fed: string | null;
  tipo_nomina: TipoNomina | null;
  num_dias_pagados: number;
  total_percepciones: number;
  total_deducciones: number;
  total_otros_pagos: number;
  neto: number;
  estado_sat: 'Vigente' | 'Cancelado' | 'No encontrado' | null;
  warnings: string[];
}

export interface NominaRecibosResponse {
  total: number;
  page: number;
  page_size: number;
  items: NominaRecibo[];
}

export interface NominaConceptoDetalle {
  clase: ClaseConcepto;
  tipo_concepto: string;
  clave_interna: string | null;
  concepto: string | null;
  importe_gravado: number;
  importe_exento: number;
  importe: number;
  subsidio_causado: number;
}

export interface EmployeeIsrBreakdown {
  rfc: string;
  nombre: string;
  percepciones_gravadas: number;
  isr_retenido: number;
  isr_teorico: number;
  diferencia: number;
  periodicidad: string;
  periodos_detectados: number;
  meses_detectados: number;
  advertencia_periodo: string | null;
}

export interface IsrAnalisis {
  year_detected: number;
  tarifa_label: string;
  isr_bruto: number;
  subsidio_aplicado: number;
  isr_teorico: number;
  isr_diferencia: number;
  limite_spe: number;
  aplica_spe: boolean;
}

export interface ReporteDeducibilidad {
  reporte: 'deducibilidad';
  periodo_inicio: string;
  periodo_fin: string;
  total_percepciones: number;
  percepciones_gravadas: number;
  percepciones_exentas: number;
  total_deducciones: number;
  seguro_social: number;
  isr_retenido: number;
  aportaciones_retiro_cesantia: number;
  otros_deducciones: number;
  salario_neto: number;
  isr_analisis: IsrAnalisis;
  empleados_analizados: number;
  desglose_por_empleado: EmployeeIsrBreakdown[];
  advertencias_periodo: string[];
  recomendaciones: string[];
  detalle_analisis: {
    cumplimiento_retenciones: string;
    adecuacion_fiscal: string;
    observaciones: string[];
  };
}

export interface ImssRegistro {
  rfc: string;
  nss: string;
  nombre: string;
  fechas_registro: string[];
  salario_base_cot_apor: number;
  salario_diario_integrado: number;
  dias_trabajados: number;
  aportaciones_patronal: number;
  aportaciones_obrero: number;
  seguro_social: number;
  tipo_regimen: string;
  riesgo_trabajo: string;
  observaciones: string[];
}

export interface ReporteImss {
  reporte: 'imss';
  periodo_inicio: string;
  periodo_fin: string;
  total_empleados: number;
  registros: ImssRegistro[];
  totales: {
    suma_sbc: number;
    suma_dias: number;
    suma_aportaciones_patronal: number;
    suma_aportaciones_obrero: number;
    suma_seguro_social: number;
  };
  alertas: {
    empleados_sin_nss: string[];
    sbc_fuera_limites: string[];
    dias_anomalous: string[];
  };
}

export interface PeriodoVariaciones {
  empleados_variacion: number;
  empleados_variacion_pct: number;
  percepciones_variacion: number;
  percepciones_variacion_pct: number;
  deducciones_variacion: number;
  deducciones_variacion_pct: number;
  empleados_nuevos: string[];
  empleados_eliminados: string[];
  conceptos_nuevos: string[];
  conceptos_eliminados: string[];
}

export interface PeriodoMetricas {
  inicio: string;
  fin: string;
  total_empleados: number;
  total_percepciones: number;
  total_deducciones: number;
  promedio_por_empleado: number;
}

export interface ReportePeriodoVsPeriodo {
  reporte: 'periodo-vs-periodo';
  insuficiente: boolean;
  mensaje_insuficiente: string | null;
  periodo_previo: PeriodoMetricas | null;
  periodo_actual: PeriodoMetricas | null;
  variaciones: PeriodoVariaciones | null;
  analisis_detallado: {
    tendencia: string;
    observaciones: string[];
  } | null;
}

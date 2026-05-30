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

// POST /validar — request body
export interface CfdiValidarInput {
  uuid: string;
  emisor_rfc: string;
  receptor_rfc: string;
  total: number;
}

export interface ValidarRequest {
  cfdis: CfdiValidarInput[];
  concurrency?: number;
}

export interface ValidarResult {
  uuid: string;
  estado: string;
  es_cancelable: string | null;
  estatus_cancelacion: string | null;
  validacion_efos: string | null;
  error: string | null;
}

export interface ValidarResponse {
  results: ValidarResult[];
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

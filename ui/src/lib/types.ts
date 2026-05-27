// ---------------------------------------------------------------------------
// Types mirroring the Python Pydantic models in sat_descarga/server.py
// ---------------------------------------------------------------------------

// GET /health
export interface HealthResponse {
  status: string;
  rfc_cargado: string | null;
  efirma_lista: boolean;
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

// POST /metadata — uses SolicitudRequest body, returns MetadataResponse

export interface MetadataRecord {
  uuid: string;
  rfc_emisor: string;
  nombre_emisor: string;
  rfc_receptor: string;
  nombre_receptor: string;
  rfc_pac: string;
  fecha_emision: string;
  fecha_certificacion: string;
  monto: string;
  efecto_comprobante: string;
  estatus: string;
  fecha_cancelacion: string;
}

export interface MetadataResponse {
  ok: boolean;
  total: number;
  records: MetadataRecord[];
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

// POST /ciec/cfdi (el agente computa el directorio de salida)
export interface CiecCfdiRequest {
  rfc: string;
  ciec: string;
  fecha_inicio: string;
  fecha_fin: string;
  tipo_comprobante?: string;
  max_registros?: number;
}

// POST /ciec/constancia y /ciec/opinion
export interface CiecDocRequest {
  rfc: string;
  ciec: string;
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

// GET /empresas → { empresas: Empresa[] }
export interface Empresa {
  rfc: string;
  nombre: string;
  metodo: MetodoEmpresa;
  cer_path?: string | null;
  vencimiento?: string;
  default: boolean;
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
  metodo: MetodoEmpresa;
  efirma_lista: boolean;
}

// GET /empresas/{rfc}/solicitudes (Historial)
export interface Solicitud {
  id_solicitud: string;
  fecha_inicio: string;
  fecha_fin: string;
  tipo: string;
  estado: string;
  timestamp: string;
  package_ids?: string[];
}

export interface SolicitudesResponse {
  solicitudes: Solicitud[];
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

// ---------------------------------------------------------------------------
// Constants for the SAT Descarga Masiva UI
// ---------------------------------------------------------------------------

/**
 * Base URL for the Python FastAPI server.
 * Falls back to localhost:8787 when no env var is set.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_SAT_API_URL ?? 'http://localhost:8787';

/**
 * Base URL efectiva del agente. Dentro de Electron, el preload inyecta
 * `window.satAgent.baseUrl` (puerto efímero); en el navegador cae a API_BASE_URL.
 */
export function getAgentBaseUrl(): string {
  if (typeof window !== 'undefined') {
    const injected = (window as unknown as { satAgent?: { baseUrl?: string } }).satAgent?.baseUrl;
    if (injected) return injected;
  }
  return API_BASE_URL;
}

// ---------------------------------------------------------------------------
// CodEstado labels (VerificaSolicitud response states)
// ---------------------------------------------------------------------------

export interface CodEstadoInfo {
  label: string;
  color: string;
  description: string;
}

export const COD_ESTADO_LABELS: Map<number, CodEstadoInfo> = new Map([
  [
    1,
    {
      label: 'En cola',
      color: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400',
      description: 'La solicitud fue recibida y está en espera de procesamiento.',
    },
  ],
  [
    2,
    {
      label: 'Procesando',
      color: 'bg-blue-100 text-blue-800 dark:bg-blue-900/30 dark:text-blue-400',
      description: 'El SAT está procesando la solicitud.',
    },
  ],
  [
    3,
    {
      label: 'Lista',
      color: 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
      description: 'Los paquetes están listos para descargar.',
    },
  ],
  [
    4,
    {
      label: 'Error',
      color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      description: 'Ocurrió un error en el servidor del SAT.',
    },
  ],
  [
    5,
    {
      label: 'Rechazada',
      color: 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
      description: 'La solicitud fue rechazada por el SAT.',
    },
  ],
]);

// ---------------------------------------------------------------------------
// Folder structure patterns (from organizador.py ESTRUCTURAS)
// ---------------------------------------------------------------------------

export const ESTRUCTURAS = [
  { value: 'rfc_emisor/anio/mes', label: 'RFC Emisor / Año / Mes' },
  { value: 'rfc_emisor/anio', label: 'RFC Emisor / Año' },
  { value: 'anio/mes/rfc_emisor', label: 'Año / Mes / RFC Emisor' },
  { value: 'anio/mes', label: 'Año / Mes' },
  { value: 'anio/mes/dia', label: 'Año / Mes / Día' },
  { value: 'tipo/anio/mes', label: 'Tipo / Año / Mes' },
  { value: 'rfc_emisor/tipo/anio/mes', label: 'RFC Emisor / Tipo / Año / Mes' },
  { value: 'rfc_receptor/anio/mes', label: 'RFC Receptor / Año / Mes' },
  { value: 'plano', label: 'Plano (sin subcarpetas)' },
] as const;

// ---------------------------------------------------------------------------
// Rename patterns (from organizador.py PATRONES_NOMBRE)
// ---------------------------------------------------------------------------

export const PATRONES_NOMBRE = [
  { value: 'emisor_fecha_total', label: 'Emisor - Fecha - Total' },
  { value: 'receptor_fecha_total', label: 'Receptor - Fecha - Total' },
  { value: 'uuid', label: 'UUID' },
  { value: 'fecha_emisor_total', label: 'Fecha - Emisor - Total' },
  { value: 'fecha_uuid', label: 'Fecha - UUID' },
] as const;

// ---------------------------------------------------------------------------
// Tipo de solicitud (download content type)
// ---------------------------------------------------------------------------

export const TIPO_SOLICITUD = [
  { value: 'CFDI', label: 'CFDI (XMLs completos)' },
  { value: 'Metadata', label: 'Metadata (resumen CSV)' },
] as const;

// ---------------------------------------------------------------------------
// Tipo de comprobante (emitido / recibido)
// ---------------------------------------------------------------------------

export const TIPO_COMPROBANTE = [
  { value: 'E', label: 'Emitidos' },
  { value: 'R', label: 'Recibidos' },
] as const;

// ---------------------------------------------------------------------------
// Estado del comprobante (for SolicitudRequest filters)
// ---------------------------------------------------------------------------

export const ESTADO_COMPROBANTE = [
  { value: 'Vigente', label: 'Vigente' },
  { value: 'Cancelado', label: 'Cancelado' },
  { value: 'Todos', label: 'Todos' },
] as const;

// ---------------------------------------------------------------------------
// Efecto del comprobante (from CFDI metadata)
// ---------------------------------------------------------------------------

export const EFECTO_COMPROBANTE: Record<string, string> = {
  I: 'Ingreso',
  E: 'Egreso',
  P: 'Pago',
  T: 'Traslado',
  N: 'Nómina',
};

// ---------------------------------------------------------------------------
// Polling intervals (mirroring sat_descarga/config.py)
// ---------------------------------------------------------------------------

export const HEALTH_POLL_INTERVAL_MS = 5_000;
export const VERIFICAR_POLL_INTERVAL_MS = 15_000;

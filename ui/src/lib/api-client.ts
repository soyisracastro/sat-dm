import { API_BASE_URL } from './constants';
import type {
  HealthResponse,
  CargarFielResponse,
  DescargarFielResponse,
  SolicitudRequest,
  SolicitudResponse,
  VerificarRequest,
  VerificarResponse,
  DescargarResponse,
  DescargaCompletaRequest,
  SolicitudFolioRequest,
  OrganizadorRequest,
  OrganizadorResult,
  RenombrarRequest,
  DeduplicarRequest,
  DeduplicarResult,
  CiecCfdiRequest,
  CiecDocRequest,
  CfdiFielRequest,
  JobIniciado,
  JobEstadoResponse,
  JobEvent,
  EmpresasResponse,
  EmpresaCiecRequest,
  EmpresaUpdatePatch,
  ActivarEmpresaResponse,
  SolicitudesResponse,
  HistorialResponse,
  DocumentoResponse,
  CfdiListResponse,
  CfdiStats,
  CfdiFiltros,
  CargarDesdeEmpresaRequest,
  ProcesadorCargarResponse,
  ReporteTotalesMes,
  ReporteTopContrapartes,
  ReporteIntegridad,
  ValidarSatResponse,
} from './types';

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`[${status}] ${detail}`);
    this.name = 'ApiError';
  }
}

// ---------------------------------------------------------------------------
// API Client
// ---------------------------------------------------------------------------

export class SatApiClient {
  private readonly baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = (baseUrl ?? API_BASE_URL).replace(/\/+$/, '');
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  private async request<T>(
    path: string,
    options: RequestInit = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;

    const res = await fetch(url, {
      ...options,
      headers: {
        ...(options.headers ?? {}),
      },
    });

    if (!res.ok) {
      let detail: string;
      try {
        const body = await res.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch {
        detail = await res.text().catch(() => res.statusText);
      }
      throw new ApiError(res.status, detail);
    }

    return res.json() as Promise<T>;
  }

  private async post<T>(
    path: string,
    body: Record<string, unknown> = {},
  ): Promise<T> {
    return this.request<T>(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  private async del<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' });
  }

  private async patch<T>(
    path: string,
    body: Record<string, unknown> = {},
  ): Promise<T> {
    return this.request<T>(path, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
  }

  /** URL absoluta para un path del agente (p. ej. para EventSource). */
  url(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  // -----------------------------------------------------------------------
  // Health
  // -----------------------------------------------------------------------

  async health(): Promise<HealthResponse> {
    return this.request<HealthResponse>('/health');
  }

  // -----------------------------------------------------------------------
  // Auth / e-firma
  // -----------------------------------------------------------------------

  /**
   * Upload the FIEL (e-firma) files to the local Python server.
   *
   * Uses FormData because the Python endpoint expects `UploadFile` + `Form`.
   */
  async cargarFiel(
    cerFile: File,
    keyFile: File,
    password: string,
  ): Promise<CargarFielResponse> {
    const formData = new FormData();
    formData.append('cer_file', cerFile);
    formData.append('key_file', keyFile);
    formData.append('password', password);

    return this.request<CargarFielResponse>('/auth/cargar-fiel', {
      method: 'POST',
      body: formData,
      // Do NOT set Content-Type — the browser sets the multipart boundary automatically.
    });
  }

  /**
   * Unload the FIEL from server memory and delete temporary files.
   */
  async descargarFiel(): Promise<DescargarFielResponse> {
    return this.request<DescargarFielResponse>('/auth/fiel', {
      method: 'DELETE',
    });
  }

  // -----------------------------------------------------------------------
  // Web Service: async flow
  // -----------------------------------------------------------------------

  /**
   * Step 1: Request a bulk download from the SAT.
   * Returns a RequestID to poll with `verificar`.
   */
  async solicitar(req: SolicitudRequest): Promise<SolicitudResponse> {
    return this.post<SolicitudResponse>('/solicitar', req as unknown as Record<string, unknown>);
  }

  /**
   * Step 2: Check the status of a download request.
   * When `cod_estado === 3` the packages are ready.
   */
  async verificar(req: VerificarRequest): Promise<VerificarResponse> {
    return this.post<VerificarResponse>('/verificar', req as unknown as Record<string, unknown>);
  }

  /**
   * Step 3: Download the packages for a completed request.
   *
   * Sin `directorioSalida` el agente usa la convención por empresa
   * (`<descargas>/cfdi/{RFC}/`), igual que CIEC.
   */
  async descargar(
    idSolicitud: string,
    directorioSalida?: string,
    extraer = true,
  ): Promise<DescargarResponse> {
    const params = new URLSearchParams({
      id_solicitud: idSolicitud,
      extraer: String(extraer),
    });
    if (directorioSalida) params.set('directorio_salida', directorioSalida);
    return this.request<DescargarResponse>(`/descargar?${params}`, {
      method: 'POST',
    });
  }

  /**
   * All-in-one: solicitar + poll + descargar in a single blocking call.
   * WARNING: Can block for hours for CFDI downloads.
   */
  async descargaCompleta(
    req: DescargaCompletaRequest,
  ): Promise<DescargarResponse> {
    return this.post<DescargarResponse>('/descarga-completa', req as unknown as Record<string, unknown>);
  }

  // -----------------------------------------------------------------------
  // Download by UUID
  // -----------------------------------------------------------------------

  /**
   * Download specific CFDIs by UUID.
   * Blocking: solicitar-folio + poll + descargar in one call.
   */
  async solicitarFolio(
    req: SolicitudFolioRequest,
  ): Promise<DescargarResponse> {
    return this.post<DescargarResponse>('/solicitar-folio', req as unknown as Record<string, unknown>);
  }

  // -----------------------------------------------------------------------
  // File tools (organizar, renombrar, deduplicar)
  // -----------------------------------------------------------------------

  /**
   * Organize XML files into a folder structure based on their content.
   */
  async organizar(req: OrganizadorRequest): Promise<OrganizadorResult> {
    return this.post<OrganizadorResult>('/organizar', req as unknown as Record<string, unknown>);
  }

  /**
   * Bulk-rename XML files based on their CFDI content.
   */
  async renombrar(req: RenombrarRequest): Promise<OrganizadorResult> {
    return this.post<OrganizadorResult>('/renombrar', req as unknown as Record<string, unknown>);
  }

  /**
   * Find and remove duplicate XML files (by UUID).
   */
  async deduplicar(req: DeduplicarRequest): Promise<DeduplicarResult> {
    return this.post<DeduplicarResult>('/deduplicar', req as unknown as Record<string, unknown>);
  }

  // -----------------------------------------------------------------------
  // Jobs CIEC (captcha in-app por SSE) — agente desktop
  // -----------------------------------------------------------------------

  /** Inicia una descarga de CFDIs vía CIEC. Devuelve { job_id }. */
  async ciecCfdi(req: CiecCfdiRequest): Promise<JobIniciado> {
    return this.post<JobIniciado>('/ciec/cfdi', req as unknown as Record<string, unknown>);
  }

  /** Inicia la descarga de la Constancia de Situación Fiscal vía CIEC. */
  async ciecConstancia(req: CiecDocRequest): Promise<JobIniciado> {
    return this.post<JobIniciado>('/ciec/constancia', req as unknown as Record<string, unknown>);
  }

  /** Inicia la descarga de la Opinión de Cumplimiento 32-D vía CIEC. */
  async ciecOpinion(req: CiecDocRequest): Promise<JobIniciado> {
    return this.post<JobIniciado>('/ciec/opinion', req as unknown as Record<string, unknown>);
  }

  /** Entrega la solución del captcha (o `null` para cancelar el job). */
  async responderCaptcha(jobId: string, solution: string | null): Promise<{ ok: boolean }> {
    return this.post<{ ok: boolean }>(`/jobs/${jobId}/captcha`, { solution });
  }

  /** Estado actual de un job. */
  async getJob(jobId: string): Promise<JobEstadoResponse> {
    return this.request<JobEstadoResponse>(`/jobs/${jobId}`);
  }

  /**
   * Suscribe al stream SSE de progreso de un job (incluye `captcha_required`).
   * Devuelve el `EventSource`; el caller debe llamar `.close()` al terminar.
   * Solo en navegador/Electron (usa la API EventSource).
   */
  subscribeJob(
    jobId: string,
    onEvent: (ev: JobEvent) => void,
    onError?: (e: Event) => void,
  ): EventSource {
    const es = new EventSource(this.url(`/events/${jobId}`));
    es.onmessage = (e) => {
      try {
        onEvent(JSON.parse(e.data) as JobEvent);
      } catch {
        /* ignorar líneas no-JSON */
      }
    };
    if (onError) es.onerror = onError;
    return es;
  }

  // -----------------------------------------------------------------------
  // Documentos vía e.firma (FIEL en sesión; sin captcha)
  // -----------------------------------------------------------------------

  /** Inicia una descarga de CFDIs vía portal con la e.firma en sesión (sin captcha). */
  async cfdiFiel(req: CfdiFielRequest): Promise<JobIniciado> {
    return this.post<JobIniciado>('/cfdi/fiel', req as unknown as Record<string, unknown>);
  }

  async constanciaFiel(): Promise<DocumentoResponse> {
    return this.post<DocumentoResponse>('/constancia/fiel');
  }

  async opinionFiel(): Promise<DocumentoResponse> {
    return this.post<DocumentoResponse>('/opinion/fiel');
  }

  // -----------------------------------------------------------------------
  // Empresas (catálogo persistente; credenciales en keychain del SO)
  // -----------------------------------------------------------------------

  async listEmpresas(): Promise<EmpresasResponse> {
    return this.request<EmpresasResponse>('/empresas');
  }

  /** Registra una empresa por e.firma (multipart .cer/.key/password/nombre). */
  async addEmpresaFiel(
    cerFile: File,
    keyFile: File,
    password: string,
    nombre: string,
    rfcEsperado?: string,
  ): Promise<{ ok: boolean; rfc: string }> {
    const formData = new FormData();
    formData.append('cer_file', cerFile);
    formData.append('key_file', keyFile);
    formData.append('password', password);
    formData.append('nombre', nombre);
    // Al agregar e.firma a una empresa existente, valida que el RFC del cert coincida.
    if (rfcEsperado) formData.append('rfc_esperado', rfcEsperado);
    return this.request<{ ok: boolean; rfc: string }>('/empresas/fiel', {
      method: 'POST',
      body: formData,
    });
  }

  /** Registra una empresa por CIEC (RFC + nombre + contraseña CIEC). */
  async addEmpresaCiec(req: EmpresaCiecRequest): Promise<{ ok: boolean; rfc: string }> {
    return this.post<{ ok: boolean; rfc: string }>(
      '/empresas/ciec',
      req as unknown as Record<string, unknown>,
    );
  }

  async removeEmpresa(rfc: string): Promise<{ ok: boolean }> {
    return this.del<{ ok: boolean }>(`/empresas/${encodeURIComponent(rfc)}`);
  }

  /** Activa una empresa para la sesión (FIEL → carga la e.firma en memoria). */
  async activarEmpresa(rfc: string): Promise<ActivarEmpresaResponse> {
    return this.post<ActivarEmpresaResponse>(`/empresas/${encodeURIComponent(rfc)}/activar`);
  }

  /** Marca una empresa como predeterminada (activa) del catálogo. */
  async setDefaultEmpresa(rfc: string): Promise<{ ok: boolean; rfc: string }> {
    return this.post<{ ok: boolean; rfc: string }>(
      `/empresas/${encodeURIComponent(rfc)}/default`,
    );
  }

  /** Archiva la empresa (soft-delete; la oculta de la lista principal). */
  async archiveEmpresa(rfc: string): Promise<{ ok: boolean; rfc: string }> {
    return this.post<{ ok: boolean; rfc: string }>(
      `/empresas/${encodeURIComponent(rfc)}/archive`,
    );
  }

  /** Desarchiva la empresa (la regresa a la lista principal). */
  async unarchiveEmpresa(rfc: string): Promise<{ ok: boolean; rfc: string }> {
    return this.post<{ ok: boolean; rfc: string }>(
      `/empresas/${encodeURIComponent(rfc)}/unarchive`,
    );
  }

  /** Aplica un patch parcial a la empresa (regimenes_fiscales, actividades_economicas). */
  async updateEmpresa(
    rfc: string,
    patch: EmpresaUpdatePatch,
  ): Promise<{ ok: boolean; rfc: string }> {
    return this.patch<{ ok: boolean; rfc: string }>(
      `/empresas/${encodeURIComponent(rfc)}`,
      patch as unknown as Record<string, unknown>,
    );
  }

  /** Historial de solicitudes de una empresa. */
  async listSolicitudes(rfc: string): Promise<SolicitudesResponse> {
    return this.request<SolicitudesResponse>(
      `/empresas/${encodeURIComponent(rfc)}/solicitudes`,
    );
  }

  /** Borra una solicitud del catálogo local (no afecta al SAT). */
  async deleteSolicitud(rfc: string, idSolicitud: string): Promise<{ ok: boolean }> {
    return this.del<{ ok: boolean }>(
      `/empresas/${encodeURIComponent(rfc)}/solicitudes/${encodeURIComponent(idSolicitud)}`,
    );
  }

  /** Historial de descargas completadas de TODAS las empresas (recientes primero). */
  async listHistorial(): Promise<HistorialResponse> {
    return this.request<HistorialResponse>('/historial');
  }

  /** Historial de descargas completadas de una empresa. */
  async listHistorialEmpresa(rfc: string): Promise<HistorialResponse> {
    return this.request<HistorialResponse>(
      `/empresas/${encodeURIComponent(rfc)}/historial`,
    );
  }

  /** Abre en el SO una descarga del historial: su carpeta o el archivo (PDF). */
  async abrir(ruta: string, modo: 'carpeta' | 'archivo' = 'carpeta'): Promise<{ ok: boolean }> {
    return this.post<{ ok: boolean }>('/abrir', { ruta, modo });
  }

  // -----------------------------------------------------------------------
  // Ajustes
  // -----------------------------------------------------------------------

  /** Carpeta base donde se guardan las descargas. */
  async getDescargasDir(): Promise<{ dir: string }> {
    return this.request<{ dir: string }>('/config/descargas-dir');
  }

  /** Cambia la carpeta base de descargas. */
  async setDescargasDir(dir: string): Promise<{ dir: string }> {
    return this.request<{ dir: string }>('/config/descargas-dir', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dir }),
    });
  }

  // -----------------------------------------------------------------------
  // Procesador de comprobantes — CFDI
  // -----------------------------------------------------------------------

  /** Sube XMLs por multipart al buffer del procesador (drag&drop, examinar). */
  async procesadorCargar(files: File[]): Promise<ProcesadorCargarResponse> {
    const form = new FormData();
    for (const f of files) form.append('files', f);
    return this.request<ProcesadorCargarResponse>('/procesador/cfdi/cargar', {
      method: 'POST',
      body: form,
    });
  }

  /** Importa CFDIs ya descargados por el agente para una empresa registrada. */
  async procesadorCargarDesdeEmpresa(
    req: CargarDesdeEmpresaRequest,
  ): Promise<ProcesadorCargarResponse> {
    return this.post<ProcesadorCargarResponse>(
      '/procesador/cfdi/cargar-desde-empresa',
      req as unknown as Record<string, unknown>,
    );
  }

  /** Valida contra el SAT los CFDIs del buffer (o los uuids indicados). */
  async procesadorValidarSat(uuids?: string[]): Promise<ValidarSatResponse> {
    return this.post<ValidarSatResponse>('/procesador/cfdi/validar-sat', {
      uuids: uuids ?? null,
    });
  }

  /** Lista paginada del buffer con filtros. */
  async procesadorListar(
    filtros?: Partial<CfdiFiltros>,
    page = 1,
    pageSize = 50,
  ): Promise<CfdiListResponse> {
    const qs = _filtrosToQuery({ ...filtros, page, page_size: pageSize });
    return this.request<CfdiListResponse>(`/procesador/cfdi?${qs}`);
  }

  /** Stats agregados (cards superiores). */
  async procesadorStats(filtros?: Partial<CfdiFiltros>): Promise<CfdiStats> {
    const qs = _filtrosToQuery(filtros ?? {});
    return this.request<CfdiStats>(`/procesador/cfdi/stats?${qs}`);
  }

  /** Reporte específico: 'totales-mes' | 'top-contrapartes' | 'integridad'. */
  async procesadorReporte(
    nombre: 'totales-mes',
    filtros?: Partial<CfdiFiltros>,
  ): Promise<ReporteTotalesMes>;
  async procesadorReporte(
    nombre: 'top-contrapartes',
    filtros?: Partial<CfdiFiltros>,
  ): Promise<ReporteTopContrapartes>;
  async procesadorReporte(
    nombre: 'integridad',
    filtros?: Partial<CfdiFiltros>,
  ): Promise<ReporteIntegridad>;
  async procesadorReporte(
    nombre: string,
    filtros?: Partial<CfdiFiltros>,
  ): Promise<ReporteTotalesMes | ReporteTopContrapartes | ReporteIntegridad> {
    const qs = _filtrosToQuery(filtros ?? {});
    return this.request(`/procesador/cfdi/reporte/${nombre}?${qs}`);
  }

  /** Filtros persistidos (lectura). */
  async procesadorFiltrosGet(): Promise<CfdiFiltros> {
    return this.request<CfdiFiltros>('/procesador/cfdi/filtros');
  }

  /** Filtros persistidos (escritura). */
  async procesadorFiltrosSet(filtros: Partial<CfdiFiltros>): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>('/procesador/cfdi/filtros', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filtros),
    });
  }

  /** Vacía el buffer completo. */
  async procesadorBorrar(): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>('/procesador/cfdi', { method: 'DELETE' });
  }

  /** Descarga el buffer filtrado como Blob (xlsx o csv). */
  async procesadorExportar(
    formato: 'xlsx' | 'csv',
    filtros?: Partial<CfdiFiltros>,
  ): Promise<Blob> {
    const qs = _filtrosToQuery({ ...(filtros ?? {}), formato });
    const r = await fetch(this.url(`/procesador/cfdi/exportar?${qs}`));
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Error al exportar: ${r.status} ${text}`);
    }
    return await r.blob();
  }
}


function _filtrosToQuery(filtros: Record<string, unknown>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filtros)) {
    if (value === null || value === undefined || value === '') continue;
    if (typeof value === 'boolean') {
      if (value) params.set(key, 'true');
      continue;
    }
    params.set(key, String(value));
  }
  return params.toString();
}

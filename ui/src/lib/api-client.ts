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
  ValidarRequest,
  ValidarResponse,
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
  // CFDI Validation (public SAT endpoint — no FIEL required)
  // -----------------------------------------------------------------------

  /**
   * Validate the status of CFDIs (Vigente / Cancelado / No Encontrado).
   */
  async validar(req: ValidarRequest): Promise<ValidarResponse> {
    return this.post<ValidarResponse>('/validar', req as unknown as Record<string, unknown>);
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
}

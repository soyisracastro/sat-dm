import { API_BASE_URL, getAgentToken } from './constants';
import { agregarBreadcrumb, capturarExcepcion } from './telemetria';
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
  PagosFiltros,
  PagosStats,
  FacturasPPDResponse,
  PagoRelacionadoDetalle,
  ReporteAnalisisFechas,
  ReportePagosHuerfanos,
  ReporteIncidenciasPue,
  NominaFiltros,
  NominaStats,
  NominaRecibosResponse,
  NominaConceptoDetalle,
  ReporteDeducibilidad,
  ReporteImss,
  ReportePeriodoVsPeriodo,
  ListaNegraMatch,
  ListasNegrasMetadata,
  ListasNegrasConsultarResponse,
  ProcesadorValidarListasNegrasResponse,
  ProcesadorListasNegrasStats,
  EmisoresListasNegrasResponse,
  CalculadoraNombre,
  CalculadoraRequestMap,
  CalculadoraResultadoMap,
  CalculoResponse,
  CalculadorasEstadoResponse,
  CalculadoraEstadoResponse,
  CalculadoraGuardado,
  CalculadoraGuardadoRequest,
  IndicadoresCalculadoras,
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

  /**
   * ¿El agente respondió alguna vez en esta sesión? Arranca en `false` y pasa a
   * `true` con la primera respuesta HTTP (cualquier status). Sirve para distinguir
   * "el agente aún no termina de levantar" (carrera de arranque esperada en equipos
   * lentos; el health poll reintenta y se recupera solo) de "el agente se cayó /
   * se perdió la conexión" — solo este último vale reportar a Sentry.
   */
  private agenteVistoArriba = false;

  constructor(baseUrl?: string) {
    this.baseUrl = (baseUrl ?? API_BASE_URL).replace(/\/+$/, '');
  }

  // -----------------------------------------------------------------------
  // Internal helpers
  // -----------------------------------------------------------------------

  /** Header de autenticación con el agente (token efímero inyectado por Electron). */
  private tokenHeaders(): Record<string, string> {
    const token = getAgentToken();
    return token ? { 'X-Agent-Token': token } : {};
  }

  private async request<T>(
    path: string,
    options: RequestInit = {},
    opts: { reportarFallosDeRed?: boolean } = {},
  ): Promise<T> {
    const url = `${this.baseUrl}${path}`;
    const method = options.method ?? 'GET';
    agregarBreadcrumb({ category: 'http', message: `${method} ${path}`, level: 'info' });

    let res: Response;
    try {
      res = await fetch(url, {
        ...options,
        headers: {
          ...this.tokenHeaders(),
          ...(options.headers ?? {}),
        },
      });
    } catch (err) {
      // Fallo de red. Solo lo reportamos si el agente YA respondió alguna vez en
      // esta sesión (= se cayó / se perdió la conexión). Antes de eso es la carrera
      // de arranque (el binario del agente tarda en aceptar conexiones en equipos
      // lentos): ruido esperado que el health poll resuelve solo, no un fallo real.
      if (opts.reportarFallosDeRed !== false && this.agenteVistoArriba) {
        capturarExcepcion(err, { path, method });
      }
      throw err;
    }

    // Hubo respuesta HTTP (cualquier status): el agente está arriba.
    this.agenteVistoArriba = true;

    if (!res.ok) {
      let detail: string;
      try {
        const body = await res.json();
        detail = body.detail ?? JSON.stringify(body);
      } catch {
        detail = await res.text().catch(() => res.statusText);
      }
      const error = new ApiError(res.status, detail);
      // Solo capturamos 5xx (fallo real del agente). Los 4xx son esperados
      // (409 job concurrente, 400/422 validación, 401 token) y harían ruido.
      if (res.status >= 500) capturarExcepcion(error, { path, method });
      throw error;
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

  /**
   * Como `url()`, pero con el token como query param. Solo para EventSource,
   * que no acepta headers; el resto de requests manda el header.
   */
  private urlConToken(path: string): string {
    const token = getAgentToken();
    if (!token) return this.url(path);
    const sep = path.includes('?') ? '&' : '?';
    return `${this.baseUrl}${path}${sep}token=${encodeURIComponent(token)}`;
  }

  // -----------------------------------------------------------------------
  // Health
  // -----------------------------------------------------------------------

  async health(): Promise<HealthResponse> {
    // El health es la sonda de liveness: su fallo de red es estado esperado
    // (lo maneja `useServerHealth` marcando isConnected=false y reintentando),
    // no un error que valga reportar. Nunca va a Sentry.
    return this.request<HealthResponse>('/health', {}, { reportarFallosDeRed: false });
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
    const es = new EventSource(this.urlConToken(`/events/${jobId}`));
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
    nombre = '',
    rfcEsperado?: string,
  ): Promise<{ ok: boolean; rfc: string }> {
    const formData = new FormData();
    formData.append('cer_file', cerFile);
    formData.append('key_file', keyFile);
    formData.append('password', password);
    // Opcional: vacío → el agente usa la razón social del certificado.
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

  /** Quita SOLO la e.firma de la empresa (la CIEC no se toca). */
  async removeEfirmaEmpresa(rfc: string): Promise<{ ok: boolean }> {
    return this.del<{ ok: boolean }>(`/empresas/${encodeURIComponent(rfc)}/fiel`);
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
    const r = await fetch(this.url(`/procesador/cfdi/exportar?${qs}`), { headers: this.tokenHeaders() });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Error al exportar: ${r.status} ${text}`);
    }
    return await r.blob();
  }

  // -----------------------------------------------------------------------
  // Procesador de comprobantes — Pagos
  // -----------------------------------------------------------------------
  //
  // Vista especializada sobre el buffer compartido. NO tiene cargar/borrar —
  // los XMLs entran por `procesadorCargar` (CFDI). Filtros propios con key
  // `'pagos_actuales'` en el backend.

  /** Facturas PPD paginadas con status calculado. */
  async procesadorPagosListar(
    filtros?: Partial<PagosFiltros>,
    page = 1,
    pageSize = 50,
  ): Promise<FacturasPPDResponse> {
    const params: Record<string, unknown> = {
      desde: filtros?.desde,
      hasta: filtros?.hasta,
      busqueda: filtros?.busqueda,
      page,
      page_size: pageSize,
    };
    if (filtros?.status && filtros.status.length > 0) {
      params.status = filtros.status.join(',');
    }
    const qs = _filtrosToQuery(params);
    return this.request<FacturasPPDResponse>(`/procesador/pagos?${qs}`);
  }

  /** KPIs del procesador de Pagos. */
  async procesadorPagosStats(filtros?: Partial<PagosFiltros>): Promise<PagosStats> {
    const qs = _filtrosToQuery({
      desde: filtros?.desde,
      hasta: filtros?.hasta,
      busqueda: filtros?.busqueda,
    });
    return this.request<PagosStats>(`/procesador/pagos/stats?${qs}`);
  }

  /** Drilldown: complementos asociados a una factura PPD. */
  async procesadorPagosDetalleFactura(
    uuid: string,
  ): Promise<{ uuid: string; items: PagoRelacionadoDetalle[] }> {
    return this.request(`/procesador/pagos/factura/${encodeURIComponent(uuid)}/pagos`);
  }

  /** Reporte específico. */
  async procesadorPagosReporte(
    nombre: 'analisis-fechas',
    filtros?: Partial<PagosFiltros>,
  ): Promise<ReporteAnalisisFechas>;
  async procesadorPagosReporte(
    nombre: 'huerfanos',
    filtros?: Partial<PagosFiltros>,
  ): Promise<ReportePagosHuerfanos>;
  async procesadorPagosReporte(
    nombre: 'incidencias-pue',
    filtros?: Partial<PagosFiltros>,
  ): Promise<ReporteIncidenciasPue>;
  async procesadorPagosReporte(
    nombre: string,
    filtros?: Partial<PagosFiltros>,
  ): Promise<ReporteAnalisisFechas | ReportePagosHuerfanos | ReporteIncidenciasPue> {
    const qs = _filtrosToQuery({
      desde: filtros?.desde,
      hasta: filtros?.hasta,
      busqueda: filtros?.busqueda,
    });
    return this.request(`/procesador/pagos/reporte/${nombre}?${qs}`);
  }

  /** Filtros persistidos del procesador de Pagos. */
  async procesadorPagosFiltrosGet(): Promise<PagosFiltros> {
    return this.request<PagosFiltros>('/procesador/pagos/filtros');
  }

  async procesadorPagosFiltrosSet(filtros: Partial<PagosFiltros>): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>('/procesador/pagos/filtros', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filtros),
    });
  }

  /** Descarga XLSX multi-sheet del procesador de Pagos. */
  async procesadorPagosExportar(filtros?: Partial<PagosFiltros>): Promise<Blob> {
    const qs = _filtrosToQuery({
      desde: filtros?.desde,
      hasta: filtros?.hasta,
      busqueda: filtros?.busqueda,
    });
    const r = await fetch(this.url(`/procesador/pagos/exportar?${qs}`), { headers: this.tokenHeaders() });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Error al exportar: ${r.status} ${text}`);
    }
    return await r.blob();
  }

  // -------------------------------------------------------------------------
  // Procesador de comprobantes — Nómina
  // -------------------------------------------------------------------------
  // Vista especializada sobre el buffer compartido `cfdis` + tablas
  // `nomina_recibos` y `nomina_conceptos`. Mismo flujo de carga que CFDI:
  // los XMLs entran por `procesadorCargar`. Filtros propios con key
  // `'nomina_actuales'` en el backend.

  private _filtrosNominaParams(filtros?: Partial<NominaFiltros>): Record<string, unknown> {
    return {
      desde: filtros?.desde,
      hasta: filtros?.hasta,
      busqueda: filtros?.busqueda,
      tipo_nomina: filtros?.tipo_nomina,
      periodicidad: filtros?.periodicidad,
      solo_con_errores: filtros?.solo_con_errores ? 'true' : undefined,
    };
  }

  /** Recibos de nómina paginados (1 fila por CFDI tipo N). */
  async procesadorNominaListar(
    filtros?: Partial<NominaFiltros>,
    page = 1,
    pageSize = 50,
  ): Promise<NominaRecibosResponse> {
    const qs = _filtrosToQuery({
      ...this._filtrosNominaParams(filtros),
      page,
      page_size: pageSize,
    });
    return this.request<NominaRecibosResponse>(`/procesador/nomina?${qs}`);
  }

  /** KPIs del procesador de Nómina. */
  async procesadorNominaStats(filtros?: Partial<NominaFiltros>): Promise<NominaStats> {
    const qs = _filtrosToQuery(this._filtrosNominaParams(filtros));
    return this.request<NominaStats>(`/procesador/nomina/stats?${qs}`);
  }

  /** Drilldown: conceptos de un recibo de nómina ordenados por clase. */
  async procesadorNominaConceptosDeRecibo(
    uuid: string,
  ): Promise<{ uuid: string; items: NominaConceptoDetalle[] }> {
    return this.request(
      `/procesador/nomina/recibo/${encodeURIComponent(uuid)}/conceptos`,
    );
  }

  /** Reporte específico (Deductibilidad / IMSS / Periodo vs Periodo). */
  async procesadorNominaReporte(
    nombre: 'deducibilidad',
    filtros?: Partial<NominaFiltros>,
  ): Promise<ReporteDeducibilidad>;
  async procesadorNominaReporte(
    nombre: 'imss',
    filtros?: Partial<NominaFiltros>,
  ): Promise<ReporteImss>;
  async procesadorNominaReporte(
    nombre: 'periodo-vs-periodo',
    filtros?: Partial<NominaFiltros>,
  ): Promise<ReportePeriodoVsPeriodo>;
  async procesadorNominaReporte(
    nombre: string,
    filtros?: Partial<NominaFiltros>,
  ): Promise<ReporteDeducibilidad | ReporteImss | ReportePeriodoVsPeriodo> {
    const qs = _filtrosToQuery(this._filtrosNominaParams(filtros));
    return this.request(`/procesador/nomina/reporte/${nombre}?${qs}`);
  }

  /** Filtros persistidos del procesador de Nómina. */
  async procesadorNominaFiltrosGet(): Promise<NominaFiltros> {
    return this.request<NominaFiltros>('/procesador/nomina/filtros');
  }

  async procesadorNominaFiltrosSet(
    filtros: Partial<NominaFiltros>,
  ): Promise<{ ok: boolean }> {
    return this.request<{ ok: boolean }>('/procesador/nomina/filtros', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filtros),
    });
  }

  /** Descarga XLSX multi-sheet del procesador de Nómina (con disclaimer fiscal). */
  async procesadorNominaExportar(filtros?: Partial<NominaFiltros>): Promise<Blob> {
    const qs = _filtrosToQuery(this._filtrosNominaParams(filtros));
    const r = await fetch(this.url(`/procesador/nomina/exportar?${qs}`), { headers: this.tokenHeaders() });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Error al exportar: ${r.status} ${text}`);
    }
    return await r.blob();
  }

  // -------------------------------------------------------------------------
  // Auth + license (proxy hacia todoconta-apps via el agente)
  // -------------------------------------------------------------------------
  // El Bearer token NO llega al renderer — vive solo en el proceso Python.
  // El renderer solo conoce el estado derivado (autenticado, is_founder, etc.)

  /** Genera un device_code y devuelve el URL público de activación. */
  async authInit(): Promise<AuthInitResponse> {
    return this.post<AuthInitResponse>('/auth/init', {});
  }

  /** Polling del device_code hasta que el usuario completa el login web. */
  async authPoll(device_code: string): Promise<AuthPollResponse> {
    return this.post<AuthPollResponse>('/auth/poll', { device_code });
  }

  /** Login en-app con correo + contraseña (directo contra Supabase). */
  async authLoginPassword(email: string, password: string): Promise<AuthSessionResponse> {
    return this.post<AuthSessionResponse>('/auth/login-password', { email, password });
  }

  /**
   * Envía un código de 6 dígitos al correo. Con `crearCuenta` el código
   * también registra al usuario (con `nombre` opcional). `tipo='signup'`
   * reenvía la confirmación de un registro con contraseña.
   */
  async authOtpSend(
    email: string,
    opts: { crearCuenta?: boolean; nombre?: string; tipo?: 'email' | 'signup' } = {},
  ): Promise<{ ok: boolean }> {
    return this.post<{ ok: boolean }>('/auth/otp-send', {
      email,
      crear_cuenta: opts.crearCuenta ?? false,
      nombre: opts.nombre ?? '',
      tipo: opts.tipo ?? 'email',
    });
  }

  /** Verifica el código tecleado en la app y guarda la sesión en el agente. */
  async authOtpVerify(
    email: string,
    token: string,
    tipo: 'email' | 'signup' = 'email',
  ): Promise<AuthSessionResponse> {
    return this.post<AuthSessionResponse>('/auth/otp-verify', { email, token, tipo });
  }

  /**
   * Registro con correo + contraseña. Si `requiere_confirmacion` viene true,
   * Supabase mandó un código al correo y hay que verificarlo (tipo='signup').
   */
  async authSignup(
    email: string,
    password: string,
    nombre: string,
  ): Promise<AuthSessionResponse> {
    return this.post<AuthSessionResponse>('/auth/signup', { email, password, nombre });
  }

  /**
   * Inicia el OAuth con Google (PKCE). Devuelve la URL de Supabase que el
   * renderer abre en el navegador del SO; al volver, Supabase entrega el
   * `auth_code` por el deep link `todoconta://auth-callback`.
   */
  async authOauthStart(provider: 'google' = 'google'): Promise<{ url: string }> {
    return this.post<{ url: string }>('/auth/oauth/start', { provider });
  }

  /** Canjea el auth_code del deep link por la sesión (la guarda en el agente). */
  async authOauthCallback(code: string): Promise<AuthSessionResponse> {
    return this.post<AuthSessionResponse>('/auth/oauth/callback', { code });
  }

  /** Estado de licencia del usuario actual (cached 24h). */
  async authLicense(refresh = false): Promise<LicenseStatus> {
    const qs = refresh ? '?refresh=true' : '';
    return this.request<LicenseStatus>(`/auth/license${qs}`);
  }

  /** Crea una Stripe Checkout session (Fundador) y devuelve la URL para abrir. */
  async authUpgrade(): Promise<{ url: string; session_id?: string }> {
    return this.post<{ url: string; session_id?: string }>('/auth/upgrade', {});
  }

  /** Checkout de la suscripción anual (tarjeta). El backend elige promo/regular. */
  async authSubscribe(): Promise<AuthSubscribeResponse> {
    return this.post<AuthSubscribeResponse>('/auth/subscribe', {});
  }

  /** Cancela la suscripción al fin del periodo. */
  async authCancelSubscription(): Promise<CancelSubscriptionResponse> {
    return this.post<CancelSubscriptionResponse>('/auth/cancel-subscription', {});
  }

  /** Registra intención de pago por transferencia; devuelve datos bancarios. */
  async authTransferIntent(): Promise<TransferIntentResponse> {
    return this.post<TransferIntentResponse>('/auth/transfer-intent', {});
  }

  /** Cierra sesión local (borra keyring + cache). */
  async authLogout(): Promise<{ ok: boolean }> {
    return this.post<{ ok: boolean }>('/auth/logout', {});
  }

  /**
   * Carga la FIEL de la empresa activa en sesión del agente.
   *
   * Antes lo hacía el lifespan del agente al arranque, pero en Windows con
   * binario sin firma el `keyring.get_password()` quedaba bloqueado y el
   * agente nunca aceptaba conexiones. Ahora el renderer lo invoca post-login.
   * Es idempotente y nunca falla (los errores devuelven `ok=false`).
   */
  async autocargarFiel(): Promise<{
    ok: boolean;
    cargada: boolean;
    rfc: string | null;
    error?: string;
  }> {
    return this.post('/auth/autocargar-fiel', {});
  }

  // -----------------------------------------------------------------------
  // Listas negras del SAT (Art. 69 y 69-B)
  // -----------------------------------------------------------------------

  /** Consulta ad-hoc de RFCs. No persiste en SQLite. */
  async listasNegrasConsultar(rfcs: string[]): Promise<ListasNegrasConsultarResponse> {
    return this.post<ListasNegrasConsultarResponse>('/listas-negras/consultar', { rfcs });
  }

  /** Cuándo se actualizaron las listas en el origen (cron mensual del día 5). */
  async listasNegrasMetadata(): Promise<ListasNegrasMetadata> {
    return this.request<ListasNegrasMetadata>('/listas-negras/metadata');
  }

  /** Valida los RFCs del buffer del procesador y persiste el resultado por fila. */
  async procesadorValidarListasNegras(
    opts: { uuids?: string[]; force_refresh?: boolean } = {},
  ): Promise<ProcesadorValidarListasNegrasResponse> {
    return this.post<ProcesadorValidarListasNegrasResponse>(
      '/procesador/cfdi/validar-listas-negras',
      {
        uuids: opts.uuids ?? null,
        force_refresh: opts.force_refresh ?? false,
      },
    );
  }

  /** KPIs (EFOS / EDOS / Aclarado / 69 / Limpios / Sin validar) sobre el buffer filtrado. */
  async procesadorListasNegrasStats(
    filtros?: Partial<CfdiFiltros>,
  ): Promise<ProcesadorListasNegrasStats> {
    const qs = _filtrosToQuery(filtros ?? {});
    return this.request<ProcesadorListasNegrasStats>(
      `/procesador/cfdi/listas-negras/stats?${qs}`,
    );
  }

  /** Una fila por emisor_rfc (no por CFDI) con SUM(total) + COUNT, ordenada por total desc. */
  async procesadorListasNegrasPorEmisor(
    filtros?: Partial<CfdiFiltros>,
    page = 1,
    pageSize = 50,
  ): Promise<EmisoresListasNegrasResponse> {
    const qs = _filtrosToQuery({ ...(filtros ?? {}), page, page_size: pageSize });
    return this.request<EmisoresListasNegrasResponse>(
      `/procesador/cfdi/listas-negras/por-emisor?${qs}`,
    );
  }

  // -----------------------------------------------------------------------
  // Calculadoras fiscales y laborales
  // -----------------------------------------------------------------------

  /**
   * Calcula una calculadora. Si el body lleva `rfc`, el agente auto-guarda
   * el estado (inputs + resultado) para esa empresa en el mismo round-trip.
   */
  async calculadoraCalcular<N extends CalculadoraNombre>(
    nombre: N,
    body: CalculadoraRequestMap[N],
  ): Promise<CalculoResponse<CalculadoraResultadoMap[N]>> {
    return this.post<CalculoResponse<CalculadoraResultadoMap[N]>>(
      `/calculadoras/${nombre}`,
      body as unknown as Record<string, unknown>,
    );
  }

  /** Estado completo de la empresa: último estado por calculadora + guardados. */
  async calculadoraEstado(rfc: string): Promise<CalculadorasEstadoResponse> {
    return this.request<CalculadorasEstadoResponse>(
      `/calculadoras/estado/${encodeURIComponent(rfc)}`,
    );
  }

  /** Último estado (inputs + resultado) de una calculadora, o null si no hay. */
  async calculadoraEstadoDe(
    rfc: string,
    calculadora: CalculadoraNombre,
  ): Promise<CalculadoraEstadoResponse> {
    return this.request<CalculadoraEstadoResponse>(
      `/calculadoras/estado/${encodeURIComponent(rfc)}/${calculadora}`,
    );
  }

  /** Guarda un snapshot con nombre (botón "Guardar cálculo"). */
  async calculadoraGuardar(
    rfc: string,
    body: CalculadoraGuardadoRequest,
  ): Promise<{ ok: boolean; guardado: CalculadoraGuardado }> {
    return this.post<{ ok: boolean; guardado: CalculadoraGuardado }>(
      `/calculadoras/guardados/${encodeURIComponent(rfc)}`,
      body as unknown as Record<string, unknown>,
    );
  }

  /** Elimina un cálculo guardado por id. */
  async calculadoraEliminarGuardado(rfc: string, id: string): Promise<{ ok: boolean }> {
    return this.del<{ ok: boolean }>(
      `/calculadoras/guardados/${encodeURIComponent(rfc)}/${encodeURIComponent(id)}`,
    );
  }

  /** Indicadores del ejercicio (UMA, SMG, ISN por estado, clases de riesgo, ...). */
  async calculadoraIndicadores(anio: number): Promise<IndicadoresCalculadoras> {
    return this.request<IndicadoresCalculadoras>(`/calculadoras/indicadores/${anio}`);
  }

  /**
   * Exporta un cálculo (recalcula server-side desde los inputs).
   * Premium: el gating vive en la UI (`license.premium_features_unlocked`).
   */
  async calculadoraExportar(
    formato: 'xlsx' | 'pdf' | 'recibos-ptu',
    calculadora: CalculadoraNombre,
    inputs: Record<string, unknown>,
  ): Promise<Blob> {
    const r = await fetch(this.url(`/calculadoras/exportar/${formato}`), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...this.tokenHeaders() },
      body: JSON.stringify({ calculadora, inputs }),
    });
    if (!r.ok) {
      const text = await r.text();
      throw new Error(`Error al exportar: ${r.status} ${text}`);
    }
    return await r.blob();
  }
}

// ---------------------------------------------------------------------------
// Tipos de auth + license
// ---------------------------------------------------------------------------

export interface AuthInitResponse {
  device_code: string;
  expires_at: string;
  activate_url: string;
}

/** Respuesta de login-password / otp-verify / signup (auth en-app). */
export interface AuthSessionResponse {
  ok: boolean;
  user?: { id: string; email: string | null };
  requiere_confirmacion?: boolean;
}

export type AuthPollStatus = 'ok' | 'pending' | 'expired' | 'not_found';

export interface AuthPollResponse {
  status: AuthPollStatus;
  user?: { id: string; email: string | null };
}

export type DesktopPlan = 'founder' | 'premium' | 'trial' | 'free';

export interface LicenseStatus {
  authenticated: boolean;
  user_id?: string;
  email?: string | null;

  // Plan derivado + cuenta regresiva (pueden faltar en fallback offline sin cache).
  plan?: DesktopPlan;
  days_remaining?: number | null;
  expires_at?: string | null;
  subscription_cancel_at_period_end?: boolean;

  // Promo anual del 50% (bloqueado de por vida).
  promo_active?: boolean;
  promo_ends_at?: string | null;
  promo_price_mxn?: number;
  regular_price_mxn?: number;
  promo_days?: number;

  // Fundador.
  is_founder?: boolean;
  founder_acquired_at?: string | null;
  founder_window_open?: boolean;
  founder_window_closes_at?: string;
  founder_price_mxn?: number;

  premium_features_unlocked?: boolean;
  ai_credits_balance?: number;
  // Flags del cache local del agente.
  from_cache?: boolean;
  stale?: boolean;
  offline?: boolean;
  reason?: string;
}

export interface AuthSubscribeResponse {
  url: string;
  session_id?: string;
  promo?: boolean;
}

export interface CancelSubscriptionResponse {
  ok: boolean;
  cancel_at?: string | null;
  manual?: boolean;
  message?: string;
}

export interface DatosBancarios {
  banco: string;
  clabe: string;
  beneficiario: string;
  referencia: string;
}

export interface TransferIntentResponse {
  ok: boolean;
  amount_mxn: number;
  promo: boolean;
  banco: DatosBancarios;
  message?: string;
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

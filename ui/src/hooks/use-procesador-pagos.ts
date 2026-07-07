'use client';

import {
  useProcesadorGenerico,
  type ProcesadorConfig,
} from '@/hooks/use-procesador-generico';
import type {
  FacturasPPDResponse,
  PagosFiltros,
  PagosStats,
} from '@/lib/types';

const FILTROS_INICIALES: PagosFiltros = {
  desde: null,
  hasta: null,
  busqueda: null,
  status: null,
  solo_extemporaneos: false,
};

const CONFIG: ProcesadorConfig<PagosFiltros, FacturasPPDResponse, PagosStats> = {
  filtrosIniciales: FILTROS_INICIALES,
  etiquetaLog: 'pagos',
  filtrosGet: (api, rfc) => api.procesadorPagosFiltrosGet(rfc),
  filtrosSet: (api, rfc, filtros) => api.procesadorPagosFiltrosSet(rfc, filtros),
  listar: (api, rfc, filtros, page, pageSize) =>
    api.procesadorPagosListar(rfc, filtros, page, pageSize),
  stats: (api, rfc, filtros) => api.procesadorPagosStats(rfc, filtros),
};

/**
 * Estado del procesador de Pagos:
 * - filtros: persistidos en el backend con key `'pagos_actuales'`.
 * - data: facturas PPD paginadas con status.
 * - stats: KPIs (incluye `total_global_ppd` para detectar buffer vacío).
 *
 * Hidrata desde `GET /procesador/pagos/filtros` al montar; cualquier cambio
 * dispara `PUT` con debounce + refetch.
 */
export function useProcesadorPagos() {
  return useProcesadorGenerico(CONFIG);
}

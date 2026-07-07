'use client';

import {
  useProcesadorGenerico,
  type ProcesadorConfig,
} from '@/hooks/use-procesador-generico';
import type {
  CfdiFiltros,
  CfdiListResponse,
  CfdiStats,
} from '@/lib/types';

const FILTROS_INICIALES: CfdiFiltros = {
  desde: null,
  hasta: null,
  tipo: null,
  direccion: null,
  busqueda: null,
  solo_con_errores: false,
  monto_min: null,
  monto_max: null,
};

const CONFIG: ProcesadorConfig<CfdiFiltros, CfdiListResponse, CfdiStats> = {
  filtrosIniciales: FILTROS_INICIALES,
  etiquetaLog: 'procesador',
  filtrosGet: (api, rfc) => api.procesadorFiltrosGet(rfc),
  filtrosSet: (api, rfc, filtros) => api.procesadorFiltrosSet(rfc, filtros),
  listar: (api, rfc, filtros, page, pageSize) =>
    api.procesadorListar(rfc, filtros, page, pageSize),
  stats: (api, rfc, filtros) => api.procesadorStats(rfc, filtros),
};

/**
 * Estado del procesador CFDI:
 * - filtros: persistidos en el backend (PUT debounced).
 * - data: lista paginada.
 * - stats: KPIs agregados de los mismos filtros.
 *
 * Hidrata desde `GET /procesador/cfdi/filtros` al montar; cualquier cambio
 * dispara `PUT` con debounce + refetch de data/stats.
 */
export function useProcesadorCfdi() {
  return useProcesadorGenerico(CONFIG);
}

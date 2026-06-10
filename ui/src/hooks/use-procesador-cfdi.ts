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
  filtrosGet: (api) => api.procesadorFiltrosGet(),
  filtrosSet: (api, filtros) => api.procesadorFiltrosSet(filtros),
  listar: (api, filtros, page, pageSize) =>
    api.procesadorListar(filtros, page, pageSize),
  stats: (api, filtros) => api.procesadorStats(filtros),
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

'use client';

import {
  useProcesadorGenerico,
  type ProcesadorConfig,
} from '@/hooks/use-procesador-generico';
import type {
  NominaFiltros,
  NominaRecibosResponse,
  NominaStats,
} from '@/lib/types';

const FILTROS_INICIALES: NominaFiltros = {
  desde: null,
  hasta: null,
  busqueda: null,
  tipo_nomina: null,
  periodicidad: null,
  solo_con_errores: false,
};

const CONFIG: ProcesadorConfig<NominaFiltros, NominaRecibosResponse, NominaStats> = {
  filtrosIniciales: FILTROS_INICIALES,
  etiquetaLog: 'nomina',
  filtrosGet: (api, rfc) => api.procesadorNominaFiltrosGet(rfc),
  filtrosSet: (api, rfc, filtros) => api.procesadorNominaFiltrosSet(rfc, filtros),
  listar: (api, rfc, filtros, page, pageSize) =>
    api.procesadorNominaListar(rfc, filtros, page, pageSize),
  stats: (api, rfc, filtros) => api.procesadorNominaStats(rfc, filtros),
};

/**
 * Estado del procesador de Nómina:
 * - filtros persistidos en el backend con key `'nomina_actuales'`.
 * - data: recibos paginados (1 fila por CFDI tipo N).
 * - stats: KPIs (incluye `total_global_recibos` para el bufferVacío de la UI).
 *
 * Hidrata desde `GET /procesador/nomina/filtros` al montar; cualquier cambio
 * dispara `PUT` con debounce + refetch.
 */
export function useProcesadorNomina() {
  return useProcesadorGenerico(CONFIG);
}

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
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
  const { apiClient } = useServer();
  const [filtros, setFiltrosState] = useState<NominaFiltros>(FILTROS_INICIALES);
  const [hidratado, setHidratado] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<NominaRecibosResponse | null>(null);
  const [stats, setStats] = useState<NominaStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hidratación inicial.
  useEffect(() => {
    let mounted = true;
    apiClient
      .procesadorNominaFiltrosGet()
      .then((f) => {
        if (mounted) {
          setFiltrosState({ ...FILTROS_INICIALES, ...f });
          setHidratado(true);
        }
      })
      .catch(() => {
        if (mounted) setHidratado(true);
      });
    return () => {
      mounted = false;
    };
  }, [apiClient]);

  // Persistencia debounced.
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!hidratado) return;
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      apiClient.procesadorNominaFiltrosSet(filtros).catch((e) => {
        console.warn('[nomina] no se pudieron persistir filtros:', e);
      });
    }, 500);
    return () => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
    };
  }, [apiClient, filtros, hidratado]);

  const recargar = useCallback(async () => {
    if (!hidratado) return;
    setLoading(true);
    setError(null);
    try {
      const [list, statsResp] = await Promise.all([
        apiClient.procesadorNominaListar(filtros, page, pageSize),
        apiClient.procesadorNominaStats(filtros),
      ]);
      setData(list);
      setStats(statsResp);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [apiClient, filtros, page, pageSize, hidratado]);

  useEffect(() => {
    if (hidratado) recargar();
  }, [recargar, hidratado]);

  const setFiltro = useCallback(
    <K extends keyof NominaFiltros>(key: K, value: NominaFiltros[K]) => {
      setFiltrosState((prev) => ({ ...prev, [key]: value }));
      setPage(1);
    },
    [],
  );

  const reset = useCallback(() => {
    setFiltrosState(FILTROS_INICIALES);
    setPage(1);
  }, []);

  const filtrosActivos = useMemo(() => {
    return (Object.keys(filtros) as (keyof NominaFiltros)[]).filter((k) => {
      const v = filtros[k];
      if (k === 'solo_con_errores') return Boolean(v);
      if (Array.isArray(v)) return v.length > 0;
      return v !== null && v !== '';
    }).length;
  }, [filtros]);

  return {
    filtros,
    setFiltro,
    reset,
    page,
    setPage,
    pageSize,
    setPageSize,
    data,
    stats,
    loading,
    error,
    recargar,
    filtrosActivos,
    hidratado,
  };
}

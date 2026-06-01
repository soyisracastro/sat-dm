'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
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
  const { apiClient } = useServer();
  const [filtros, setFiltrosState] = useState<PagosFiltros>(FILTROS_INICIALES);
  const [hidratado, setHidratado] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<FacturasPPDResponse | null>(null);
  const [stats, setStats] = useState<PagosStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hidratación inicial.
  useEffect(() => {
    let mounted = true;
    apiClient
      .procesadorPagosFiltrosGet()
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
      apiClient.procesadorPagosFiltrosSet(filtros).catch((e) => {
        console.warn('[pagos] no se pudieron persistir filtros:', e);
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
        apiClient.procesadorPagosListar(filtros, page, pageSize),
        apiClient.procesadorPagosStats(filtros),
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
    <K extends keyof PagosFiltros>(key: K, value: PagosFiltros[K]) => {
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
    return (Object.keys(filtros) as (keyof PagosFiltros)[]).filter((k) => {
      const v = filtros[k];
      if (k === 'solo_extemporaneos') return Boolean(v);
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

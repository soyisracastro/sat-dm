'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
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
  const { apiClient } = useServer();
  const [filtros, setFiltrosState] = useState<CfdiFiltros>(FILTROS_INICIALES);
  const [hidratado, setHidratado] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<CfdiListResponse | null>(null);
  const [stats, setStats] = useState<CfdiStats | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hidratación inicial (una sola vez).
  useEffect(() => {
    let mounted = true;
    apiClient
      .procesadorFiltrosGet()
      .then((f) => {
        if (mounted) {
          setFiltrosState({ ...FILTROS_INICIALES, ...f });
          setHidratado(true);
        }
      })
      .catch(() => {
        if (mounted) setHidratado(true); // continuar con filtros vacíos
      });
    return () => {
      mounted = false;
    };
  }, [apiClient]);

  // Persistencia debounced de filtros (al backend).
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!hidratado) return;
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      apiClient.procesadorFiltrosSet(filtros).catch((e) => {
        console.warn('[procesador] no se pudieron persistir filtros:', e);
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
        apiClient.procesadorListar(filtros, page, pageSize),
        apiClient.procesadorStats(filtros),
      ]);
      setData(list);
      setStats(statsResp);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [apiClient, filtros, page, pageSize, hidratado]);

  // Refetch ante cambios de filtros, página o page size.
  useEffect(() => {
    if (hidratado) recargar();
  }, [recargar, hidratado]);

  const setFiltro = useCallback(
    <K extends keyof CfdiFiltros>(key: K, value: CfdiFiltros[K]) => {
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
    return (Object.keys(filtros) as (keyof CfdiFiltros)[]).filter((k) => {
      const v = filtros[k];
      if (k === 'solo_con_errores') return Boolean(v);
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

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { mensajeDeError } from '@/lib/errores';
import type { SatApiClient } from '@/lib/api-client';

/**
 * Configuración de un procesador (CFDI, Pagos, Nómina): valores iniciales de
 * los filtros + los 4 endpoints del apiClient que lo alimentan. Defínela como
 * constante de módulo para que su identidad sea estable entre renders.
 */
export interface ProcesadorConfig<F extends object, D, S> {
  /** Valores default de los filtros; también el estado tras `reset()`. */
  filtrosIniciales: F;
  /** Prefijo de los `console.warn` (p. ej. `procesador`, `pagos`, `nomina`). */
  etiquetaLog: string;
  /** GET de los filtros persistidos en el backend (hidratación al montar). */
  filtrosGet: (api: SatApiClient) => Promise<Partial<F>>;
  /** PUT de los filtros persistidos (se llama con debounce de 500 ms). */
  filtrosSet: (api: SatApiClient, filtros: F) => Promise<unknown>;
  /** Lista paginada del buffer con los filtros aplicados. */
  listar: (
    api: SatApiClient,
    filtros: F,
    page: number,
    pageSize: number,
  ) => Promise<D>;
  /** KPIs agregados de los mismos filtros. */
  stats: (api: SatApiClient, filtros: F) => Promise<S>;
}

/**
 * Estado compartido de los procesadores (CFDI / Pagos / Nómina):
 * - filtros: persistidos en el backend (PUT debounced).
 * - data: lista paginada.
 * - stats: KPIs agregados de los mismos filtros.
 *
 * Hidrata con `filtrosGet` al montar; cualquier cambio de filtros/página
 * dispara la persistencia debounced + refetch de data/stats en paralelo.
 */
export function useProcesadorGenerico<F extends object, D, S>(
  config: ProcesadorConfig<F, D, S>,
) {
  const {
    filtrosIniciales,
    etiquetaLog,
    filtrosGet,
    filtrosSet,
    listar,
    stats: cargarStats,
  } = config;
  const { apiClient } = useServer();
  const [filtros, setFiltrosState] = useState<F>(filtrosIniciales);
  const [hidratado, setHidratado] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<D | null>(null);
  const [stats, setStats] = useState<S | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Hidratación inicial (una sola vez).
  useEffect(() => {
    let mounted = true;
    filtrosGet(apiClient)
      .then((f) => {
        if (mounted) {
          setFiltrosState({ ...filtrosIniciales, ...f } as F);
          setHidratado(true);
        }
      })
      .catch(() => {
        if (mounted) setHidratado(true); // continuar con filtros vacíos
      });
    return () => {
      mounted = false;
    };
  }, [apiClient, filtrosGet, filtrosIniciales]);

  // Persistencia debounced de filtros (al backend).
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!hidratado) return;
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      filtrosSet(apiClient, filtros).catch((e) => {
        console.warn(`[${etiquetaLog}] no se pudieron persistir filtros:`, e);
      });
    }, 500);
    return () => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
    };
  }, [apiClient, filtros, hidratado, filtrosSet, etiquetaLog]);

  const recargar = useCallback(async () => {
    if (!hidratado) return;
    setLoading(true);
    setError(null);
    try {
      const [list, statsResp] = await Promise.all([
        listar(apiClient, filtros, page, pageSize),
        cargarStats(apiClient, filtros),
      ]);
      setData(list);
      setStats(statsResp);
    } catch (e) {
      setError(mensajeDeError(e));
    } finally {
      setLoading(false);
    }
  }, [apiClient, filtros, page, pageSize, hidratado, listar, cargarStats]);

  // Refetch ante cambios de filtros, página o page size.
  useEffect(() => {
    if (hidratado) recargar();
  }, [recargar, hidratado]);

  const setFiltro = useCallback(
    <K extends keyof F>(key: K, value: F[K]) => {
      setFiltrosState((prev) => ({ ...prev, [key]: value } as F));
      setPage(1);
    },
    [],
  );

  const reset = useCallback(() => {
    setFiltrosState(filtrosIniciales);
    setPage(1);
  }, [filtrosIniciales]);

  const filtrosActivos = useMemo(() => {
    return (Object.keys(filtros) as (keyof F)[]).filter((k) => {
      const v: unknown = filtros[k];
      if (typeof v === 'boolean') return v;
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

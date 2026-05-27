'use client';

import { useCallback, useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { HistorialItem } from '@/lib/types';

interface UseHistorialState {
  descargas: HistorialItem[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Historial de descargas completadas de todas las empresas (GET /historial),
 * más recientes primero. El agente lo persiste por empresa en ~/.sat-descarga.
 */
export function useHistorial(): UseHistorialState {
  const { apiClient } = useServer();
  const [descargas, setDescargas] = useState<HistorialItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiClient
      .listHistorial()
      .then((r) => {
        if (mounted) {
          setDescargas(r.descargas);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (mounted) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [apiClient, tick]);

  return { descargas, loading, error, refresh };
}

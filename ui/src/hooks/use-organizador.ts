'use client';

import { useCallback, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type {
  OrganizadorRequest,
  OrganizadorResult,
  RenombrarRequest,
  DeduplicarRequest,
  DeduplicarResult,
} from '@/lib/types';

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

interface UseOrganizadorReturn {
  organizar: (request: OrganizadorRequest) => Promise<void>;
  renombrar: (request: RenombrarRequest) => Promise<void>;
  deduplicar: (request: DeduplicarRequest) => Promise<void>;
  result: OrganizadorResult | DeduplicarResult | null;
  isLoading: boolean;
  error: string | null;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useOrganizador(): UseOrganizadorReturn {
  const { apiClient } = useServer();

  const [result, setResult] = useState<OrganizadorResult | DeduplicarResult | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const organizar = useCallback(
    async (request: OrganizadorRequest) => {
      setIsLoading(true);
      setError(null);
      setResult(null);
      try {
        const res = await apiClient.organizar(request);
        setResult(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al organizar archivos');
      } finally {
        setIsLoading(false);
      }
    },
    [apiClient],
  );

  const renombrar = useCallback(
    async (request: RenombrarRequest) => {
      setIsLoading(true);
      setError(null);
      setResult(null);
      try {
        const res = await apiClient.renombrar(request);
        setResult(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al renombrar archivos');
      } finally {
        setIsLoading(false);
      }
    },
    [apiClient],
  );

  const deduplicar = useCallback(
    async (request: DeduplicarRequest) => {
      setIsLoading(true);
      setError(null);
      setResult(null);
      try {
        const res = await apiClient.deduplicar(request);
        setResult(res);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Error al deduplicar archivos');
      } finally {
        setIsLoading(false);
      }
    },
    [apiClient],
  );

  const reset = useCallback(() => {
    setResult(null);
    setError(null);
    setIsLoading(false);
  }, []);

  return { organizar, renombrar, deduplicar, result, isLoading, error, reset };
}

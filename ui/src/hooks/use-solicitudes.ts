'use client';

import { useCallback, useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { Solicitud } from '@/lib/types';

interface UseSolicitudesState {
  solicitudes: Solicitud[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
}

/**
 * Lista las solicitudes de descarga WS de una empresa (más recientes primero),
 * tal como el agente las persiste en `~/.sat-descarga/solicitudes/{RFC}.json`.
 *
 * Si `rfc` es null, devuelve una lista vacía sin pegarle al agente.
 */
export function useSolicitudes(rfc: string | null): UseSolicitudesState {
  const { apiClient } = useServer();
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    if (!rfc) {
      setSolicitudes([]);
      setError(null);
      return;
    }
    let mounted = true;
    setLoading(true);
    apiClient
      .listSolicitudes(rfc)
      .then((r) => {
        if (mounted) {
          setSolicitudes(r.solicitudes);
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
  }, [apiClient, rfc, tick]);

  return { solicitudes, loading, error, refresh };
}

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import type { SatApiClient } from '@/lib/api-client';
import { HEALTH_POLL_INTERVAL_MS } from '@/lib/constants';

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

interface ServerHealthState {
  /** Whether the last health check succeeded. */
  isConnected: boolean;
  /** RFC loaded on the server (null if no FIEL is loaded). */
  rfcCargado: string | null;
  /** Whether the server has a FIEL loaded and ready. */
  efirmaLista: boolean;
  /** Manually trigger an immediate health check. */
  refresh: () => void;
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

/**
 * Polls the Python server's /health endpoint at a fixed interval.
 *
 * - On success: sets `isConnected = true` and extracts `rfc_cargado` /
 *   `efirma_lista` from the response.
 * - On failure (network error, server down): sets `isConnected = false`.
 * - Cleans up the interval on unmount.
 *
 * @param apiClient - A `SatApiClient` instance (should be a stable reference).
 * @param intervalMs - Polling interval in milliseconds (default 5 000).
 */
export function useServerHealth(
  apiClient: SatApiClient,
  intervalMs: number = HEALTH_POLL_INTERVAL_MS,
): ServerHealthState {
  const [isConnected, setIsConnected] = useState(false);
  const [rfcCargado, setRfcCargado] = useState<string | null>(null);
  const [efirmaLista, setEfirmaLista] = useState(false);

  // Ref to track whether we should still process the result (component mounted).
  const mountedRef = useRef(true);

  // Counter to force an immediate check (bumped by `refresh()`).
  const [refreshCounter, setRefreshCounter] = useState(0);

  const checkHealth = useCallback(async () => {
    try {
      const data = await apiClient.health();
      if (!mountedRef.current) return;

      setIsConnected(true);
      setRfcCargado(data.rfc_cargado);
      setEfirmaLista(data.efirma_lista);
    } catch {
      if (!mountedRef.current) return;

      setIsConnected(false);
      setRfcCargado(null);
      setEfirmaLista(false);
    }
  }, [apiClient]);

  // Run on mount and whenever refreshCounter changes (manual refresh).
  useEffect(() => {
    checkHealth();
  }, [checkHealth, refreshCounter]);

  // Periodic polling
  useEffect(() => {
    mountedRef.current = true;

    const id = setInterval(checkHealth, intervalMs);

    return () => {
      mountedRef.current = false;
      clearInterval(id);
    };
  }, [checkHealth, intervalMs]);

  const refresh = useCallback(() => {
    setRefreshCounter((c) => c + 1);
  }, []);

  return { isConnected, rfcCargado, efirmaLista, refresh };
}

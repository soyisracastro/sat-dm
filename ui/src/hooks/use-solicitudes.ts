'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { Solicitud } from '@/lib/types';

// Estados que NO han terminado: las solicitudes con estos estados deben re-pollearse.
// "3"/"4"/"5"/"descargada" son terminales (lista/error/rechazada/descargada).
const ESTADOS_NO_TERMINALES = new Set(['solicitada', '1', '2']);
const POLL_INTERVAL_MS = 15_000;

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

  // Auto-poll de solicitudes no-terminales: cuando hay alguna que sigue en cola o
  // procesando (incluyendo la primera de un "Ambos" que NO está en el active flow),
  // periódicamente pegamos a /verificar para que el agente actualice su estado en
  // el catálogo, y refrescamos la lista. Sin esto, esa solicitud quedaría "atorada"
  // visualmente como "Solicitada".
  const idsNoTerminales = useMemo(
    () =>
      solicitudes
        .filter((s) => ESTADOS_NO_TERMINALES.has(s.estado))
        .map((s) => s.id_solicitud),
    [solicitudes],
  );

  useEffect(() => {
    if (!rfc || idsNoTerminales.length === 0) return;
    const interval = setInterval(async () => {
      await Promise.all(
        idsNoTerminales.map((id) =>
          apiClient.verificar({ id_solicitud: id, poll: false }).catch(() => null),
        ),
      );
      refresh();
    }, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [apiClient, rfc, idsNoTerminales, refresh]);

  return { solicitudes, loading, error, refresh };
}

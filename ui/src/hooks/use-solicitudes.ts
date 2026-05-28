'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { notifyDescargaCompleta, notifyDescargaError } from '@/lib/notify';
import type { Solicitud } from '@/lib/types';

// Estados que NO han terminado: las solicitudes con estos estados deben re-pollearse.
// "3"/"4"/"5"/"descargada" son terminales (lista/error/rechazada/descargada).
const ESTADOS_NO_TERMINALES = new Set(['solicitada', '1', '2']);
const POLL_INTERVAL_MS = 15_000;

// Transiciones a estos estados disparan notificación.
const ESTADO_LISTA = '3';
const ESTADOS_ERROR = new Set(['4', '5']);

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

  // Estados previos por id_solicitud para detectar transiciones a terminal.
  // Se reinicia cuando cambia el RFC (cambiar empresa no debe disparar notif).
  const estadosPrevRef = useRef<Map<string, string>>(new Map());
  useEffect(() => {
    estadosPrevRef.current = new Map();
  }, [rfc]);

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
          detectarYNotificarTransiciones(r.solicitudes, estadosPrevRef.current, rfc);
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

/**
 * Compara el estado actual de cada solicitud contra el snapshot previo y
 * dispara notificaciones cuando hay transición desde un estado no-terminal
 * hacia "lista" (3) o "error" (4/5). En el primer load `prev` está vacío
 * y no se dispara nada (evita ruido al cargar la página).
 */
function detectarYNotificarTransiciones(
  actuales: Solicitud[],
  prev: Map<string, string>,
  rfc: string,
): void {
  if (prev.size === 0) {
    for (const s of actuales) prev.set(s.id_solicitud, s.estado);
    return;
  }
  for (const s of actuales) {
    const prevEstado = prev.get(s.id_solicitud);
    prev.set(s.id_solicitud, s.estado);
    if (prevEstado === undefined) continue; // nueva solicitud creada en este ciclo
    if (prevEstado === s.estado) continue;
    if (!ESTADOS_NO_TERMINALES.has(prevEstado)) continue;

    if (s.estado === ESTADO_LISTA) {
      notifyDescargaCompleta({
        canal: 'ws',
        rfc,
        count: s.numero_cfdis,
        jobId: s.id_solicitud,
      });
    } else if (ESTADOS_ERROR.has(s.estado)) {
      notifyDescargaError({
        canal: 'ws',
        rfc,
        motivo: s.mensaje,
        jobId: s.id_solicitud,
      });
    }
  }
}

'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { notifyDescargaCompleta, notifyDescargaError } from '@/lib/notify';
import type { Solicitud } from '@/lib/types';
import type { SatApiClient } from '@/lib/api-client';

// Estados que NO han terminado: las solicitudes con estos estados deben re-pollearse.
// "3"/"4"/"5"/"descargada" son terminales (lista/error/rechazada/descargada).
const ESTADOS_NO_TERMINALES = new Set(['solicitada', '1', '2']);
const POLL_INTERVAL_MS = 15_000;

// Transiciones a estos estados disparan notificación.
const ESTADO_LISTA = '3';
const ESTADOS_ERROR = new Set(['4', '5']);

// Clave en localStorage que `useDescarga` usa para trackear la solicitud
// que está en el "active flow" (la última de un Ambos, o la única si es E o R).
// Esa la maneja el propio hook (polling + auto-descarga), así que NO debemos
// disparar /descargar para ella desde aquí — provocaría doble HTTP request.
const ACTIVE_FLOW_LS_KEY = 'sat-dm-request-id';

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
  // Solicitudes para las que ya disparamos auto-descarga en esta sesión
  // (dedup por id; sobrevive a refreshes rápidos consecutivos).
  const autoDescargadasRef = useRef<Set<string>>(new Set());
  useEffect(() => {
    estadosPrevRef.current = new Map();
    autoDescargadasRef.current = new Set();
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
          procesarTransiciones(
            r.solicitudes,
            estadosPrevRef.current,
            autoDescargadasRef.current,
            rfc,
            apiClient,
            refresh,
          );
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
  }, [apiClient, rfc, tick, refresh]);

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
 * Compara el estado actual de cada solicitud contra el snapshot previo y,
 * para las que transitan desde no-terminal:
 *   - hacia "lista" (3): dispara notificación de éxito Y auto-descarga
 *     (apiClient.descargar). Skip si la solicitud la maneja el active flow
 *     (useDescarga, vía localStorage) o si ya la descargamos automáticamente.
 *   - hacia "error" (4/5): dispara notificación de error.
 *
 * En el primer load `prev` está vacío y no se dispara nada (evita ruido al
 * cargar la página).
 *
 * Esto cierra el caso del bug "Ambos": la previa (E) que el page envía
 * directo al catálogo sin pasar por el active flow ahora también baja sola
 * cuando el SAT la marca como Lista.
 */
function procesarTransiciones(
  actuales: Solicitud[],
  prev: Map<string, string>,
  autoDescargadas: Set<string>,
  rfc: string,
  apiClient: SatApiClient,
  refresh: () => void,
): void {
  if (prev.size === 0) {
    for (const s of actuales) prev.set(s.id_solicitud, s.estado);
    return;
  }

  const activeFlowId =
    typeof window !== 'undefined' ? window.localStorage.getItem(ACTIVE_FLOW_LS_KEY) : null;

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
      // Auto-descarga: skip si el active flow ya la tiene tomada o si ya
      // disparamos en este ciclo. Si falla, lo logueamos pero NO mostramos
      // error al usuario (el row queda en "Lista" y puede bajarse manual).
      if (
        s.id_solicitud !== activeFlowId &&
        !autoDescargadas.has(s.id_solicitud)
      ) {
        autoDescargadas.add(s.id_solicitud);
        apiClient
          .descargar(s.id_solicitud)
          .then(() => refresh())
          .catch((e: unknown) => {
            console.warn('[auto-descarga] falló para', s.id_solicitud, e);
          });
      }
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

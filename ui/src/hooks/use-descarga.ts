'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { VERIFICAR_POLL_INTERVAL_MS } from '@/lib/constants';
import type { SolicitudRequest } from '@/lib/types';

// ---------------------------------------------------------------------------
// State machine
// ---------------------------------------------------------------------------

export type DescargaState =
  | 'idle'
  | 'requesting'
  | 'polling'
  | 'ready'
  | 'downloading'
  | 'done'
  | 'error';

// ---------------------------------------------------------------------------
// LocalStorage key
// ---------------------------------------------------------------------------

const LS_KEY = 'sat-dm-request-id';

function loadRequestId(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(LS_KEY);
}

function saveRequestId(id: string | null) {
  if (typeof window === 'undefined') return;
  if (id) {
    localStorage.setItem(LS_KEY, id);
  } else {
    localStorage.removeItem(LS_KEY);
  }
}

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

export interface UseDescargaReturn {
  state: DescargaState;
  requestId: string | null;
  codEstado: number | null;
  mensaje: string | null;
  numeroCfdis: number | null;
  packageIds: string[];
  archivosDescargados: string[];
  error: string | null;
  solicitar: (request: SolicitudRequest) => Promise<void>;
  descargar: () => Promise<void>;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export function useDescarga(
  pollIntervalMs: number = VERIFICAR_POLL_INTERVAL_MS,
): UseDescargaReturn {
  const { apiClient } = useServer();

  const [state, setState] = useState<DescargaState>('idle');
  const [requestId, setRequestId] = useState<string | null>(null);
  const [codEstado, setCodEstado] = useState<number | null>(null);
  const [mensaje, setMensaje] = useState<string | null>(null);
  const [numeroCfdis, setNumeroCfdis] = useState<number | null>(null);
  const [packageIds, setPackageIds] = useState<string[]>([]);
  const [archivosDescargados, setArchivosDescargados] = useState<string[]>([]);
  const [error, setError] = useState<string | null>(null);

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const mountedRef = useRef(true);
  // RequestID para la cual ya disparamos la descarga automática al pasar a 'ready'.
  // Permite re-descargar manualmente (descargar() puede llamarse de nuevo) sin
  // que el efecto auto-dispare otra vez por el mismo state→ready transition.
  const autoDescargaDispatchedRef = useRef<string | null>(null);

  // -----------------------------------------------------------------------
  // Cleanup interval
  // -----------------------------------------------------------------------

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, []);

  // Evita encimar verificaciones si el SAT responde más lento que el intervalo.
  const pollBusyRef = useRef(false);

  // -----------------------------------------------------------------------
  // Poll once
  // -----------------------------------------------------------------------

  const pollOnce = useCallback(
    async (id: string) => {
      if (pollBusyRef.current) return;
      pollBusyRef.current = true;
      try {
        const res = await apiClient.verificar({ id_solicitud: id, poll: false });
        if (!mountedRef.current) return;

        // SAT returns cod_estado as string, coerce to number
        const codEstadoNum = Number(res.cod_estado);
        setCodEstado(codEstadoNum);
        setMensaje(res.mensaje);
        setNumeroCfdis(res.numero_cfdis);

        if (codEstadoNum === 3 || res.terminada) {
          // Ready to download
          setPackageIds(res.package_ids);
          setState('ready');
          stopPolling();
        } else if (codEstadoNum === 4 || codEstadoNum === 5) {
          // Error or rejected
          setError(res.mensaje || 'La solicitud fue rechazada o tuvo un error.');
          setState('error');
          stopPolling();
        }
        // cod_estado 1 or 2: keep polling
      } catch (err) {
        if (!mountedRef.current) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(`Error al verificar solicitud: ${msg}`);
        setState('error');
        stopPolling();
      } finally {
        pollBusyRef.current = false;
      }
    },
    [apiClient, stopPolling],
  );

  // -----------------------------------------------------------------------
  // Start polling loop
  // -----------------------------------------------------------------------

  const startPolling = useCallback(
    (id: string) => {
      stopPolling();
      setState('polling');

      // Poll immediately once
      pollOnce(id);

      // Then on interval
      intervalRef.current = setInterval(() => {
        pollOnce(id);
      }, pollIntervalMs);
    },
    [pollOnce, pollIntervalMs, stopPolling],
  );

  // -----------------------------------------------------------------------
  // solicitar
  // -----------------------------------------------------------------------

  const solicitar = useCallback(
    async (request: SolicitudRequest) => {
      try {
        setState('requesting');
        setError(null);
        setCodEstado(null);
        setMensaje(null);
        setNumeroCfdis(null);
        setPackageIds([]);
        setArchivosDescargados([]);

        const res = await apiClient.solicitar(request);
        if (!mountedRef.current) return;

        setRequestId(res.id_solicitud);
        saveRequestId(res.id_solicitud);
        startPolling(res.id_solicitud);
      } catch (err) {
        if (!mountedRef.current) return;
        const msg = err instanceof Error ? err.message : String(err);
        setError(`Error al solicitar descarga: ${msg}`);
        setState('error');
      }
    },
    [apiClient, startPolling],
  );

  // -----------------------------------------------------------------------
  // descargar
  // -----------------------------------------------------------------------

  const descargar = useCallback(async () => {
    if (!requestId) return;

    try {
      setState('downloading');
      setError(null);

      const res = await apiClient.descargar(requestId);
      if (!mountedRef.current) return;

      setArchivosDescargados(res.archivos);
      saveRequestId(null);
      setState('done');
    } catch (err) {
      if (!mountedRef.current) return;
      const msg = err instanceof Error ? err.message : String(err);
      setError(`Error al descargar: ${msg}`);
      setState('error');
    }
  }, [apiClient, requestId]);

  // -----------------------------------------------------------------------
  // reset
  // -----------------------------------------------------------------------

  const reset = useCallback(() => {
    stopPolling();
    setState('idle');
    setRequestId(null);
    setCodEstado(null);
    setMensaje(null);
    setNumeroCfdis(null);
    setPackageIds([]);
    setArchivosDescargados([]);
    setError(null);
    saveRequestId(null);
    autoDescargaDispatchedRef.current = null;
  }, [stopPolling]);

  // Auto-descarga: tan pronto la solicitud quede lista, dispara `descargar()`
  // una sola vez por solicitud (sin bloquear la re-descarga manual posterior).
  useEffect(() => {
    if (
      state === 'ready' &&
      requestId &&
      autoDescargaDispatchedRef.current !== requestId
    ) {
      autoDescargaDispatchedRef.current = requestId;
      void descargar();
    }
  }, [state, requestId, descargar]);

  // -----------------------------------------------------------------------
  // Resume polling on mount if localStorage has a requestId
  // -----------------------------------------------------------------------

  useEffect(() => {
    mountedRef.current = true;

    const savedId = loadRequestId();
    if (savedId) {
      setRequestId(savedId);
      startPolling(savedId);
    }

    return () => {
      mountedRef.current = false;
      stopPolling();
    };
    // Only run on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    state,
    requestId,
    codEstado,
    mensaje,
    numeroCfdis,
    packageIds,
    archivosDescargados,
    error,
    solicitar,
    descargar,
    reset,
  };
}

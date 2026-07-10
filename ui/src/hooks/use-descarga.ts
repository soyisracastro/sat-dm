'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { ApiError } from '@/lib/api-client';
import { VERIFICAR_POLL_INTERVAL_MS } from '@/lib/constants';
import type { SolicitudRequest } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

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
// LocalStorage: flujo activo POR EMPRESA
//
// La llave lleva el RFC (`sat-dm-request-id:XAXX010101000`). Antes era una
// llave global única: al cambiar de empresa, la página retomaba el polling de
// una solicitud de OTRA empresa y el "Estado de la solicitud" aparecía en
// todas (y /verificar iba firmado con la FIEL equivocada). Ver PR.
// ---------------------------------------------------------------------------

// Llave global legacy (pre-fix). Se elimina al montar para que una solicitud
// vieja no "resucite" en todas las empresas tras actualizar.
const LS_LEGACY_KEY = 'sat-dm-request-id';
// Una solicitud pendiente >72h ya venció para el SAT: no vale la pena retomarla.
const RESUME_MAX_AGE_MS = 72 * 60 * 60 * 1000;

function lsKey(rfc: string): string {
  return `sat-dm-request-id:${rfc}`;
}

function loadRequestId(rfc: string | null): string | null {
  if (typeof window === 'undefined' || !rfc) return null;
  const raw = localStorage.getItem(lsKey(rfc));
  if (!raw) return null;
  try {
    const { id, ts } = JSON.parse(raw) as { id?: string; ts?: number };
    if (!id) return null;
    if (typeof ts === 'number' && Date.now() - ts > RESUME_MAX_AGE_MS) {
      localStorage.removeItem(lsKey(rfc));
      return null;
    }
    return id;
  } catch {
    localStorage.removeItem(lsKey(rfc));
    return null;
  }
}

function saveRequestId(rfc: string | null, id: string | null) {
  if (typeof window === 'undefined' || !rfc) return;
  if (id) {
    localStorage.setItem(lsKey(rfc), JSON.stringify({ id, ts: Date.now() }));
  } else {
    localStorage.removeItem(lsKey(rfc));
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

/**
 * Flujo activo de descarga WS de UNA empresa (`rfc`): solicitar → polling →
 * descarga automática. El estado persistido en localStorage va aislado por
 * RFC, así que cambiar de empresa nunca arrastra la solicitud de otra.
 */
export function useDescarga(
  rfc: string | null,
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
  // El RFC vigente, para que los callbacks asíncronos no escriban en la llave
  // de otra empresa si el usuario cambió mientras el request estaba en vuelo.
  const rfcRef = useRef(rfc);
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

        // Sin cod_estado = el SAT no reconoce la solicitud para esta e.firma
        // (típicamente pertenece a otra empresa, o ya caducó en el SAT).
        // Cerramos el flujo y limpiamos para no pollearla eternamente.
        if (!res.cod_estado) {
          setError(
            res.mensaje ||
              'El SAT no reconoce esta solicitud para la empresa activa. Crea una nueva solicitud.',
          );
          setState('error');
          stopPolling();
          saveRequestId(rfcRef.current, null);
          return;
        }

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
        } else if (codEstadoNum === 4 || codEstadoNum === 5 || codEstadoNum === 6) {
          // Error, rechazada o vencida: estado final — el agente ya lo persistió
          // en el catálogo; aquí cerramos el flujo activo.
          setError(res.mensaje || 'La solicitud fue rechazada o tuvo un error.');
          setState('error');
          stopPolling();
          saveRequestId(rfcRef.current, null);
        }
        // cod_estado 1 or 2: keep polling
      } catch (err) {
        if (!mountedRef.current) return;
        const msg = mensajeDeError(err);
        setError(`Error al verificar solicitud: ${msg}`);
        setState('error');
        stopPolling();
        // Un 400 del agente es un rechazo definitivo (no reintentable);
        // errores de red / 401 / 5xx son transitorios y el flujo se retoma
        // en el siguiente mount (el poller del agente sigue trabajando).
        if (err instanceof ApiError && err.status === 400) {
          saveRequestId(rfcRef.current, null);
        }
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
        saveRequestId(rfcRef.current, res.id_solicitud);
        startPolling(res.id_solicitud);
      } catch (err) {
        if (!mountedRef.current) return;
        const msg = mensajeDeError(err);
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
      saveRequestId(rfcRef.current, null);
      setState('done');
    } catch (err) {
      if (!mountedRef.current) return;
      // 409 = el poller en background ya está bajando esta solicitud: no es un
      // error para el usuario; el catálogo quedará en "Descargada" solo.
      if (err instanceof ApiError && err.status === 409) {
        saveRequestId(rfcRef.current, null);
        setState('done');
        return;
      }
      const msg = mensajeDeError(err);
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
    saveRequestId(rfcRef.current, null);
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
  // Por empresa: al montar Y al cambiar de RFC se limpia el estado en memoria
  // y se retoma el polling SOLO si esta empresa dejó una solicitud pendiente.
  // -----------------------------------------------------------------------

  useEffect(() => {
    mountedRef.current = true;
    rfcRef.current = rfc;

    // Migración: la llave global legacy hacía que una solicitud apareciera en
    // TODAS las empresas. Se elimina sin retomarla; si sigue viva, el poller
    // del agente y la lista de solicitudes la resuelven por su cuenta.
    if (typeof window !== 'undefined') {
      localStorage.removeItem(LS_LEGACY_KEY);
    }

    // Cambio de empresa: estado en memoria a cero (sin tocar localStorage de
    // la empresa anterior — su flujo sigue guardado y el poller lo atiende).
    stopPolling();
    setState('idle');
    setRequestId(null);
    setCodEstado(null);
    setMensaje(null);
    setNumeroCfdis(null);
    setPackageIds([]);
    setArchivosDescargados([]);
    setError(null);
    autoDescargaDispatchedRef.current = null;

    const savedId = loadRequestId(rfc);
    if (savedId) {
      setRequestId(savedId);
      startPolling(savedId);
    }

    return () => {
      mountedRef.current = false;
      stopPolling();
    };
    // Reinicia solo cuando cambia la empresa activa.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rfc]);

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

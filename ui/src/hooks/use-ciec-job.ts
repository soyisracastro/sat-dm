'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { notifyDescargaCompleta, notifyDescargaError } from '@/lib/notify';
import type { JobEvent } from '@/lib/types';
import { mensajeAmigable, mensajeDeError } from '@/lib/errores';

export type JobUiEstado =
  | 'idle'
  | 'iniciando'
  | 'corriendo'
  | 'captcha'
  | 'done'
  | 'error'
  | 'cancelled';

export interface CaptchaState {
  imagen: string; // data:image/jpeg;base64,...
  intento: number;
  max: number;
}

export interface LogEntry {
  t: string;
  msg: string;
  level?: 'info' | 'ok' | 'warn' | 'error';
}

export interface JobMeta {
  /** RFC asociado al job; si se provee, se dispara una notificación al terminar/fallar. */
  rfc?: string;
}

// Tope FIFO del log: un job largo puede emitir miles de eventos; sin límite,
// cada evento re-renderiza una lista cada vez más grande y la memoria crece
// durante toda la descarga.
const MAX_LOG_ENTRIES = 500;

interface UseCiecJob {
  estado: JobUiEstado;
  log: LogEntry[];
  captcha: CaptchaState | null;
  resultado: unknown;
  error: string | null;
  /** Arranca un job: `starter` llama al endpoint (ciecCfdi/…) y devuelve { job_id }. */
  iniciar: (
    starter: () => Promise<{ job_id: string }>,
    meta?: JobMeta,
  ) => Promise<void>;
  /** Entrega el captcha tecleado, o null para cancelar. */
  responderCaptcha: (texto: string | null) => Promise<void>;
  reset: () => void;
}

/**
 * Orquesta un job CIEC del agente: lo arranca, se suscribe a su stream SSE
 * (`/events/{id}`) y traduce los eventos (estado, captcha_required, done, error,
 * cancelled) a estado de UI + un log estilo terminal. El captcha se resuelve por HTTP
 * (`responderCaptcha`), que es lo que reanuda el scraping headless en el agente.
 */
export function useCiecJob(): UseCiecJob {
  const { apiClient } = useServer();
  const [estado, setEstado] = useState<JobUiEstado>('idle');
  const [log, setLog] = useState<LogEntry[]>([]);
  const [captcha, setCaptcha] = useState<CaptchaState | null>(null);
  const [resultado, setResultado] = useState<unknown>(null);
  const [error, setError] = useState<string | null>(null);

  const jobIdRef = useRef<string | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const metaRef = useRef<JobMeta>({});

  const addLog = useCallback((msg: string, level: LogEntry['level'] = 'info') => {
    setLog((l) =>
      [...l, { t: new Date().toLocaleTimeString('es-MX'), msg, level }].slice(-MAX_LOG_ENTRIES),
    );
  }, []);

  const cerrarStream = useCallback(() => {
    esRef.current?.close();
    esRef.current = null;
  }, []);

  // Cerrar el EventSource si el componente se desmonta.
  useEffect(() => () => cerrarStream(), [cerrarStream]);

  const reset = useCallback(() => {
    cerrarStream();
    jobIdRef.current = null;
    setEstado('idle');
    setLog([]);
    setCaptcha(null);
    setResultado(null);
    setError(null);
  }, [cerrarStream]);

  const onEvent = useCallback(
    (ev: JobEvent) => {
      switch (ev.event) {
        case 'estado':
          setEstado('corriendo');
          setCaptcha(null);
          addLog(`estado: ${ev.estado}`);
          break;
        case 'captcha_required':
          setEstado('captcha');
          setCaptcha({
            imagen: ev.imagen ?? '',
            intento: ev.intento ?? 1,
            max: ev.max ?? 3,
          });
          addLog(`captcha solicitado (intento ${ev.intento}/${ev.max})`, 'warn');
          break;
        case 'captcha_timeout':
          // Cierra el modal de inmediato y avisa al usuario; el cambio a
          // 'cancelled' llega del backend en su propio evento.
          setCaptcha(null);
          setError('El captcha expiró (pasaron 5 minutos sin respuesta). Inicia la descarga de nuevo.');
          addLog('captcha: tiempo agotado', 'warn');
          break;
        case 'log':
          // Mensajes informativos del worker (p. ej. "Preparando el navegador
          // de descargas…" mientras baja Chromium la primera vez).
          addLog(ev.mensaje ?? '', ev.nivel ?? 'info');
          break;
        case 'done': {
          setEstado('done');
          setResultado(ev.resultado ?? null);
          setCaptcha(null);
          addLog('descarga completada', 'ok');
          cerrarStream();
          const rfc = metaRef.current.rfc;
          if (rfc) {
            const resultado = ev.resultado as { count?: number; total?: number } | null | undefined;
            const count = resultado?.count ?? resultado?.total;
            notifyDescargaCompleta({
              canal: 'ciec',
              rfc,
              count,
              jobId: jobIdRef.current ?? undefined,
            });
          }
          break;
        }
        case 'error': {
          const motivo = mensajeAmigable(ev.mensaje ?? 'Error');
          setEstado('error');
          setError(motivo);
          setCaptcha(null);
          addLog(`error: ${motivo}`, 'error');
          cerrarStream();
          const rfc = metaRef.current.rfc;
          if (rfc) {
            notifyDescargaError({
              canal: 'ciec',
              rfc,
              motivo,
              jobId: jobIdRef.current ?? undefined,
            });
          }
          break;
        }
        case 'cancelled':
          setEstado('cancelled');
          setCaptcha(null);
          addLog(`cancelado: ${ev.mensaje ?? ''}`, 'warn');
          cerrarStream();
          break;
      }
    },
    [addLog, cerrarStream],
  );

  const iniciar = useCallback(
    async (starter: () => Promise<{ job_id: string }>, meta: JobMeta = {}) => {
      reset();
      metaRef.current = meta;
      setEstado('iniciando');
      try {
        const { job_id } = await starter();
        jobIdRef.current = job_id;
        setEstado('corriendo');
        addLog('job iniciado');
        esRef.current = apiClient.subscribeJob(job_id, onEvent);
      } catch (e) {
        setEstado('error');
        setError(mensajeDeError(e));
        if (meta.rfc) {
          notifyDescargaError({
            canal: 'ciec',
            rfc: meta.rfc,
            motivo: mensajeDeError(e),
          });
        }
      }
    },
    [apiClient, reset, addLog, onEvent],
  );

  const responderCaptcha = useCallback(
    async (texto: string | null) => {
      const id = jobIdRef.current;
      if (!id) return;
      setCaptcha(null);
      if (texto !== null) setEstado('corriendo');
      await apiClient.responderCaptcha(id, texto);
    },
    [apiClient],
  );

  return { estado, log, captcha, resultado, error, iniciar, responderCaptcha, reset };
}

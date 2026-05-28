/**
 * API pública de notificaciones.
 *
 * PR1: solo sonner (in-app). El gating por foco y el transporte nativo
 * se agregan en PR3 sin cambiar la firma pública.
 *
 * Cada función:
 *   1. Lee prefs (si el toggle está OFF, no-op).
 *   2. Elige un mensaje aleatorio del pool correspondiente.
 *   3. Dispara `toast.success | error | info` con un `id` derivado para
 *      deduplicar si el mismo evento llega más de una vez.
 */

import { toast } from 'sonner';

import {
  type DescargaCanal,
  mensajeDescargaError,
  mensajeDescargaSuccess,
  mensajeEfirmaAviso,
} from './messages';
import { getNotifPrefs } from './prefs';

const DURATION = {
  success: 5_000,
  error: 7_000,
  info: 5_000,
};

export interface NotifyDescargaCompletaArgs {
  canal: DescargaCanal;
  rfc: string;
  count?: number;
  jobId?: string;
}

export function notifyDescargaCompleta(args: NotifyDescargaCompletaArgs): void {
  if (!getNotifPrefs().descargas) return;
  const id = `descarga:${args.canal}:${args.rfc}:${args.jobId ?? 'ok'}`;
  const mensaje = mensajeDescargaSuccess(args.canal, { count: args.count, rfc: args.rfc });
  toast.success(mensaje, { id, duration: DURATION.success });
}

export interface NotifyDescargaErrorArgs {
  canal: DescargaCanal;
  rfc: string;
  motivo?: string;
  jobId?: string;
}

export function notifyDescargaError(args: NotifyDescargaErrorArgs): void {
  if (!getNotifPrefs().descargas) return;
  const id = `descarga:${args.canal}:${args.rfc}:${args.jobId ?? 'err'}`;
  const mensaje = mensajeDescargaError(args.canal, {
    rfc: args.rfc,
    motivo: args.motivo ?? 'Revisa el detalle.',
  });
  toast.error(mensaje, { id, duration: DURATION.error });
}

export interface NotifyEfirmaArgs {
  /** Lista de e.firmas en riesgo (≤30 días), ordenadas por urgencia ascendente. */
  rfcs: Array<{ rfc: string; dias: number }>;
}

export function notifyEfirmaVencimiento(args: NotifyEfirmaArgs): void {
  if (!getNotifPrefs().efirma) return;
  if (args.rfcs.length === 0) return;
  const proxima = args.rfcs[0];
  const id = `efirma:${new Date().toISOString().slice(0, 10)}`;
  const mensaje = mensajeEfirmaAviso({
    n: args.rfcs.length,
    rfc: proxima.rfc,
    dias: proxima.dias,
  });
  toast.warning(mensaje, { id, duration: DURATION.info });
}

/** Para el botón "Probar notificación" en Ajustes. */
export function notifyPrueba(): void {
  toast.success('Si ves esto, las notificaciones in-app están funcionando.', {
    id: 'prueba',
    duration: 4_000,
  });
}

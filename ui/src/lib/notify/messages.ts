/**
 * Pools de mensajes para toasts. Patrón replicado de
 * `todoconta-apps/apps/web/src/lib/toasts/long-running.ts`:
 * mensajes cálidos, en tono mexicano profesional, 3-5 variantes
 * por contexto/timing. Se elige una al azar por evento.
 *
 * Interpolación: {count}, {rfc}, {motivo}, {n}, {dias}.
 */

export type DescargaCanal = 'ws' | 'ciec';

interface Pool {
  success: string[];
  error: string[];
}

const POOLS_DESCARGA: Record<DescargaCanal, Pool> = {
  ws: {
    success: [
      'Listo: {count} CFDIs descargados para {rfc}.',
      'El SAT respondió. Tienes {count} comprobantes nuevos en {rfc}.',
      'Descarga WS completa: {count} XMLs guardados.',
      'Solicitud lista, {count} CFDIs disponibles para {rfc}.',
    ],
    error: [
      'La descarga WS de {rfc} falló. {motivo}',
      'El SAT rechazó la solicitud de {rfc}. Revisa el detalle.',
      'No pudimos terminar la descarga WS. {motivo}',
    ],
  },
  ciec: {
    success: [
      'Descargamos {count} CFDIs vía CIEC para {rfc}.',
      'Listo, {count} XMLs guardados desde el portal.',
      'Descarga CIEC completa: {count} comprobantes para {rfc}.',
    ],
    error: [
      'La descarga CIEC de {rfc} falló. {motivo}',
      'No pudimos completar la descarga del portal. {motivo}',
    ],
  },
};

const POOL_EFIRMA_AVISO = [
  'Tienes {n} e.firmas por vencer. La más próxima: {rfc} en {dias} días.',
  'Recordatorio: la e.firma de {rfc} vence en {dias} días ({n} en total).',
  '{n} e.firmas necesitan renovación. La que urge: {rfc} a {dias} días.',
];

interface Vars {
  count?: number;
  rfc?: string;
  motivo?: string;
  n?: number;
  dias?: number;
}

function interpolate(template: string, vars: Vars): string {
  return template
    .replace(/\{count\}/g, vars.count != null ? String(vars.count) : '')
    .replace(/\{rfc\}/g, vars.rfc ?? '')
    .replace(/\{motivo\}/g, vars.motivo ?? '')
    .replace(/\{n\}/g, vars.n != null ? String(vars.n) : '')
    .replace(/\{dias\}/g, vars.dias != null ? String(vars.dias) : '');
}

function pick<T>(pool: T[]): T {
  return pool[Math.floor(Math.random() * pool.length)];
}

export function mensajeDescargaSuccess(canal: DescargaCanal, vars: Vars): string {
  return interpolate(pick(POOLS_DESCARGA[canal].success), vars);
}

export function mensajeDescargaError(canal: DescargaCanal, vars: Vars): string {
  return interpolate(pick(POOLS_DESCARGA[canal].error), vars);
}

export function mensajeEfirmaAviso(vars: Vars): string {
  return interpolate(pick(POOL_EFIRMA_AVISO), vars);
}

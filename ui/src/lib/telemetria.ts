// Telemetría de errores del renderer (Sentry), vía @sentry/electron/renderer.
//
// El SDK del renderer reenvía los eventos al proceso main por IPC; el DSN y el
// envío real viven en main (ver desktop/main.js). Aquí solo inicializamos (solo
// dentro de Electron) y exponemos helpers para capturar excepciones, dejar
// breadcrumbs y mandar el feedback del usuario.
//
// Sin Electron (navegador/dev) todo es no-op. Privacidad: un beforeSend redacta
// RFCs y rutas con nombre de usuario antes de enviar (main hace lo mismo + adjunta
// el log); nunca se envían e.firma, contraseñas ni datos fiscales.

type SentryRenderer = typeof import('@sentry/electron/renderer');

let sentry: SentryRenderer | null = null;
let activo = false;

function esDesktop(): boolean {
  if (typeof window === 'undefined') return false;
  return !!(window as unknown as { satAgent?: { isDesktop?: boolean } }).satAgent?.isDesktop;
}

const RFC_RE = /\b[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{2,3}\b/g;
const HOME_RES: Array<[RegExp, string]> = [
  [/([A-Za-z]:\\Users\\)[^\\/]+/gi, '$1<usuario>'],
  [/(\/Users\/)[^/]+/g, '$1<usuario>'],
  [/(\/home\/)[^/]+/g, '$1<usuario>'],
];

function redactarTexto(s: string): string {
  let out = s.replace(RFC_RE, '<RFC>');
  for (const [re, rep] of HOME_RES) out = out.replace(re, rep);
  return out;
}

function scrub(value: unknown): unknown {
  if (typeof value === 'string') return redactarTexto(value);
  if (Array.isArray(value)) return value.map(scrub);
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>;
    for (const k of Object.keys(obj)) {
      if (/(password|contrase|ciec|secreto|secret|token|api[_-]?key)/i.test(k)) {
        obj[k] = '<redactado>';
      } else {
        obj[k] = scrub(obj[k]);
      }
    }
  }
  return value;
}

/** Inicializa Sentry en el renderer (solo dentro de Electron; idempotente). */
export async function initTelemetria(): Promise<void> {
  if (activo || !esDesktop()) return;
  try {
    const mod = await import('@sentry/electron/renderer');
    mod.init({
      // El DSN/transport los pone el proceso main; aquí solo el scrub local.
      beforeSend: (event) => scrub(event) as typeof event,
    });
    sentry = mod;
    activo = true;
  } catch {
    // best-effort: la telemetría nunca debe romper el arranque del renderer.
  }
}

/** Reporta una excepción si la telemetría está activa; no-op si no. */
export function capturarExcepcion(error: unknown, contexto?: Record<string, unknown>): void {
  if (!activo || !sentry) return;
  sentry.captureException(error, contexto ? { extra: contexto } : undefined);
}

/** Deja una miga (breadcrumb) si la telemetría está activa; no-op si no. */
export function agregarBreadcrumb(crumb: { category?: string; message?: string; level?: 'info' | 'warning' | 'error'; data?: Record<string, unknown> }): void {
  if (!activo || !sentry) return;
  sentry.addBreadcrumb(crumb);
}

/**
 * Envía el feedback del usuario (botón "Reportar un problema"), vinculándolo al
 * último evento si lo hay. Devuelve true si se envió, false si la telemetría no
 * está activa (navegador/dev o sin DSN).
 */
export function reportarProblema(input: { mensaje: string; email?: string; nombre?: string }): boolean {
  if (!activo || !sentry) return false;
  sentry.captureFeedback({
    message: input.mensaje,
    email: input.email,
    name: input.nombre,
    associatedEventId: sentry.lastEventId(),
  });
  return true;
}

/** ¿La telemetría quedó activa? (para decidir si mostrar el botón de reporte). */
export function telemetriaActiva(): boolean {
  return activo;
}

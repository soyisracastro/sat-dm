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

// Solo inicializamos si el proceso main de Electron habilitó Sentry (window.satAgent
// .sentry === true). En el navegador/dev sin DSN es false → no se inicializa el SDK
// del renderer (evita el "failed to establish connection with the Electron main
// process", porque sin Sentry en main no hay con quién conectarse).
function sentryHabilitado(): boolean {
  if (typeof window === 'undefined') return false;
  return (window as unknown as { satAgent?: { sentry?: boolean } }).satAgent?.sentry === true;
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
  if (activo || !sentryHabilitado()) return;
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

/**
 * Asocia (o desliga) el usuario autenticado a los eventos de Sentry. La app es
 * solo para usuarios registrados, así que el `id`/`email` identifican de quién
 * viene cada reporte — sin exponer nada sensible: la e.firma, las contraseñas y
 * los datos fiscales se siguen redactando en `beforeSend`. Pasa `null` (o un
 * usuario vacío) al cerrar sesión para desligar.
 *
 * `@sentry/electron` sincroniza el scope del renderer hacia el proceso main, así
 * que este `setUser` también queda en los eventos del main (p. ej. los errores
 * del auto-update, que ocurren fuera del renderer).
 */
export function identificarUsuario(
  user: { id?: string | null; email?: string | null } | null,
): void {
  if (!activo || !sentry) return;
  if (!user || (!user.id && !user.email)) {
    sentry.setUser(null);
    return;
  }
  sentry.setUser({
    id: user.id ?? undefined,
    email: user.email ?? undefined,
  });
}

/** Deja una miga (breadcrumb) si la telemetría está activa; no-op si no. */
export function agregarBreadcrumb(crumb: { category?: string; message?: string; level?: 'info' | 'warning' | 'error'; data?: Record<string, unknown> }): void {
  if (!activo || !sentry) return;
  sentry.addBreadcrumb(crumb);
}

/**
 * Envía el reporte del usuario (botón "Reportar un problema"). Devuelve true si se
 * envió, false si la telemetría no está activa (navegador/dev sin DSN).
 *
 * Manda DOS cosas:
 *  - `captureMessage` → crea un **Issue** en Sentry, así dispara la alerta de
 *    "nuevo issue" por correo y aparece en la lista de Issues (donde uno mira).
 *  - `captureFeedback` → además queda en la bandeja "User Feedback", vinculado al
 *    issue anterior (vista más rica con el correo de contacto).
 * Sin esto, un feedback suelto NO aparece en Issues ni dispara alertas de issue.
 */
export function reportarProblema(input: { mensaje: string; email?: string; nombre?: string }): boolean {
  if (!activo || !sentry) return false;
  const eventId = sentry.captureMessage(`Reporte del usuario: ${input.mensaje}`, {
    level: 'info',
    tags: { tipo: 'reporte_usuario' },
    user: input.email ? { email: input.email } : undefined,
    extra: { mensaje: input.mensaje },
  });
  try {
    sentry.captureFeedback({
      message: input.mensaje,
      email: input.email,
      name: input.nombre,
      associatedEventId: eventId,
    });
  } catch {
    /* el feedback es secundario; el issue ya quedó */
  }
  return true;
}

/** ¿La telemetría quedó activa? (para decidir si mostrar el botón de reporte). */
export function telemetriaActiva(): boolean {
  return activo;
}

/**
 * Traduce mensajes de error técnicos conocidos a un mensaje accionable en
 * español. Red de seguridad final: el backend ya intenta producir mensajes
 * amigables, pero errores crudos de Playwright (p. ej. el browser ausente
 * tras una actualización) pueden colarse por los endpoints síncronos.
 */
export function mensajeAmigable(msg: string): string {
  if (/Executable doesn't exist|playwright install|BrowserType\.launch/i.test(msg)) {
    return (
      'Falta el navegador de descargas en este equipo. Se instalará ' +
      'automáticamente; espera un momento y vuelve a intentar.'
    );
  }
  return msg;
}

/**
 * Extrae un mensaje legible de cualquier valor capturado en un `catch`.
 * Centraliza el patrón `e instanceof Error ? e.message : String(e)`.
 *
 * Para `ApiError` prefiere su campo `detail` (mensaje del backend, ya en español)
 * sobre `message`, que trae el prefijo técnico "[502] …" que no debe ver el
 * usuario final. El status sigue disponible en el objeto y se reporta a Sentry.
 */
export function mensajeDeError(e: unknown): string {
  if (
    e &&
    typeof e === 'object' &&
    'detail' in e &&
    typeof (e as { detail: unknown }).detail === 'string' &&
    (e as { detail: string }).detail.trim() !== ''
  ) {
    return mensajeAmigable((e as { detail: string }).detail);
  }
  if (e instanceof Error) return mensajeAmigable(e.message);
  if (typeof e === 'string') return mensajeAmigable(e);
  return mensajeAmigable(String(e));
}

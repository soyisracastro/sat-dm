/**
 * Extrae un mensaje legible de cualquier valor capturado en un `catch`.
 * Centraliza el patrón `e instanceof Error ? e.message : String(e)`.
 */
export function mensajeDeError(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === 'string') return e;
  return String(e);
}

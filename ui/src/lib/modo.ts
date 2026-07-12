// ---------------------------------------------------------------------------
// Modo de ejecución del renderer: desktop (Electron) o web (app.todoconta.com).
//
// El modo web es un BUILD distinto (env NEXT_PUBLIC_MODO_WEB=1 en el proyecto
// de Vercel): así "dev en navegador contra un agente local" nunca se confunde
// con la versión web de producción. El bundle desktop no cambia.
// ---------------------------------------------------------------------------

/**
 * True cuando este build es la versión web Y no está corriendo dentro de
 * Electron (el preload inyecta `window.satAgent`).
 */
export function esWeb(): boolean {
  if (process.env.NEXT_PUBLIC_MODO_WEB !== '1') return false;
  if (typeof window === 'undefined') return true; // prerender del build web
  return !(window as unknown as { satAgent?: unknown }).satAgent;
}

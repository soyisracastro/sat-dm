'use strict';
/*
 * Preload de Electron: puente mínimo y seguro entre el proceso main y el renderer.
 *
 * Por ahora solo expone el base URL del agente (que el main pasó como argumento)
 * para que el renderer (ui/) apunte sus llamadas HTTP al puerto efímero correcto.
 * Aquí se irán agregando, detrás de contextBridge, los file pickers nativos
 * (.cer/.key), revelar archivos en el explorador, etc. El renderer NUNCA toca Node.
 */

const { contextBridge } = require('electron');

function leerAgentUrl() {
  const arg = process.argv.find((a) => a.startsWith('--sat-agent-url='));
  if (!arg) return null;
  const url = arg.slice('--sat-agent-url='.length);
  return url || null;
}

contextBridge.exposeInMainWorld('satAgent', {
  /** Base URL del agente Python local (http://127.0.0.1:<puerto efímero>). */
  baseUrl: leerAgentUrl(),
  /** Marca para que el renderer sepa que corre dentro de Electron. */
  isDesktop: true,
});

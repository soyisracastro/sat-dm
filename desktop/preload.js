'use strict';
/*
 * Preload de Electron: puente mínimo y seguro entre el proceso main y el renderer.
 *
 * Por ahora solo expone el base URL del agente (que el main pasó como argumento)
 * para que el renderer (ui/) apunte sus llamadas HTTP al puerto efímero correcto.
 * Aquí se irán agregando, detrás de contextBridge, los file pickers nativos
 * (.cer/.key), revelar archivos en el explorador, etc. El renderer NUNCA toca Node.
 */

const { contextBridge, ipcRenderer } = require('electron');

function leerArg(prefijo) {
  const arg = process.argv.find((a) => a.startsWith(prefijo));
  if (!arg) return null;
  return arg.slice(prefijo.length) || null;
}

contextBridge.exposeInMainWorld('satAgent', {
  /** Base URL del agente Python local (http://127.0.0.1:<puerto efímero>). */
  baseUrl: leerArg('--sat-agent-url='),
  /**
   * Token efímero de autenticación con el agente (uno nuevo por arranque).
   * El agente rechaza requests sin él; va como header X-Agent-Token
   * (o ?token= en SSE, porque EventSource no acepta headers).
   */
  token: leerArg('--sat-agent-token='),
  /** Marca para que el renderer sepa que corre dentro de Electron. */
  isDesktop: true,
});

contextBridge.exposeInMainWorld('satDesktop', {
  /** Abre el selector de carpeta nativo del SO; devuelve la ruta o null. */
  elegirCarpeta: () => ipcRenderer.invoke('elegir-carpeta'),
  /**
   * Dispara una notificación nativa del SO (Windows Action Center / macOS
   * Notification Center). Click en la toast → enfoca la ventana de la app.
   * Devuelve true si el SO soporta y se envió, false si no.
   */
  notify: (payload) => ipcRenderer.invoke('notify-native', payload),
  /**
   * Enfoca y trae al frente la ventana de la app (sale de minimizado, sube
   * al frente del SO, hace flash en Windows). Lo usa el flow de login
   * device-code: cuando el usuario completa la activación en el browser,
   * la desktop "se vuelve a poner adelante" sin que el usuario tenga que
   * cambiar de ventana — estilo Notion / 1Password.
   */
  focusWindow: () => ipcRenderer.invoke('focus-window'),
  /**
   * Suscribe un callback al evento "deep link recibido". El SO lanza/enfoca
   * la app con una URL `todoconta://activated?code=XXX` cuando el usuario
   * completa el activate en el browser; el main process la parsea y envía
   * por IPC. El renderer (LoginPage) usa esto para poll inmediato con el
   * code recibido.
   *
   * Devuelve una función `dispose()` para quitar el listener (cleanup).
   */
  onProtocolActivated: (cb) => {
    const handler = (_event, payload) => cb(payload);
    ipcRenderer.on('protocol-activated', handler);
    return () => ipcRenderer.removeListener('protocol-activated', handler);
  },
});

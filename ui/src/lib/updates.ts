/**
 * Bridge a las actualizaciones de la app (electron-updater en el main de
 * Electron, expuesto por el preload como `window.satDesktop.updates`).
 * En navegador (dev) no existe → los consumidores ocultan su UI.
 */

export interface UpdatesState {
  estado: 'idle' | 'buscando' | 'al-dia' | 'descargando' | 'lista' | 'error' | string;
  /** Versión nueva detectada (si hay). */
  version?: string | null;
  /** Porcentaje de descarga 0-100 (estado 'descargando'). */
  progreso?: number | null;
  /** Detalle del error (estado 'error'). */
  mensaje?: string | null;
  /** false = updater inoperante (dev sin empaquetar): ocultar el botón. */
  disponible?: boolean;
}

export interface UpdatesBridge {
  /** Dispara una búsqueda manual; devuelve el estado al momento. */
  check: () => Promise<UpdatesState>;
  /** Estado actual sin disparar nada. */
  getState: () => Promise<UpdatesState>;
  /** Reinicia e instala el update ya descargado (estado 'lista'). */
  install: () => Promise<boolean>;
  /** Suscribe a cambios de estado; devuelve dispose() para limpiar. */
  onChanged: (cb: (state: UpdatesState) => void) => () => void;
}

export function getUpdatesBridge(): UpdatesBridge | null {
  if (typeof window === 'undefined') return null;
  const w = window as unknown as { satDesktop?: { updates?: UpdatesBridge } };
  return w.satDesktop?.updates ?? null;
}

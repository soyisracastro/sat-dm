/**
 * Transporte nativo. En Electron usa IPC al main process; en browser dev
 * cae al HTML5 Notification API. Si nada está disponible, no-op (sonner
 * cubre el caso enfocado).
 */

interface SatDesktopBridge {
  notify?: (payload: { title: string; body: string; urgent?: boolean }) => Promise<boolean>;
}
interface SatAgentBridge {
  isDesktop?: boolean;
}

function getBridge(): { satDesktop?: SatDesktopBridge; satAgent?: SatAgentBridge } {
  if (typeof window === 'undefined') return {};
  return window as unknown as {
    satDesktop?: SatDesktopBridge;
    satAgent?: SatAgentBridge;
  };
}

export function isElectron(): boolean {
  return !!getBridge().satAgent?.isDesktop;
}

export interface NativePayload {
  title: string;
  body: string;
  /** True para que el SO suene; false (default) = silent. */
  urgent?: boolean;
}

/**
 * Despacha una notificación nativa. En Electron va por IPC; en browser
 * usa HTML5 Notification si el usuario ya dio permiso. NUNCA pide
 * permiso aquí (eso se hace en respuesta a un gesto del usuario en
 * Ajustes — ver `requestBrowserPermission`).
 */
export async function dispatchNative(payload: NativePayload): Promise<boolean> {
  const bridge = getBridge();
  if (bridge.satAgent?.isDesktop && bridge.satDesktop?.notify) {
    try {
      return await bridge.satDesktop.notify(payload);
    } catch {
      return false;
    }
  }

  // Browser dev fallback
  if (typeof window !== 'undefined' && 'Notification' in window) {
    if (Notification.permission !== 'granted') return false;
    try {
      const n = new Notification(payload.title, {
        body: payload.body,
        silent: !payload.urgent,
      });
      n.onclick = () => {
        window.focus();
        n.close();
      };
      return true;
    } catch {
      return false;
    }
  }

  return false;
}

/**
 * Pide permiso de notificaciones al browser. Solo tiene sentido fuera
 * de Electron (en Electron el permission ya está granted por default).
 * Devuelve el estado final.
 */
export async function requestBrowserPermission(): Promise<NotificationPermission> {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'denied';
  if (Notification.permission === 'granted') return 'granted';
  if (Notification.permission === 'denied') return 'denied';
  try {
    return await Notification.requestPermission();
  } catch {
    return 'denied';
  }
}

/**
 * Estado actual del permiso. En Electron siempre 'granted'.
 */
export function browserPermission(): NotificationPermission {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'denied';
  return Notification.permission;
}

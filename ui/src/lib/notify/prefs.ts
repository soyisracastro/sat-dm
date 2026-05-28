/**
 * Preferencias de notificaciones (sonner + nativas SO). Persistidas en
 * localStorage. En PR1 solo controlan sonner; PR3 las reutiliza para
 * decidir si dispara la nativa.
 */

const STORAGE_KEY = 'sat-dm:notif-prefs:v1';

export interface NotifPrefs {
  /** Avisar cuando termine (o falle) una descarga WS o CIEC. */
  descargas: boolean;
  /** Recordatorio diario cuando la e.firma activa esté por vencer (≤30 días). */
  efirma: boolean;
}

const DEFAULTS: NotifPrefs = {
  descargas: true,
  efirma: true,
};

export function getNotifPrefs(): NotifPrefs {
  if (typeof window === 'undefined') return DEFAULTS;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULTS;
    const parsed = JSON.parse(raw) as Partial<NotifPrefs>;
    return { ...DEFAULTS, ...parsed };
  } catch {
    return DEFAULTS;
  }
}

export function setNotifPrefs(patch: Partial<NotifPrefs>): NotifPrefs {
  const next = { ...getNotifPrefs(), ...patch };
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* localStorage no disponible (Safari privado, etc.) */
  }
  return next;
}

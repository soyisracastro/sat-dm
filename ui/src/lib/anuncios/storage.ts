/**
 * Estado de lectura de anuncios. Persistido en localStorage como un mapa
 * `{ [id]: true }`. El `id` viene del JSON remoto y es estable.
 */

const STORAGE_KEY = 'sat-dm:anuncios-read:v1';

type ReadMap = Record<string, boolean>;

function leer(): ReadMap {
  if (typeof window === 'undefined') return {};
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    return parsed && typeof parsed === 'object' ? (parsed as ReadMap) : {};
  } catch {
    return {};
  }
}

function escribir(mapa: ReadMap): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(mapa));
  } catch {
    /* localStorage no disponible */
  }
}

export function getReadMap(): ReadMap {
  return leer();
}

export function isRead(id: string): boolean {
  return leer()[id] === true;
}

export function markRead(id: string): ReadMap {
  const next = { ...leer(), [id]: true };
  escribir(next);
  return next;
}

export function markAllRead(ids: string[]): ReadMap {
  const next = { ...leer() };
  for (const id of ids) next[id] = true;
  escribir(next);
  return next;
}

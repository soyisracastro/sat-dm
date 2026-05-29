/**
 * Fetch del JSON remoto de anuncios con cache en memoria (1 hora).
 * Tolerante a fallos: si la red o el JSON están rotos, devuelve [].
 */

import { type Anuncio, filtrarVigentes, parseAnunciosPayload } from './types';

const CACHE_TTL_MS = 60 * 60 * 1000; // 1 hora
const DEFAULT_URL = 'https://todoconta.com/anuncios.json';

interface CacheEntry {
  at: number;
  anuncios: Anuncio[];
}

let memo: CacheEntry | null = null;

function getUrl(): string {
  return process.env.NEXT_PUBLIC_ANUNCIOS_URL || DEFAULT_URL;
}

export async function fetchAnuncios(opts: { force?: boolean } = {}): Promise<Anuncio[]> {
  const now = Date.now();
  if (!opts.force && memo && now - memo.at < CACHE_TTL_MS) {
    return memo.anuncios;
  }

  try {
    const res = await fetch(getUrl(), { cache: 'no-store' });
    if (!res.ok) {
      memo = { at: now, anuncios: [] };
      return [];
    }
    const raw = await res.json();
    const payload = parseAnunciosPayload(raw);
    const anuncios = payload ? filtrarVigentes(payload.anuncios, now) : [];
    memo = { at: now, anuncios };
    return anuncios;
  } catch {
    memo = { at: now, anuncios: [] };
    return [];
  }
}

/** Útil para tests / forzar refresh al cambiar de empresa/usuario. */
export function clearAnunciosCache(): void {
  memo = null;
}

/**
 * Schema del JSON publicado en `todoconta.com/anuncios.json`. Versionado
 * en el root para evolucionar sin romper clientes viejos. El `id` es la
 * clave de read-state en localStorage — nunca cambiarlo una vez publicado.
 */

export type AnuncioCategoria =
  | 'curso'
  | 'taller'
  | 'blog'
  | 'oferta'
  | 'producto'
  | 'aviso';

export interface Anuncio {
  id: string;
  title: string;
  body: string;
  category: AnuncioCategoria;
  publishedAt: string;   // ISO 8601
  expiresAt?: string;    // ISO 8601 — el cliente filtra si ya pasó
  link?: string;         // URL externa (se abre con shell.openExternal en Electron)
  priority?: number;     // 0 normal · 1 destacado · -1 silencioso (futuro)
  minAppVersion?: string;
  audience?: string[];   // futuro: ["plan:pro"], etc.
}

export interface AnunciosPayload {
  version: number;
  anuncios: Anuncio[];
}

const CATEGORIAS_VALIDAS: AnuncioCategoria[] = [
  'curso', 'taller', 'blog', 'oferta', 'producto', 'aviso',
];

/**
 * Validación defensiva del JSON remoto. Devuelve la lista de anuncios
 * bien formados, descartando entradas inválidas en silencio. Si el
 * payload completo no parsea, devuelve null para que el caller distinga
 * "vacío legítimo" de "JSON roto".
 */
export function parseAnunciosPayload(raw: unknown): AnunciosPayload | null {
  if (!raw || typeof raw !== 'object') return null;
  const obj = raw as Record<string, unknown>;
  if (typeof obj.version !== 'number') return null;
  if (!Array.isArray(obj.anuncios)) return null;

  const anuncios: Anuncio[] = [];
  for (const item of obj.anuncios) {
    if (!item || typeof item !== 'object') continue;
    const a = item as Record<string, unknown>;
    if (typeof a.id !== 'string' || !a.id) continue;
    if (typeof a.title !== 'string' || !a.title) continue;
    if (typeof a.body !== 'string') continue;
    if (typeof a.category !== 'string' || !CATEGORIAS_VALIDAS.includes(a.category as AnuncioCategoria)) continue;
    if (typeof a.publishedAt !== 'string') continue;

    anuncios.push({
      id: a.id,
      title: a.title,
      body: a.body,
      category: a.category as AnuncioCategoria,
      publishedAt: a.publishedAt,
      expiresAt: typeof a.expiresAt === 'string' ? a.expiresAt : undefined,
      link: typeof a.link === 'string' ? a.link : undefined,
      priority: typeof a.priority === 'number' ? a.priority : undefined,
      minAppVersion: typeof a.minAppVersion === 'string' ? a.minAppVersion : undefined,
      audience: Array.isArray(a.audience) ? a.audience.filter((x): x is string => typeof x === 'string') : undefined,
    });
  }

  return { version: obj.version, anuncios };
}

/**
 * Filtra anuncios vencidos (expiresAt < now). Mantiene los sin expiración.
 */
export function filtrarVigentes(anuncios: Anuncio[], now = Date.now()): Anuncio[] {
  return anuncios.filter((a) => {
    if (!a.expiresAt) return true;
    const t = Date.parse(a.expiresAt);
    if (Number.isNaN(t)) return true;
    return t > now;
  });
}

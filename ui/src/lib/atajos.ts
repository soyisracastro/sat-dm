// Atajos de teclado de la app: detección de plataforma, formato de hints
// (⌘K vs Ctrl+K) y la tabla de referencia que consumen la card de /ayuda y
// los CommandShortcut del palette. La captura real de teclas vive en
// hooks/use-atajos-globales.ts; el cableado de acciones en
// components/layout/global-shortcuts.tsx.

// Eventos window de los atajos (mismo patrón que 'empresas:refresh'):
// desacoplan GlobalShortcuts del Sidebar sin levantar un context.
export const EVENTO_PALETTE_OPEN = 'tc:palette-open';
export const EVENTO_SIDEBAR_TOGGLE = 'tc:sidebar-toggle';

export interface Plataforma {
  desktop: boolean;
  mac: boolean;
  win: boolean;
}

/**
 * Detecta si corremos dentro de Electron y en qué SO. El preload expone la
 * plataforma real (`window.satDesktop.platform`); user-agent solo como
 * fallback (preloads viejos / navegador dev). Llamar solo post-mount: en el
 * primer render (prerender del export estático) devuelve todo false.
 */
export function detectarPlataforma(): Plataforma {
  if (typeof window === 'undefined') return { desktop: false, mac: false, win: false };
  const w = window as unknown as {
    satAgent?: { isDesktop?: boolean };
    satDesktop?: { platform?: string };
  };
  const desktop = !!w.satAgent?.isDesktop;
  const platform = w.satDesktop?.platform;
  if (platform) {
    return { desktop, mac: platform === 'darwin', win: platform === 'win32' };
  }
  const ua = navigator.platform || navigator.userAgent || '';
  return { desktop, mac: /Mac/i.test(ua), win: /Win/i.test(ua) };
}

export function esMac(): boolean {
  return detectarPlataforma().mac;
}

/** Un atajo de la tabla de referencia (solo presentación, no captura). */
export interface Atajo {
  id: string;
  /** Tecla legible: 'K', 'E', '1…7', ','. */
  tecla: string;
  shift?: boolean;
  descripcion: string;
  grupo: 'Navegación' | 'Vista';
}

/**
 * Formatea un atajo para mostrarlo: mac '⇧⌘L', win/linux 'Ctrl+Shift+L'.
 * Como `esMac()` depende de window, llamar post-mount (patrón de /ajustes).
 */
export function formatearAtajo(atajo: Pick<Atajo, 'tecla' | 'shift'>, mac: boolean): string {
  if (mac) return `${atajo.shift ? '⇧' : ''}⌘${atajo.tecla}`;
  return `Ctrl+${atajo.shift ? 'Shift+' : ''}${atajo.tecla}`;
}

// Tabla de referencia (card "Atajos de teclado" en /ayuda). Los ⌘1..⌘7 se
// asignan por el ORDEN de NAV_ITEMS en lib/navegacion.ts — ver nota ahí.
export const ATAJOS: readonly Atajo[] = [
  { id: 'palette', tecla: 'K', descripcion: 'Buscar página o acción', grupo: 'Navegación' },
  { id: 'empresas', tecla: 'E', descripcion: 'Cambiar de empresa activa', grupo: 'Navegación' },
  { id: 'paginas', tecla: '1…7', descripcion: 'Ir a la página N del menú (en su orden)', grupo: 'Navegación' },
  { id: 'ajustes', tecla: ',', descripcion: 'Abrir Ajustes', grupo: 'Navegación' },
  { id: 'tema', tecla: 'L', shift: true, descripcion: 'Alternar tema claro/oscuro', grupo: 'Vista' },
  { id: 'sidebar', tecla: 'B', descripcion: 'Colapsar o expandir el menú lateral', grupo: 'Vista' },
] as const;

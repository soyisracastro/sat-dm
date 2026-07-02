// Fuente única de las páginas de la app: el sidebar, el command palette (⌘K)
// y los atajos numéricos (⌘1..⌘N) se derivan de estos arrays.
//
// OJO con el ORDEN de NAV_ITEMS: el atajo ⌘1..⌘N se asigna por posición
// (⌘1 = primer item, ⌘2 = segundo, ...). Si se reordenan, agregan o mueven
// páginas del sidebar, el número de cada atajo cambia con ellas — la card de
// atajos en /ayuda se regenera sola, pero avisa el cambio en el CHANGELOG.

export interface PaginaNav {
  href: string;
  label: string;
  icon: string;
}

// Nav plano del sidebar (Ajustes vive en el menú de cuenta; Ayuda en el footer).
export const NAV_ITEMS: readonly PaginaNav[] = [
  { href: '/', label: 'Inicio', icon: 'ph:squares-four-light' },
  { href: '/empresas', label: 'Empresas', icon: 'ph:buildings-light' },
  { href: '/descarga', label: 'Descargar CFDIs', icon: 'ph:download-simple-light' },
  { href: '/comprobantes', label: 'Comprobantes', icon: 'ph:files-light' },
  { href: '/listas-negras', label: 'Listas negras', icon: 'ph:shield-check-light' },
  { href: '/organizador', label: 'Organizador', icon: 'ph:folders-light' },
  { href: '/historial', label: 'Historial', icon: 'ph:clock-counter-clockwise-light' },
] as const;

// Páginas fuera del nav plano (footer del sidebar / menú de cuenta).
export const NAV_SECUNDARIO: readonly PaginaNav[] = [
  { href: '/ayuda', label: 'Ayuda', icon: 'ph:question-light' },
  { href: '/ajustes', label: 'Ajustes', icon: 'ph:gear-light' },
] as const;

// Páginas adicionales que el palette ofrece pero no viven en el sidebar.
export const PAGINAS_EXTRA: readonly PaginaNav[] = [
  { href: '/descarga/rapida', label: 'Descarga rápida', icon: 'ph:lightning-light' },
] as const;

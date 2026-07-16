import type { Empresa } from './types';

export type MetodoPortal = 'fiel' | 'ciec';

/**
 * Método de portal preferido para descargas (CFDI, CSF, 32-D).
 *
 * Regla de negocio: e.firma gana siempre que esté cargada (cero captcha,
 * 100% automatizable); si no, CIEC como fallback; si no hay nada, `null`.
 */
export function metodoPortalPreferido(
  empresa: Empresa | null | undefined,
): MetodoPortal | null {
  if (!empresa) return null;
  if (empresa.metodos.includes('fiel')) return 'fiel';
  if (empresa.metodos.includes('ciec')) return 'ciec';
  return null;
}

/** Etiqueta visible al usuario en chips/avisos. */
export function etiquetaMetodo(m: MetodoPortal): string {
  return m === 'fiel' ? 'e.firma' : 'Contraseña';
}

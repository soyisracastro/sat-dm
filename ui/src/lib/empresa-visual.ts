// ---------------------------------------------------------------------------
// Identidad visual de una empresa en la UI (badge PF/PM del sidebar, detalle).
// ---------------------------------------------------------------------------

export type TipoPersona = 'PF' | 'PM';

/** Persona Física (RFC de 13) vs Persona Moral (RFC de 12). */
export function tipoPersona(rfc: string | null | undefined): TipoPersona {
  return (rfc || '').trim().length >= 13 ? 'PF' : 'PM';
}

// Paleta de identidad por empresa (badge del selector). Es una paleta de DATOS
// (distinguir empresas entre sí), no tokens de superficie del design system —
// por eso son hex fijos y no variables CSS. Los tres primeros coinciden con
// primary/success/warning del DS.
const PALETA_EMPRESA = [
  '#0B5FFF', // primary
  '#059669', // success
  '#B45309', // warning
  '#7C3AED', // violeta
  '#DB2777', // rosa
  '#0891B2', // cian oscuro
] as const;

/** Color determinista por RFC (estable entre sesiones y vistas). */
export function colorEmpresa(rfc: string | null | undefined): string {
  const s = (rfc || '').trim().toUpperCase();
  let hash = 0;
  for (let i = 0; i < s.length; i++) hash = (hash * 31 + s.charCodeAt(i)) >>> 0;
  return PALETA_EMPRESA[hash % PALETA_EMPRESA.length];
}

/** Iniciales para avatares (p. ej. del email de la cuenta o del nombre). */
export function iniciales(texto: string | null | undefined): string {
  const limpio = (texto || '').split('@')[0].trim();
  if (!limpio) return '?';
  const partes = limpio.split(/[\s._-]+/).filter(Boolean);
  if (partes.length >= 2) {
    return (partes[0][0] + partes[1][0]).toUpperCase();
  }
  return limpio.slice(0, 2).toUpperCase();
}

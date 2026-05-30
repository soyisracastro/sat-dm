/** RFC de 12 chars → Persona Moral, 13 → Persona Física. */
export function tipoPersonaDeRfc(rfc: string): 'PF' | 'PM' {
  return rfc.trim().length === 12 ? 'PM' : 'PF';
}

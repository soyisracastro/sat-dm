// ---------------------------------------------------------------------------
// Conexión de la versión web con SU agente (contenedor por usuario en el VPS).
//
// En desktop el preload inyecta baseUrl+token; en la web los entrega el
// provisioner al hacer login (o la página /conectar en el piloto) y viven en
// localStorage para sobrevivir recargas. El token autentica contra el agente
// (header X-Agent-Token / ?token=), NO es la sesión de Supabase.
// ---------------------------------------------------------------------------

export interface ConexionAgente {
  /** Base URL del agente del usuario, p. ej. https://agente.todoconta.com/u/abc123 */
  baseUrl: string;
  /** Token de auth del agente (derivado por usuario). */
  token: string;
}

const STORAGE_KEY = 'todoconta.agente.conexion';

export function getConexion(): ConexionAgente | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as Partial<ConexionAgente>;
    if (typeof data.baseUrl !== 'string' || typeof data.token !== 'string') {
      return null;
    }
    return { baseUrl: data.baseUrl.replace(/\/+$/, ''), token: data.token };
  } catch {
    return null;
  }
}

export function setConexion(conexion: ConexionAgente): void {
  try {
    window.localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify({
        baseUrl: conexion.baseUrl.replace(/\/+$/, ''),
        token: conexion.token,
      }),
    );
  } catch {
    // localStorage bloqueado (modo privado estricto): la conexión vivirá solo
    // en memoria durante esta pestaña.
  }
}

export function clearConexion(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // sin localStorage no hay nada que borrar
  }
}

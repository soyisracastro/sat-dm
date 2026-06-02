'use client';

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import { useServer } from '@/providers/server-provider';
import type { LicenseStatus } from '@/lib/api-client';

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface AuthContextValue {
  /** Estado actual de licencia del usuario. null mientras carga inicial. */
  license: LicenseStatus | null;
  /** True si nunca se ha cargado el estado todavía. */
  loading: boolean;
  /** Re-fetch del backend (force_refresh). Lo llaman botones de "refrescar". */
  refresh: () => Promise<void>;
  /** Logout — limpia keyring y vuelve a la pantalla de login. */
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

/**
 * AuthProvider — fuente de verdad del estado de autenticación + licencia.
 *
 * - Carga el estado al montar (cache local del agente; sin red).
 * - Re-fetch automático cada 6h en background (no bloquea).
 * - Expone `refresh()` para invalidar manualmente y `logout()`.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const { apiClient, isConnected } = useServer();
  const [license, setLicense] = useState<LicenseStatus | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchLicense = useCallback(
    async (force = false) => {
      try {
        const data = await apiClient.authLicense(force);
        setLicense(data);
      } catch (e) {
        console.warn('[auth] authLicense falló:', e);
        // Mantenemos el estado previo si lo había; si no, marcamos no-auth.
        setLicense((prev) => prev ?? { authenticated: false });
      } finally {
        setLoading(false);
      }
    },
    [apiClient],
  );

  // Carga inicial: solo cuando el agente está conectado.
  useEffect(() => {
    if (!isConnected) return;
    fetchLicense(false);
  }, [isConnected, fetchLicense]);

  // Re-fetch cada 6h en background (el agente decidirá si pega al backend o
  // devuelve cache fresh).
  useEffect(() => {
    if (!isConnected) return;
    const interval = setInterval(() => {
      fetchLicense(false);
    }, 6 * 60 * 60 * 1000);
    return () => clearInterval(interval);
  }, [isConnected, fetchLicense]);

  const refresh = useCallback(() => fetchLicense(true), [fetchLicense]);

  const logout = useCallback(async () => {
    try {
      await apiClient.authLogout();
    } catch (e) {
      console.warn('[auth] logout falló:', e);
    }
    setLicense({ authenticated: false });
    setLoading(false);
  }, [apiClient]);

  const value = useMemo<AuthContextValue>(
    () => ({ license, loading, refresh, logout }),
    [license, loading, refresh, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

// ---------------------------------------------------------------------------
// Hooks
// ---------------------------------------------------------------------------

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth debe usarse dentro de <AuthProvider>');
  }
  return ctx;
}

/**
 * `useRequireAuth` — devuelve la license cuando ya hay sesión; antes de eso,
 * permite a las páginas mostrar un loader.
 */
export function useRequireAuth(): {
  ready: boolean;
  authenticated: boolean;
  license: LicenseStatus | null;
} {
  const { license, loading } = useAuth();
  if (loading || license === null) {
    return { ready: false, authenticated: false, license: null };
  }
  return {
    ready: true,
    authenticated: license.authenticated === true,
    license,
  };
}

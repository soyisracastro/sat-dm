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
import { identificarUsuario } from '@/lib/telemetria';
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
 * - Carga el estado al montar con cache (render instantáneo, sin red) y luego
 *   reconcilia en background con un force-refresh (corrige banners/badges si el
 *   estado cambió en el servidor: ventana de fundadores cerrada, promo activa,
 *   suscripción, etc.) sin bloquear ni mostrar spinner.
 * - Re-fetch automático cada 6h con force (ignora el cache de 24h del agente)
 *   para que sesiones largas no queden desactualizadas.
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
        // Identifica al usuario en Sentry (o lo desliga si no hay sesión) para
        // que los reportes traigan quién es. Idempotente entre re-fetches.
        identificarUsuario(
          data.authenticated ? { id: data.user_id, email: data.email } : null,
        );
        // Disparar autocarga de FIEL en background si el usuario está
        // autenticado. Antes lo hacía el lifespan del agente, pero bloqueaba
        // el startup en Windows (keyring sin prompt UI). Ahora es lazy y no
        // bloquea — si falla, la app sigue funcional y el usuario carga la
        // FIEL a mano desde Empresas.
        if (data.authenticated) {
          apiClient.autocargarFiel().catch((e) => {
            console.warn('[auth] autocargarFiel falló (no bloqueante):', e);
          });
        }
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

  // Carga inicial: cache primero (render instantáneo) y luego un force-refresh
  // en background para reconciliar con el servidor. El force no vuelve a poner
  // `loading=true` (solo se apaga en el finally), así que el shell no parpadea;
  // si el estado cambió (p. ej. ventana de fundadores cerrada), los banners se
  // corrigen solos en cuanto llega la respuesta. Offline-safe: el agente cae a
  // su cache si no hay red.
  useEffect(() => {
    if (!isConnected) return;
    void fetchLicense(false).then(() => fetchLicense(true));
  }, [isConnected, fetchLicense]);

  // Re-fetch cada 6h con force: ignora el cache de 24h del agente para que una
  // sesión abierta por días refleje cambios del servidor a tiempo.
  useEffect(() => {
    if (!isConnected) return;
    const interval = setInterval(() => {
      fetchLicense(true);
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
    identificarUsuario(null); // desliga al usuario de los próximos reportes
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

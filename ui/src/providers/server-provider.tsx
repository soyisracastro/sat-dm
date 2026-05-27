'use client';

import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useRef,
  type ReactNode,
} from 'react';

import { SatApiClient } from '@/lib/api-client';
import { getAgentBaseUrl } from '@/lib/constants';
import { useServerHealth } from '@/hooks/use-server-health';

// ---------------------------------------------------------------------------
// Context shape
// ---------------------------------------------------------------------------

interface FielStatus {
  loaded: boolean;
  rfc: string | null;
  numeroSerie: string | null;
}

interface ServerContextValue {
  /** Typed API client instance (stable reference). */
  apiClient: SatApiClient;

  /** Whether the Python server at localhost:8787 is reachable. */
  isConnected: boolean;

  /** Current e-firma status from the server. */
  fielStatus: FielStatus;

  /** Upload the FIEL (.cer + .key + password) to the local server. */
  cargarFiel: (
    cerFile: File,
    keyFile: File,
    password: string,
  ) => Promise<{ rfc: string; numeroSerie: string }>;

  /** Unload the FIEL from server memory. */
  descargarFiel: () => Promise<void>;

  /** Force an immediate health check (e.g. after cargar/descargar fiel). */
  refreshHealth: () => void;
}

const ServerContext = createContext<ServerContextValue | null>(null);

// ---------------------------------------------------------------------------
// Provider
// ---------------------------------------------------------------------------

interface ServerProviderProps {
  children: ReactNode;
  /** Override the base URL for the Python server. */
  baseUrl?: string;
}

export function ServerProvider({ children, baseUrl }: ServerProviderProps) {
  // En Electron el agente corre en un puerto efímero que el preload inyecta en
  // window.satAgent.baseUrl; en el navegador cae a API_BASE_URL (localhost:8787).
  const resolvedBaseUrl = baseUrl ?? getAgentBaseUrl();
  const apiClient = useMemo(() => new SatApiClient(resolvedBaseUrl), [resolvedBaseUrl]);

  const {
    isConnected,
    rfcCargado,
    efirmaLista,
    refresh: refreshHealth,
  } = useServerHealth(apiClient);

  // Track numero_serie separately — the /health endpoint does not return it,
  // so we store it when cargarFiel succeeds and clear it on descargarFiel.
  const numeroSerieRef = useRef<string | null>(null);

  const fielStatus: FielStatus = useMemo(
    () => ({
      loaded: efirmaLista,
      rfc: rfcCargado,
      numeroSerie: efirmaLista ? numeroSerieRef.current : null,
    }),
    [efirmaLista, rfcCargado],
  );

  const cargarFiel = useCallback(
    async (cerFile: File, keyFile: File, password: string) => {
      const res = await apiClient.cargarFiel(cerFile, keyFile, password);
      numeroSerieRef.current = res.numero_serie;
      // Trigger an immediate health refresh so isConnected/fielStatus update
      refreshHealth();
      return { rfc: res.rfc, numeroSerie: res.numero_serie };
    },
    [apiClient, refreshHealth],
  );

  const descargarFiel = useCallback(async () => {
    await apiClient.descargarFiel();
    numeroSerieRef.current = null;
    refreshHealth();
  }, [apiClient, refreshHealth]);

  const value: ServerContextValue = useMemo(
    () => ({
      apiClient,
      isConnected,
      fielStatus,
      cargarFiel,
      descargarFiel,
      refreshHealth,
    }),
    [apiClient, isConnected, fielStatus, cargarFiel, descargarFiel, refreshHealth],
  );

  return (
    <ServerContext.Provider value={value}>{children}</ServerContext.Provider>
  );
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Access the server connection state and API client.
 *
 * Must be used inside `<ServerProvider>`.
 */
export function useServer(): ServerContextValue {
  const ctx = useContext(ServerContext);
  if (!ctx) {
    throw new Error('useServer must be used within a <ServerProvider>');
  }
  return ctx;
}

'use client';

import { useCallback, useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { Empresa } from '@/lib/types';

interface UseEmpresasState {
  empresas: Empresa[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  addCiec: (rfc: string, nombre: string, ciec: string) => Promise<void>;
  addFiel: (
    cer: File,
    key: File,
    password: string,
    nombre: string,
  ) => Promise<void>;
  remove: (rfc: string) => Promise<void>;
  activar: (rfc: string) => Promise<void>;
}

/**
 * Catálogo de empresas del agente (GET /empresas) + altas (FIEL/CIEC), baja y
 * activación. La contraseña la guarda el agente en el keychain del SO; aquí solo
 * manejamos metadata. `activar` recarga el health por si cargó la e.firma en sesión.
 */
export function useEmpresas(): UseEmpresasState {
  const { apiClient, refreshHealth } = useServer();
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => setTick((t) => t + 1), []);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    apiClient
      .listEmpresas()
      .then((r) => {
        if (mounted) {
          setEmpresas(r.empresas);
          setError(null);
        }
      })
      .catch((e: unknown) => {
        if (mounted) setError(e instanceof Error ? e.message : String(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [apiClient, tick]);

  const addCiec = useCallback(
    async (rfc: string, nombre: string, ciec: string) => {
      await apiClient.addEmpresaCiec({ rfc, nombre, ciec });
      refresh();
    },
    [apiClient, refresh],
  );

  const addFiel = useCallback(
    async (cer: File, key: File, password: string, nombre: string) => {
      await apiClient.addEmpresaFiel(cer, key, password, nombre);
      refresh();
    },
    [apiClient, refresh],
  );

  const remove = useCallback(
    async (rfc: string) => {
      await apiClient.removeEmpresa(rfc);
      refresh();
    },
    [apiClient, refresh],
  );

  const activar = useCallback(
    async (rfc: string) => {
      await apiClient.activarEmpresa(rfc);
      refreshHealth(); // por si cargó la e.firma en sesión
    },
    [apiClient, refreshHealth],
  );

  return { empresas, loading, error, refresh, addCiec, addFiel, remove, activar };
}

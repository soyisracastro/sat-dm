'use client';

import { useCallback, useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { Empresa, MetodoEmpresa } from '@/lib/types';

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
    rfcEsperado?: string,
  ) => Promise<void>;
  remove: (rfc: string) => Promise<void>;
  /** Marca la empresa como activa (predeterminada); si tiene FIEL, carga la e.firma. */
  seleccionar: (rfc: string, metodos: MetodoEmpresa[]) => Promise<void>;
  /** Carga la e.firma de la empresa en la sesión (sin cambiar la predeterminada). */
  activarSesion: (rfc: string) => Promise<void>;
  /** Soft-delete: oculta la empresa de la lista principal (reversible). */
  archive: (rfc: string) => Promise<void>;
  /** Reactiva una empresa archivada. */
  unarchive: (rfc: string) => Promise<void>;
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
    async (cer: File, key: File, password: string, nombre: string, rfcEsperado?: string) => {
      await apiClient.addEmpresaFiel(cer, key, password, nombre, rfcEsperado);
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

  const seleccionar = useCallback(
    async (rfc: string, metodos: MetodoEmpresa[]) => {
      await apiClient.setDefaultEmpresa(rfc); // marca activa (persistente)
      if (metodos.includes('fiel')) {
        await apiClient.activarEmpresa(rfc); // carga la e.firma en sesión
      } else {
        // Empresa solo-CIEC: descarga la e.firma anterior para que la sesión
        // (cabecera/Inicio) refleje la empresa activa y no una desincronizada.
        await apiClient.descargarFiel();
      }
      refresh();
      refreshHealth();
    },
    [apiClient, refresh, refreshHealth],
  );

  const activarSesion = useCallback(
    async (rfc: string) => {
      await apiClient.activarEmpresa(rfc); // carga la e.firma en sesión
      refreshHealth();
    },
    [apiClient, refreshHealth],
  );

  const archive = useCallback(
    async (rfc: string) => {
      await apiClient.archiveEmpresa(rfc);
      refresh();
      // Archivar puede promover otra empresa como default → recargar health.
      refreshHealth();
    },
    [apiClient, refresh, refreshHealth],
  );

  const unarchive = useCallback(
    async (rfc: string) => {
      await apiClient.unarchiveEmpresa(rfc);
      refresh();
    },
    [apiClient, refresh],
  );

  return {
    empresas, loading, error, refresh,
    addCiec, addFiel, remove, seleccionar, activarSesion,
    archive, unarchive,
  };
}

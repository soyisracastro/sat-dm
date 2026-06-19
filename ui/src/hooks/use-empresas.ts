'use client';

import { useCallback, useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { Empresa, EmpresaUpdatePatch, MetodoEmpresa } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

// Evento global de sincronización: cada instancia de `useEmpresas()` tiene su
// propio estado, pero el catálogo es uno (sidebar + páginas). Cualquier mutación
// dispara este evento y TODAS las instancias montadas refetchean.
const EVENTO_REFRESH = 'empresas:refresh';

function notificarEmpresasCambiaron() {
  window.dispatchEvent(new Event(EVENTO_REFRESH));
}

interface UseEmpresasState {
  empresas: Empresa[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  /** `nombre` es opcional: vacío → el agente usa el RFC como nombre provisional. */
  addCiec: (rfc: string, ciec: string, nombre?: string) => Promise<void>;
  /** `nombre` es opcional: vacío → el agente usa la razón social del certificado. */
  addFiel: (
    cer: File,
    key: File,
    password: string,
    nombre?: string,
    rfcEsperado?: string,
  ) => Promise<void>;
  remove: (rfc: string) => Promise<void>;
  /** Quita SOLO la e.firma de la empresa (la CIEC se conserva). */
  removeEfirma: (rfc: string) => Promise<void>;
  /** Marca la empresa como activa (predeterminada); si tiene FIEL, carga la e.firma. */
  seleccionar: (rfc: string, metodos: MetodoEmpresa[]) => Promise<void>;
  /** Carga la e.firma de la empresa en la sesión (sin cambiar la predeterminada). */
  activarSesion: (rfc: string) => Promise<void>;
  /** Soft-delete: oculta la empresa de la lista principal (reversible). */
  archive: (rfc: string) => Promise<void>;
  /** Reactiva una empresa archivada. */
  unarchive: (rfc: string) => Promise<void>;
  /** Patch parcial: regimenes_fiscales / actividades_economicas. */
  update: (rfc: string, patch: EmpresaUpdatePatch) => Promise<void>;
}

/**
 * Catálogo de empresas del agente (GET /empresas) + altas (FIEL/CIEC), baja y
 * activación. La contraseña la guarda el agente en el keychain del SO; aquí solo
 * manejamos metadata. `activar` recarga el health por si cargó la e.firma en sesión.
 */
export function useEmpresas(): UseEmpresasState {
  const { apiClient, isConnected, refreshHealth } = useServer();
  const [empresas, setEmpresas] = useState<Empresa[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  // `refresh` notifica globalmente; el listener de abajo bumpea el tick local
  // (de esta y de cualquier otra instancia montada).
  const refresh = useCallback(() => notificarEmpresasCambiaron(), []);

  useEffect(() => {
    const onRefresh = () => setTick((t) => t + 1);
    window.addEventListener(EVENTO_REFRESH, onRefresh);
    return () => window.removeEventListener(EVENTO_REFRESH, onRefresh);
  }, []);

  useEffect(() => {
    // Espera a que el agente esté arriba antes del primer fetch. En equipos lentos
    // el binario del agente tarda en aceptar conexiones y el `/empresas` inicial
    // perdía la carrera de arranque: tronaba con "Failed to fetch" y la lista
    // quedaba vacía sin reintentar (hasta un refresh manual). Igual que el
    // auth-provider, nos enganchamos a `isConnected` y (re)cargamos al conectar.
    if (!isConnected) {
      setLoading(true);
      return;
    }
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
        if (mounted) setError(mensajeDeError(e));
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });
    return () => {
      mounted = false;
    };
  }, [apiClient, isConnected, tick]);

  const addCiec = useCallback(
    async (rfc: string, ciec: string, nombre = '') => {
      await apiClient.addEmpresaCiec({ rfc, nombre, ciec });
      refresh();
    },
    [apiClient, refresh],
  );

  const addFiel = useCallback(
    async (cer: File, key: File, password: string, nombre = '', rfcEsperado?: string) => {
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

  const removeEfirma = useCallback(
    async (rfc: string) => {
      await apiClient.removeEfirmaEmpresa(rfc);
      refresh();
      // Si esa e.firma estaba en sesión, el agente la descargó → reflejarlo.
      refreshHealth();
    },
    [apiClient, refresh, refreshHealth],
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

  const update = useCallback(
    async (rfc: string, patch: EmpresaUpdatePatch) => {
      await apiClient.updateEmpresa(rfc, patch);
      refresh();
    },
    [apiClient, refresh],
  );

  return {
    empresas, loading, error, refresh,
    addCiec, addFiel, remove, removeEfirma, seleccionar, activarSesion,
    archive, unarchive, update,
  };
}

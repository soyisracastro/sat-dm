'use client';

import { useCallback, useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { Tarea, TareaCrearRequest, TareaPatchRequest } from '@/lib/types';
import type { Sugerencia } from '@/lib/tareas';
import { mensajeDeError } from '@/lib/errores';

// Evento global de sincronización (mismo patrón que `empresas:refresh`): el
// estado vive en el agente y lo consumen varias vistas a la vez (Inicio +
// /tareas); cualquier mutación notifica y todas las instancias refetchean.
const EVENTO_REFRESH = 'tareas:refresh';

function notificarTareasCambiaron() {
  window.dispatchEvent(new Event(EVENTO_REFRESH));
}

interface UseTareasState {
  tareas: Tarea[];
  /** Ids de sugerencias descartadas (suprime re-derivarlas). */
  descartadas: string[];
  loading: boolean;
  error: string | null;
  refresh: () => void;
  crear: (req: TareaCrearRequest) => Promise<Tarea>;
  actualizar: (id: string, patch: TareaPatchRequest) => Promise<Tarea>;
  eliminar: (id: string) => Promise<void>;
  /** Palomear/despalomear: hecho ↔ pendiente. */
  toggleHecha: (tarea: Tarea) => Promise<void>;
  /** Convierte la sugerencia en tarea (el `sugerencia_id` la suprime). */
  aceptarSugerencia: (s: Sugerencia) => Promise<void>;
  /** Descarta la sugerencia para siempre (persistido en el agente). */
  descartarSugerencia: (id: string) => Promise<void>;
}

/**
 * Tareas personales del agente (GET /tareas) + CRUD. Tras cada mutación
 * aplica la respuesta al estado local (sin refetch) y notifica al resto de
 * instancias montadas para que refetcheen.
 */
export function useTareas(): UseTareasState {
  const { apiClient, isConnected } = useServer();
  const [tareas, setTareas] = useState<Tarea[]>([]);
  const [descartadas, setDescartadas] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [tick, setTick] = useState(0);

  const refresh = useCallback(() => notificarTareasCambiaron(), []);

  useEffect(() => {
    const onRefresh = () => setTick((t) => t + 1);
    window.addEventListener(EVENTO_REFRESH, onRefresh);
    return () => window.removeEventListener(EVENTO_REFRESH, onRefresh);
  }, []);

  useEffect(() => {
    if (!isConnected) {
      setLoading(true);
      return;
    }
    let mounted = true;
    apiClient
      .listTareas()
      .then((r) => {
        if (!mounted) return;
        setTareas(r.tareas);
        setDescartadas(r.sugerencias_descartadas);
        setError(null);
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

  const crear = useCallback(
    async (req: TareaCrearRequest) => {
      const tarea = await apiClient.crearTarea(req);
      setTareas((prev) => [tarea, ...prev]);
      notificarTareasCambiaron();
      return tarea;
    },
    [apiClient],
  );

  const actualizar = useCallback(
    async (id: string, patch: TareaPatchRequest) => {
      const tarea = await apiClient.actualizarTarea(id, patch);
      setTareas((prev) => prev.map((t) => (t.id === id ? tarea : t)));
      notificarTareasCambiaron();
      return tarea;
    },
    [apiClient],
  );

  const eliminar = useCallback(
    async (id: string) => {
      await apiClient.eliminarTarea(id);
      setTareas((prev) => prev.filter((t) => t.id !== id));
      notificarTareasCambiaron();
    },
    [apiClient],
  );

  const toggleHecha = useCallback(
    async (tarea: Tarea) => {
      await actualizar(tarea.id, {
        estado: tarea.estado === 'hecho' ? 'pendiente' : 'hecho',
      });
    },
    [actualizar],
  );

  const aceptarSugerencia = useCallback(
    async (s: Sugerencia) => {
      await crear({
        titulo: s.titulo,
        rfc: s.rfc,
        tipo: s.tipo,
        prioridad: s.prioridad,
        fecha: s.fecha,
        sugerencia_id: s.id,
      });
    },
    [crear],
  );

  const descartarSugerencia = useCallback(
    async (id: string) => {
      await apiClient.descartarSugerencia(id);
      setDescartadas((prev) => (prev.includes(id) ? prev : [...prev, id]));
      notificarTareasCambiaron();
    },
    [apiClient],
  );

  return {
    tareas,
    descartadas,
    loading,
    error,
    refresh,
    crear,
    actualizar,
    eliminar,
    toggleHecha,
    aceptarSugerencia,
    descartarSugerencia,
  };
}

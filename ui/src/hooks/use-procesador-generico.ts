'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { useEmpresas } from '@/hooks/use-empresas';
import { mensajeDeError } from '@/lib/errores';
import type { SatApiClient } from '@/lib/api-client';

/**
 * Configuración de un procesador (CFDI, Pagos, Nómina): valores iniciales de
 * los filtros + los 4 endpoints del apiClient que lo alimentan. Defínela como
 * constante de módulo para que su identidad sea estable entre renders.
 *
 * Todos los endpoints reciben el `rfc` de la empresa activa: el buffer del
 * procesador está aislado por empresa en el agente.
 */
export interface ProcesadorConfig<F extends object, D, S> {
  /** Valores default de los filtros; también el estado tras `reset()`. */
  filtrosIniciales: F;
  /** Prefijo de los `console.warn` (p. ej. `procesador`, `pagos`, `nomina`). */
  etiquetaLog: string;
  /** GET de los filtros persistidos en el backend (hidratación por empresa). */
  filtrosGet: (api: SatApiClient, rfc: string) => Promise<Partial<F>>;
  /** PUT de los filtros persistidos (se llama con debounce de 500 ms). */
  filtrosSet: (api: SatApiClient, rfc: string, filtros: F) => Promise<unknown>;
  /** Lista paginada del buffer con los filtros aplicados. */
  listar: (
    api: SatApiClient,
    rfc: string,
    filtros: F,
    page: number,
    pageSize: number,
  ) => Promise<D>;
  /** KPIs agregados de los mismos filtros. */
  stats: (api: SatApiClient, rfc: string, filtros: F) => Promise<S>;
}

/**
 * Estado compartido de los procesadores (CFDI / Pagos / Nómina), AISLADO POR
 * EMPRESA (mismo patrón "a prueba de pisadas" de use-calculadora):
 * - filtros: persistidos en el backend por empresa (PUT debounced).
 * - data: lista paginada del buffer de la empresa activa.
 * - stats: KPIs agregados de los mismos filtros.
 *
 * Al cambiar la empresa activa se re-hidrata todo (filtros + data + stats)
 * para la nueva empresa; regresar a la anterior (A→B→A) recupera lo suyo.
 * Las respuestas en vuelo de la empresa anterior se descartan con un guard
 * de época. Sin empresa activa (`sinEmpresa`) no se hace ningún fetch — las
 * páginas deben gatear la UI.
 */
export function useProcesadorGenerico<F extends object, D, S>(
  config: ProcesadorConfig<F, D, S>,
) {
  const {
    filtrosIniciales,
    etiquetaLog,
    filtrosGet,
    filtrosSet,
    listar,
    stats: cargarStats,
  } = config;
  const { apiClient } = useServer();
  const { empresas, loading: empresasLoading } = useEmpresas();
  const empresaActiva = empresas.find((e) => e.default);
  const rfcActivo = empresaActiva?.rfc ?? null;
  const sinEmpresa = !empresasLoading && rfcActivo === null;

  const [filtros, setFiltrosState] = useState<F>(filtrosIniciales);
  const [hidratado, setHidratado] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [data, setData] = useState<D | null>(null);
  const [stats, setStats] = useState<S | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Época de requests: se incrementa al cambiar de empresa para descartar
  // respuestas fuera de orden (cambio rápido A→B→A). `rfcHidratadoRef`
  // evita re-hidratar cuando el catálogo refetchea con el mismo RFC.
  const epochRef = useRef(0);
  const rfcHidratadoRef = useRef<string | null | undefined>(undefined);

  // (Re)hidratación de filtros al montar Y al cambiar de empresa activa.
  useEffect(() => {
    if (empresasLoading) return;
    if (rfcHidratadoRef.current === rfcActivo) return;
    rfcHidratadoRef.current = rfcActivo;
    epochRef.current += 1; // invalida requests en vuelo de la empresa anterior
    const epoch = epochRef.current;

    setHidratado(false);
    setData(null);
    setStats(null);
    setError(null);
    setPage(1);

    if (!rfcActivo) {
      // Sin empresa activa no hay buffer que consultar; la página gatea.
      setFiltrosState(filtrosIniciales);
      return;
    }

    filtrosGet(apiClient, rfcActivo)
      .then((f) => {
        if (epochRef.current !== epoch) return;
        setFiltrosState({ ...filtrosIniciales, ...f } as F);
        setHidratado(true);
      })
      .catch(() => {
        if (epochRef.current !== epoch) return;
        setFiltrosState(filtrosIniciales); // continuar con filtros vacíos
        setHidratado(true);
      });
  }, [apiClient, empresasLoading, rfcActivo, filtrosGet, filtrosIniciales]);

  // Persistencia debounced de filtros (al backend, bajo la empresa activa).
  // Al cambiar de empresa `hidratado` cae a false ANTES del siguiente render,
  // así que el timer pendiente se cancela y los filtros de A no se escriben
  // bajo B.
  const persistTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  useEffect(() => {
    if (!hidratado || !rfcActivo) return;
    if (persistTimer.current) clearTimeout(persistTimer.current);
    persistTimer.current = setTimeout(() => {
      filtrosSet(apiClient, rfcActivo, filtros).catch((e) => {
        console.warn(`[${etiquetaLog}] no se pudieron persistir filtros:`, e);
      });
    }, 500);
    return () => {
      if (persistTimer.current) clearTimeout(persistTimer.current);
    };
  }, [apiClient, filtros, hidratado, rfcActivo, filtrosSet, etiquetaLog]);

  const recargar = useCallback(async () => {
    if (!hidratado || !rfcActivo) return;
    const epoch = epochRef.current;
    setLoading(true);
    setError(null);
    try {
      const [list, statsResp] = await Promise.all([
        listar(apiClient, rfcActivo, filtros, page, pageSize),
        cargarStats(apiClient, rfcActivo, filtros),
      ]);
      if (epochRef.current !== epoch) return; // cambió la empresa en vuelo
      setData(list);
      setStats(statsResp);
    } catch (e) {
      if (epochRef.current !== epoch) return;
      setError(mensajeDeError(e));
    } finally {
      if (epochRef.current === epoch) setLoading(false);
    }
  }, [apiClient, rfcActivo, filtros, page, pageSize, hidratado, listar, cargarStats]);

  // Refetch ante cambios de filtros, página o page size.
  useEffect(() => {
    if (hidratado) recargar();
  }, [recargar, hidratado]);

  // Auto-reintento del primer load. Si el agente aún no responde —en Windows el
  // antivirus suele analizar el binario sin firma la primera vez que se ejecuta
  // su lógica, y la petición se cae o cuelga— reintenta solo con backoff en vez
  // de dejar la página en blanco esperando un clic manual. En cuanto hay stats
  // el contador se resetea y el efecto deja de actuar.
  const reintentosInicial = useRef(0);
  useEffect(() => {
    if (!hidratado) return;
    if (stats !== null) {
      reintentosInicial.current = 0;
      return;
    }
    // stats === null: sin error la petición sigue en curso (el spinner cubre
    // ese caso); solo reintentamos cuando ya falló, hasta un tope.
    if (!error) return;
    if (reintentosInicial.current >= 5) return;
    const intento = (reintentosInicial.current += 1);
    const delay = Math.min(500 * 2 ** (intento - 1), 5000);
    const t = setTimeout(() => recargar(), delay);
    return () => clearTimeout(t);
  }, [hidratado, stats, error, recargar]);

  const setFiltro = useCallback(
    <K extends keyof F>(key: K, value: F[K]) => {
      setFiltrosState((prev) => ({ ...prev, [key]: value } as F));
      setPage(1);
    },
    [],
  );

  const reset = useCallback(() => {
    setFiltrosState(filtrosIniciales);
    setPage(1);
  }, [filtrosIniciales]);

  const filtrosActivos = useMemo(() => {
    return (Object.keys(filtros) as (keyof F)[]).filter((k) => {
      const v: unknown = filtros[k];
      if (typeof v === 'boolean') return v;
      if (Array.isArray(v)) return v.length > 0;
      return v !== null && v !== '';
    }).length;
  }, [filtros]);

  return {
    filtros,
    setFiltro,
    reset,
    page,
    setPage,
    pageSize,
    setPageSize,
    data,
    stats,
    loading,
    error,
    recargar,
    filtrosActivos,
    hidratado,
    rfcActivo,
    sinEmpresa,
  };
}

'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';

import { useServer } from '@/providers/server-provider';
import { useEmpresas } from '@/hooks/use-empresas';
import { ApiError } from '@/lib/api-client';
import { mensajeDeError } from '@/lib/errores';
import type {
  CalculadoraInputs,
  CalculadoraNombre,
  CalculadoraRequestMap,
  CalculadoraResultadoMap,
  IndicadoresCalculadoras,
} from '@/lib/types';

/** RFC sintético del agente cuando no hay empresa activa. */
export const RFC_GENERAL = '__general__';

const DEBOUNCE_MS = 400;

interface UseCalculadoraOptions<N extends CalculadoraNombre> {
  nombre: N;
  /** Inputs iniciales cuando la empresa no tiene estado guardado. */
  defaults: CalculadoraInputs<N>;
  /** Solo se calcula (y por lo tanto se persiste) cuando los inputs son válidos. */
  esValido: (inputs: CalculadoraInputs<N>) => boolean;
  /** true → sin cálculo reactivo; el consumidor dispara `calcular()` (p. ej. PTU). */
  manual?: boolean;
}

interface UseCalculadoraState<N extends CalculadoraNombre> {
  /** RFC de la empresa activa, o `__general__` si no hay. */
  rfcActivo: string;
  inputs: CalculadoraInputs<N>;
  setInput: <K extends keyof CalculadoraInputs<N>>(
    campo: K,
    valor: CalculadoraInputs<N>[K],
  ) => void;
  setInputs: (
    next:
      | CalculadoraInputs<N>
      | ((prev: CalculadoraInputs<N>) => CalculadoraInputs<N>),
  ) => void;
  resultado: CalculadoraResultadoMap[N] | null;
  advertencias: string[];
  calculando: boolean;
  /** true mientras se restaura el estado guardado de la empresa activa. */
  restaurando: boolean;
  error: string | null;
  /** Fuerza un cálculo inmediato (sin esperar el debounce). */
  recalcular: () => void;
  /** Alias de `recalcular` para el modo manual (botón "Calcular"). */
  calcular: () => Promise<void>;
}

/**
 * Estado de una calculadora ligado a la empresa activa.
 *
 * - Al montar y al cambiar la RFC activa restaura inputs + resultado desde
 *   `GET /calculadoras/estado/{rfc}/{nombre}` (o aplica los defaults).
 * - Con inputs válidos recalcula con debounce de 400 ms; el POST lleva el RFC,
 *   así que el agente persiste el estado en el mismo round-trip.
 * - Guard contra respuestas fuera de orden: cada mutación de inputs y cada
 *   cambio de RFC suben una "época"; una respuesta solo se aplica si la época
 *   no cambió desde que se disparó el request.
 */
export function useCalculadora<N extends CalculadoraNombre>(
  options: UseCalculadoraOptions<N>,
): UseCalculadoraState<N> {
  const { nombre, defaults, esValido, manual = false } = options;
  const { apiClient, isConnected } = useServer();
  const { empresas, loading: empresasLoading } = useEmpresas();

  const empresaActiva = empresas.find((e) => e.default);
  const rfcActivo = empresaActiva?.rfc ?? RFC_GENERAL;

  const [inputs, setInputsState] = useState<CalculadoraInputs<N>>(defaults);
  const [resultado, setResultado] = useState<CalculadoraResultadoMap[N] | null>(null);
  const [advertencias, setAdvertencias] = useState<string[]>([]);
  const [calculando, setCalculando] = useState(false);
  const [restaurando, setRestaurando] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Época de inputs/RFC (guard de respuestas obsoletas) + requests en vuelo.
  const epochRef = useRef(0);
  const pendientesRef = useRef(0);
  // Evita el auto-cálculo inmediatamente después de restaurar: el resultado
  // ya viene guardado, no hay que recalcular (ni re-persistir) al montar.
  const saltarAutoCalculoRef = useRef(true);
  // RFC ya restaurada: los refetch globales de empresas (mismo RFC) no deben
  // pisar los inputs que el usuario esté editando.
  const rfcRestauradoRef = useRef<string | null>(null);

  // Refs estables para no re-suscribir efectos por identidad de funciones/objetos.
  const inputsRef = useRef(inputs);
  inputsRef.current = inputs;
  const esValidoRef = useRef(esValido);
  esValidoRef.current = esValido;
  const defaultsRef = useRef(defaults);

  const setInputs = useCallback(
    (
      next:
        | CalculadoraInputs<N>
        | ((prev: CalculadoraInputs<N>) => CalculadoraInputs<N>),
    ) => {
      epochRef.current += 1;
      setInputsState(next);
    },
    [],
  );

  const setInput = useCallback(
    <K extends keyof CalculadoraInputs<N>>(campo: K, valor: CalculadoraInputs<N>[K]) => {
      setInputs((prev) => ({ ...prev, [campo]: valor }));
    },
    [setInputs],
  );

  // ---------------------------------------------------------------------
  // Restaurar estado al montar y al cambiar la empresa activa
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (!isConnected || empresasLoading) return;
    if (rfcRestauradoRef.current === rfcActivo) return;
    rfcRestauradoRef.current = rfcActivo;

    let activo = true;
    epochRef.current += 1; // invalida cálculos en vuelo de la RFC anterior
    const epoch = epochRef.current;
    setRestaurando(true);
    setError(null);

    apiClient
      .calculadoraEstadoDe(rfcActivo, nombre)
      .then((r) => {
        if (!activo || epochRef.current !== epoch) return;
        saltarAutoCalculoRef.current = true;
        if (r.estado) {
          setInputsState({
            ...defaultsRef.current,
            ...(r.estado.inputs as Partial<CalculadoraInputs<N>>),
          });
          setResultado(r.estado.resultado as unknown as CalculadoraResultadoMap[N]);
        } else {
          setInputsState(defaultsRef.current);
          setResultado(null);
        }
        setAdvertencias([]);
      })
      .catch(() => {
        // Sin estado restaurable: se arranca de los defaults sin molestar.
        if (!activo || epochRef.current !== epoch) return;
        saltarAutoCalculoRef.current = true;
        setInputsState(defaultsRef.current);
        setResultado(null);
        setAdvertencias([]);
      })
      .finally(() => {
        if (activo) setRestaurando(false);
      });

    return () => {
      activo = false;
    };
  }, [apiClient, isConnected, empresasLoading, rfcActivo, nombre]);

  // ---------------------------------------------------------------------
  // Cálculo (compartido por el debounce y por `calcular()` manual)
  // ---------------------------------------------------------------------
  // `epochAlDisparar` se captura al AGENDAR el cálculo (no al ejecutarlo):
  // si entre el agendado y el disparo cambió la RFC o los inputs, se aborta
  // antes de pegarle al agente (evita persistir inputs viejos bajo otra RFC).
  const dispatch = useCallback(async (epochAlDisparar?: number) => {
    const epoch = epochAlDisparar ?? epochRef.current;
    if (epochRef.current !== epoch) return;

    const actuales = inputsRef.current;
    if (!esValidoRef.current(actuales)) return;

    pendientesRef.current += 1;
    setCalculando(true);
    try {
      const body = {
        ...actuales,
        rfc: rfcActivo === RFC_GENERAL ? null : rfcActivo,
      } as CalculadoraRequestMap[N];
      const r = await apiClient.calculadoraCalcular(nombre, body);
      // Cambió la RFC o los inputs desde que se disparó → respuesta obsoleta.
      if (epochRef.current !== epoch) return;
      setResultado(r.resultado);
      setAdvertencias(r.advertencias);
      setError(null);
    } catch (e) {
      if (epochRef.current !== epoch) return;
      const msg =
        e instanceof ApiError && e.status === 422
          ? 'Revisa los datos capturados: hay campos con valores inválidos.'
          : mensajeDeError(e);
      setError(msg);
      toast.error(msg, { id: `calculadora-${nombre}` });
    } finally {
      pendientesRef.current -= 1;
      if (pendientesRef.current === 0) setCalculando(false);
    }
  }, [apiClient, nombre, rfcActivo]);

  // ---------------------------------------------------------------------
  // Cálculo reactivo con debounce (excepto en modo manual)
  // ---------------------------------------------------------------------
  useEffect(() => {
    if (manual || restaurando) return;
    if (saltarAutoCalculoRef.current) {
      saltarAutoCalculoRef.current = false;
      return;
    }
    if (!esValidoRef.current(inputs)) return;
    const epoch = epochRef.current;
    const timer = setTimeout(() => {
      void dispatch(epoch);
    }, DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [inputs, manual, restaurando, dispatch]);

  // Sin args: si se usara directo como onClick, el MouseEvent no debe
  // colarse como época del dispatch.
  const calcular = useCallback(() => dispatch(), [dispatch]);

  const recalcular = useCallback(() => {
    void dispatch();
  }, [dispatch]);

  return {
    rfcActivo,
    inputs,
    setInput,
    setInputs,
    resultado,
    advertencias,
    calculando,
    restaurando,
    error,
    recalcular,
    calcular,
  };
}

/**
 * Indicadores del ejercicio (UMA, SMG, estados ISN, clases de riesgo, tipos de
 * terminación). Poblan los selects de las calculadoras; null mientras cargan.
 */
export function useIndicadores(anio = 2026): IndicadoresCalculadoras | null {
  const { apiClient, isConnected } = useServer();
  const [indicadores, setIndicadores] = useState<IndicadoresCalculadoras | null>(null);

  useEffect(() => {
    if (!isConnected) return;
    let activo = true;
    apiClient
      .calculadoraIndicadores(anio)
      .then((r) => {
        if (activo) setIndicadores(r);
      })
      .catch(() => {
        // Los selects que dependen de esto muestran fallbacks; no molestamos.
      });
    return () => {
      activo = false;
    };
  }, [apiClient, isConnected, anio]);

  return indicadores;
}

'use client';

import { useCallback, useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { CfdiValidarInput, ValidarResult } from '@/lib/types';

// ---------------------------------------------------------------------------
// Summary shape
// ---------------------------------------------------------------------------

export interface ValidacionSummary {
  vigentes: number;
  cancelados: number;
  noEncontrados: number;
  errores: number;
}

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

interface UseValidacionReturn {
  validate: (cfdis: CfdiValidarInput[]) => Promise<void>;
  isValidating: boolean;
  progress: number;
  results: ValidarResult[];
  summary: ValidacionSummary | null;
  exportCsv: () => void;
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const BATCH_SIZE = 50;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function computeSummary(results: ValidarResult[]): ValidacionSummary {
  let vigentes = 0;
  let cancelados = 0;
  let noEncontrados = 0;
  let errores = 0;

  for (const r of results) {
    const estado = (r.estado ?? '').toLowerCase();
    if (r.error) {
      errores++;
    } else if (estado.includes('vigente')) {
      vigentes++;
    } else if (estado.includes('cancelado')) {
      cancelados++;
    } else if (estado.includes('no encontrado') || estado === '') {
      noEncontrados++;
    } else {
      // Unknown state — count as error
      errores++;
    }
  }

  return { vigentes, cancelados, noEncontrados, errores };
}

function buildCsvContent(results: ValidarResult[]): string {
  const header = 'UUID,Estado,EsCancelable,EstatusCancelacion,ValidacionEFOS,Error';
  const rows = results.map((r) => {
    const fields = [
      r.uuid,
      r.estado ?? '',
      r.es_cancelable ?? '',
      r.estatus_cancelacion ?? '',
      r.validacion_efos ?? '',
      r.error ?? '',
    ];
    // Escape fields that contain commas or quotes
    return fields
      .map((f) => {
        if (f.includes(',') || f.includes('"') || f.includes('\n')) {
          return `"${f.replace(/"/g, '""')}"`;
        }
        return f;
      })
      .join(',');
  });

  return [header, ...rows].join('\n');
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useValidacion(): UseValidacionReturn {
  const { apiClient } = useServer();

  const [isValidating, setIsValidating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [results, setResults] = useState<ValidarResult[]>([]);
  const [summary, setSummary] = useState<ValidacionSummary | null>(null);

  // Abort ref so we can cancel an in-flight validation
  const abortRef = useRef(false);

  const validate = useCallback(
    async (cfdis: CfdiValidarInput[]) => {
      if (cfdis.length === 0) return;

      abortRef.current = false;
      setIsValidating(true);
      setProgress(0);
      setResults([]);
      setSummary(null);

      const allResults: ValidarResult[] = [];
      const totalBatches = Math.ceil(cfdis.length / BATCH_SIZE);

      for (let i = 0; i < totalBatches; i++) {
        if (abortRef.current) break;

        const batch = cfdis.slice(i * BATCH_SIZE, (i + 1) * BATCH_SIZE);

        try {
          const response = await apiClient.validar({ cfdis: batch });
          allResults.push(...response.results);
        } catch (err) {
          // On error, create error entries for the batch
          for (const cfdi of batch) {
            allResults.push({
              uuid: cfdi.uuid,
              estado: '',
              es_cancelable: null,
              estatus_cancelacion: null,
              validacion_efos: null,
              error: err instanceof Error ? err.message : 'Error desconocido',
            });
          }
        }

        const pct = Math.round(((i + 1) / totalBatches) * 100);
        setProgress(pct);
        setResults([...allResults]);
      }

      setSummary(computeSummary(allResults));
      setIsValidating(false);
    },
    [apiClient],
  );

  const exportCsv = useCallback(() => {
    if (results.length === 0) return;

    const csv = buildCsvContent(results);
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `validacion-cfdi-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();

    URL.revokeObjectURL(url);
  }, [results]);

  const reset = useCallback(() => {
    abortRef.current = true;
    setIsValidating(false);
    setProgress(0);
    setResults([]);
    setSummary(null);
  }, []);

  return { validate, isValidating, progress, results, summary, exportCsv, reset };
}

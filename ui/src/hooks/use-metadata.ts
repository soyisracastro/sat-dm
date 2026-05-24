'use client';

import { useCallback, useMemo, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import type { MetadataRecord, SolicitudRequest } from '@/lib/types';

// ---------------------------------------------------------------------------
// Stats computed from records
// ---------------------------------------------------------------------------

export interface MetadataStats {
  total: number;
  vigentes: number;
  cancelados: number;
  montoTotal: number;
}

// ---------------------------------------------------------------------------
// Hook return type
// ---------------------------------------------------------------------------

export interface UseMetadataReturn {
  records: MetadataRecord[];
  isLoading: boolean;
  error: string | null;
  stats: MetadataStats;
  fetchMetadata: (request: SolicitudRequest) => Promise<void>;
  exportCsv: () => void;
}

// ---------------------------------------------------------------------------
// CSV generation helper
// ---------------------------------------------------------------------------

function generateCsv(records: MetadataRecord[]): string {
  const headers = [
    'UUID',
    'RFC Emisor',
    'Nombre Emisor',
    'RFC Receptor',
    'Nombre Receptor',
    'RFC PAC',
    'Fecha Emision',
    'Fecha Certificacion',
    'Monto',
    'Efecto Comprobante',
    'Estatus',
    'Fecha Cancelacion',
  ];

  const rows = records.map((r) =>
    [
      r.uuid,
      r.rfc_emisor,
      r.nombre_emisor,
      r.rfc_receptor,
      r.nombre_receptor,
      r.rfc_pac,
      r.fecha_emision,
      r.fecha_certificacion,
      r.monto,
      r.efecto_comprobante,
      r.estatus,
      r.fecha_cancelacion,
    ]
      .map((field) => {
        // Escape double quotes and wrap in quotes if the field contains commas or quotes
        const str = String(field ?? '');
        if (str.includes(',') || str.includes('"') || str.includes('\n')) {
          return `"${str.replace(/"/g, '""')}"`;
        }
        return str;
      })
      .join(','),
  );

  return [headers.join(','), ...rows].join('\n');
}

// ---------------------------------------------------------------------------
// Hook implementation
// ---------------------------------------------------------------------------

export function useMetadata(): UseMetadataReturn {
  const { apiClient } = useServer();

  const [records, setRecords] = useState<MetadataRecord[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // -----------------------------------------------------------------------
  // Computed stats
  // -----------------------------------------------------------------------

  const stats: MetadataStats = useMemo(() => {
    let vigentes = 0;
    let cancelados = 0;
    let montoTotal = 0;

    for (const r of records) {
      const estatus = (r.estatus ?? '').toLowerCase();
      if (estatus === '0' || estatus === 'vigente') {
        vigentes++;
      } else if (estatus === '1' || estatus === 'cancelado') {
        cancelados++;
      }

      const monto = parseFloat(r.monto);
      if (!isNaN(monto)) {
        montoTotal += monto;
      }
    }

    return {
      total: records.length,
      vigentes,
      cancelados,
      montoTotal,
    };
  }, [records]);

  // -----------------------------------------------------------------------
  // fetchMetadata
  // -----------------------------------------------------------------------

  const fetchMetadata = useCallback(
    async (request: SolicitudRequest) => {
      try {
        setIsLoading(true);
        setError(null);
        setRecords([]);

        const res = await apiClient.metadata(request);
        setRecords(res.records);
      } catch (err) {
        const msg = err instanceof Error ? err.message : String(err);
        setError(`Error al obtener metadata: ${msg}`);
      } finally {
        setIsLoading(false);
      }
    },
    [apiClient],
  );

  // -----------------------------------------------------------------------
  // exportCsv
  // -----------------------------------------------------------------------

  const exportCsv = useCallback(() => {
    if (records.length === 0) return;

    const csv = generateCsv(records);
    const blob = new Blob(['\uFEFF' + csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = url;
    link.download = `metadata_sat_${new Date().toISOString().slice(0, 10)}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [records]);

  return {
    records,
    isLoading,
    error,
    stats,
    fetchMetadata,
    exportCsv,
  };
}

'use client';

import { useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { PagosFiltros, ReportePagosHuerfanos } from '@/lib/types';

interface Props {
  filtros: Partial<PagosFiltros>;
}

function formatoFecha(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatoMXN(n: number): string {
  return new Intl.NumberFormat('es-MX', {
    style: 'currency',
    currency: 'MXN',
    minimumFractionDigits: 2,
  }).format(n);
}

export function PagosHuerfanosTable({ filtros }: Props) {
  const { apiClient } = useServer();
  const [data, setData] = useState<ReportePagosHuerfanos | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    apiClient
      .procesadorPagosReporte('huerfanos', filtros)
      .then((r) => {
        if (mounted) setData(r);
      })
      .catch((e) => {
        if (mounted) setError(e instanceof Error ? e.message : String(e));
      });
    return () => {
      mounted = false;
    };
  }, [apiClient, JSON.stringify(filtros)]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }
  if (!data || data.items.length === 0) return null;

  return (
    <Card className="border-amber-300">
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Icon icon="ph:question-light" className="size-4 text-amber-700" />
          Pagos huérfanos ({data.items.length})
        </CardTitle>
        <CardDescription>
          Complementos cuyos documentos relacionados no están cargados en el procesador. Carga
          las facturas PPD originales para conciliar.
        </CardDescription>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>UUID Pago</TableHead>
              <TableHead>Fecha</TableHead>
              <TableHead>Emisor</TableHead>
              <TableHead className="text-right">Monto</TableHead>
              <TableHead>Documentos referenciados</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.items.map((h) => (
              <TableRow key={h.cfdi_pago_uuid}>
                <TableCell className="font-mono text-xs">{h.cfdi_pago_uuid}</TableCell>
                <TableCell className="text-xs">{formatoFecha(h.fecha_emision)}</TableCell>
                <TableCell className="text-xs">
                  <div className="font-medium">{h.emisor_nombre}</div>
                  <div className="font-mono text-[10px] text-muted-foreground">
                    {h.emisor_rfc}
                  </div>
                </TableCell>
                <TableCell className="text-right font-mono text-xs">
                  {formatoMXN(h.monto)}
                </TableCell>
                <TableCell className="font-mono text-[10px] break-all text-muted-foreground">
                  {h.documentos_referenciados?.split('|').join(' · ')}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

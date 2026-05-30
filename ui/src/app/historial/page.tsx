'use client';

import { useCallback, useState } from 'react';
import Link from 'next/link';

import { useHistorial } from '@/hooks/use-historial';
import { useEmpresas } from '@/hooks/use-empresas';
import { useServer } from '@/providers/server-provider';
import { PageHeading } from '@/components/layout/page-heading';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
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
import type { CanalDescarga, HistorialItem, TipoDescarga } from '@/lib/types';

const TIPO_META: Record<TipoDescarga, { label: string; icon: string }> = {
  cfdi: { label: 'CFDIs', icon: 'ph:download-simple-light' },
  metadata: { label: 'Metadata', icon: 'ph:database-light' },
  constancia: { label: 'Constancia', icon: 'ph:file-text-light' },
  opinion: { label: 'Opinión 32-D', icon: 'ph:seal-check-light' },
};

const CANAL_LABEL: Record<CanalDescarga, string> = {
  ws: 'Web Service',
  ciec: 'CIEC',
  fiel: 'e.firma',
};

function fechaLegible(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-MX', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export default function HistorialPage() {
  const { descargas, loading, error, refresh } = useHistorial();
  const { empresas } = useEmpresas();
  const { apiClient } = useServer();
  const [accionError, setAccionError] = useState<string | null>(null);

  // Empresa activa = la marcada como default en el catálogo del agente. El
  // historial solo muestra sus descargas; para ver otra, actívala en /empresas.
  const empresaActiva = empresas.find((e) => e.default);

  const abrir = useCallback(
    async (ruta: string, modo: 'carpeta' | 'archivo') => {
      setAccionError(null);
      try {
        await apiClient.abrir(ruta, modo);
      } catch (e) {
        setAccionError(e instanceof Error ? e.message : String(e));
      }
    },
    [apiClient],
  );

  const filtradas = empresaActiva
    ? descargas.filter((d) => d.rfc === empresaActiva.rfc)
    : [];

  const description = empresaActiva
    ? `Descargas completadas de ${empresaActiva.nombre} (${empresaActiva.rfc}).`
    : 'Selecciona una empresa activa en Empresas para ver su historial.';

  return (
    <div className="space-y-6">
      <PageHeading
        title="Historial"
        description={description}
        action={
          <Button variant="outline" size="sm" onClick={refresh} disabled={loading}>
            {loading ? (
              <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
            ) : (
              <Icon icon="ph:arrows-clockwise-light" className="size-4" />
            )}
            Actualizar
          </Button>
        }
      />

      {(error || accionError) && (
        <Alert variant="destructive">
          <AlertDescription>{accionError || error}</AlertDescription>
        </Alert>
      )}

      {!empresaActiva ? (
        <Alert>
          <Icon icon="ph:info-light" className="size-4" />
          <AlertDescription>
            No hay empresa activa. Actívala desde{' '}
            <Link href="/empresas" className="font-medium underline underline-offset-2">
              Empresas
            </Link>
            .
          </AlertDescription>
        </Alert>
      ) : filtradas.length === 0 ? (
        <Card className="flex flex-col items-center gap-2 p-10 text-center">
          <Icon icon="ph:clock-counter-clockwise-light" className="size-8 text-muted-foreground" />
          <p className="text-sm font-medium">Aún no hay descargas registradas</p>
          <p className="text-sm text-muted-foreground">
            Cuando completes una descarga (CIEC o Web Service) aparecerá aquí.
          </p>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Fecha</TableHead>
                <TableHead>Descarga</TableHead>
                <TableHead className="text-right">CFDIs</TableHead>
                <TableHead className="text-right">Acciones</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtradas.map((d, i) => (
                <DescargaRow
                  key={`${d.rfc}-${d.timestamp}-${i}`}
                  d={d}
                  onAbrir={abrir}
                />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

function DescargaRow({
  d,
  onAbrir,
}: {
  d: HistorialItem;
  onAbrir: (ruta: string, modo: 'carpeta' | 'archivo') => Promise<void>;
}) {
  const meta = TIPO_META[d.tipo] ?? { label: d.tipo, icon: 'ph:download-simple-light' };
  const [busy, setBusy] = useState<'carpeta' | 'archivo' | null>(null);

  // Un PDF (constancia/opinión) se puede abrir directo; los CFDIs son una carpeta.
  const esPdf =
    (d.tipo === 'constancia' || d.tipo === 'opinion') &&
    !!d.ruta &&
    d.ruta.toLowerCase().endsWith('.pdf');

  async function abrir(modo: 'carpeta' | 'archivo') {
    setBusy(modo);
    try {
      await onAbrir(d.ruta, modo);
    } finally {
      setBusy(null);
    }
  }

  return (
    <TableRow>
      <TableCell className="whitespace-nowrap text-sm text-muted-foreground">
        {fechaLegible(d.timestamp)}
      </TableCell>
      <TableCell>
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <Badge variant="secondary" className="gap-1">
              <Icon icon={meta.icon} className="size-3" /> {meta.label}
            </Badge>
            <span className="text-xs text-muted-foreground">{CANAL_LABEL[d.canal] ?? d.canal}</span>
          </div>
          {d.descripcion && (
            <span className="text-xs text-muted-foreground">{d.descripcion}</span>
          )}
        </div>
      </TableCell>
      <TableCell className="text-right font-mono text-sm">
        {d.total ?? '—'}
      </TableCell>
      <TableCell className="text-right">
        {d.ruta && (
          <div className="inline-flex items-center gap-1">
            {esPdf && (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => abrir('archivo')}
                disabled={busy !== null}
                title="Abrir el PDF"
              >
                {busy === 'archivo' ? (
                  <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
                ) : (
                  <Icon icon="ph:file-pdf-light" className="size-4" />
                )}
              </Button>
            )}
            <Button
              variant="ghost"
              size="icon"
              onClick={() => abrir('carpeta')}
              disabled={busy !== null}
              title="Abrir la carpeta donde se guardó"
            >
              {busy === 'carpeta' ? (
                <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
              ) : (
                <Icon icon="ph:folder-open-light" className="size-4" />
              )}
            </Button>
          </div>
        )}
      </TableCell>
    </TableRow>
  );
}

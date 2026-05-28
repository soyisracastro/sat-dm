'use client';

import { Icon } from '@/components/ui/icon';
import type { Solicitud } from '@/lib/types';

interface SolicitudRowExpandedProps {
  solicitud: Solicitud;
}

function fechaLegible(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString('es-MX', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function SolicitudRowExpanded({ solicitud }: SolicitudRowExpandedProps) {
  const nPaquetes = solicitud.package_ids?.length ?? 0;
  const esError = solicitud.estado === '4' || solicitud.estado === '5';

  return (
    <div className="space-y-3 text-sm">
      <dl className="grid gap-x-6 gap-y-2 sm:grid-cols-2">
        {solicitud.mensaje && <Row label="Mensaje SAT" value={solicitud.mensaje} />}
        {solicitud.numero_cfdis != null && (
          <Row
            label="CFDIs reportados"
            value={solicitud.numero_cfdis.toLocaleString('es-MX')}
          />
        )}
        {nPaquetes > 0 && (
          <Row
            label="Paquetes"
            value={`${nPaquetes} ${nPaquetes === 1 ? 'paquete' : 'paquetes'}`}
          />
        )}
        <Row label="Creada" value={fechaLegible(solicitud.timestamp)} />
        <Row
          label="SAT request ID"
          value={<span className="font-mono text-xs break-all">{solicitud.id_solicitud}</span>}
        />
      </dl>

      {esError && solicitud.mensaje && (
        <div className="flex gap-2 rounded-md border border-destructive/30 bg-destructive/5 p-3 text-xs text-destructive">
          <Icon icon="ph:warning-circle-light" className="size-4 shrink-0 mt-0.5" />
          <p>{solicitud.mensaje}</p>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between gap-4">
      <dt className="text-muted-foreground">{label}</dt>
      <dd className="text-foreground text-right min-w-0 truncate">{value}</dd>
    </div>
  );
}

'use client';

import { cn } from '@/lib/utils';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import type { Solicitud } from '@/lib/types';

// Mapeo del estado SAT (o "solicitada"/"descargada") a etiqueta + color del badge.
// Códigos SAT: 1=En cola · 2=Procesando · 3=Lista · 4=Error · 5=Rechazada.
const ESTADO_META: Record<
  string,
  { label: string; clase: string; icon?: string; spin?: boolean }
> = {
  solicitada: {
    label: 'Solicitada',
    clase:
      'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300',
  },
  '1': {
    label: 'En cola',
    clase:
      'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-400',
  },
  '2': {
    label: 'Procesando',
    clase:
      'border-blue-200 bg-blue-50 text-blue-700 dark:border-blue-900 dark:bg-blue-950 dark:text-blue-400',
    icon: 'ph:circle-notch-light',
    spin: true,
  },
  '3': {
    label: 'Lista',
    clase:
      'border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950 dark:text-green-400',
    icon: 'ph:check-circle-light',
  },
  '4': {
    label: 'Error',
    clase:
      'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400',
    icon: 'ph:x-circle-light',
  },
  '5': {
    label: 'Rechazada',
    clase:
      'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400',
    icon: 'ph:x-circle-light',
  },
  descargada: {
    label: 'Descargada',
    clase:
      'border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950 dark:text-green-400',
    icon: 'ph:download-simple-light',
  },
};

function fechaCorta(iso: string): string {
  // "YYYY-MM-DD" → "DD MMM YYYY" en es-MX, sin pegarle a timezones (string puro).
  const [y, m, d] = iso.split('-').map(Number);
  if (!y || !m || !d) return iso;
  const date = new Date(y, m - 1, d);
  return date.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', year: 'numeric' });
}

function timestampLegible(iso: string): string {
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

interface SolicitudesListProps {
  solicitudes: Solicitud[];
  loading: boolean;
}

export function SolicitudesList({ solicitudes, loading }: SolicitudesListProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Solicitudes recientes</CardTitle>
      </CardHeader>
      <CardContent>
        {loading && solicitudes.length === 0 ? (
          <div className="flex items-center justify-center gap-2 py-8 text-sm text-muted-foreground">
            <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
            Cargando solicitudes…
          </div>
        ) : solicitudes.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-8 text-center">
            <Icon icon="ph:cloud-arrow-down-light" className="size-8 text-muted-foreground" />
            <p className="text-sm font-medium">Sin solicitudes de descarga</p>
            <p className="text-sm text-muted-foreground">
              Usa el formulario de arriba para solicitar tu primera descarga masiva al SAT.
            </p>
          </div>
        ) : (
          <div className="-mx-6 overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="pl-6">Fecha</TableHead>
                  <TableHead>Período</TableHead>
                  <TableHead>Tipo</TableHead>
                  <TableHead className="pr-6">Estado</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {solicitudes.map((s) => (
                  <SolicitudRow key={s.id_solicitud} s={s} />
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function SolicitudRow({ s }: { s: Solicitud }) {
  const meta = ESTADO_META[s.estado] ?? {
    label: s.estado || 'Desconocido',
    clase:
      'border-slate-200 bg-slate-50 text-slate-700 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300',
  };
  return (
    <TableRow>
      <TableCell className="whitespace-nowrap pl-6 text-sm text-muted-foreground">
        {timestampLegible(s.timestamp)}
      </TableCell>
      <TableCell className="text-sm">
        {fechaCorta(s.fecha_inicio)} → {fechaCorta(s.fecha_fin)}
      </TableCell>
      <TableCell className="text-sm">{s.tipo || '—'}</TableCell>
      <TableCell className="pr-6">
        <span
          className={cn(
            'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
            meta.clase,
          )}
        >
          {meta.icon && (
            <Icon
              icon={meta.icon}
              className={cn('size-3 shrink-0', meta.spin && 'animate-spin')}
            />
          )}
          {meta.label}
        </span>
      </TableCell>
    </TableRow>
  );
}

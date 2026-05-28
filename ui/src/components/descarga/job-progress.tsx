'use client';

import { Card } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';
import type { JobUiEstado, LogEntry } from '@/hooks/use-ciec-job';

interface JobProgressProps {
  estado: JobUiEstado;
  log: LogEntry[];
  resultado: unknown;
  error: string | null;
}

const ESTADO_LABEL: Record<JobUiEstado, string> = {
  idle: 'Sin actividad',
  iniciando: 'Iniciando…',
  corriendo: 'En progreso…',
  captcha: 'Esperando captcha…',
  done: 'Completado',
  error: 'Error',
  cancelled: 'Cancelado',
};

function EstadoIcon({ estado }: { estado: JobUiEstado }) {
  if (estado === 'done') return <Icon icon="ph:check-circle-light" className="size-4 text-success" />;
  if (estado === 'error') return <Icon icon="ph:x-circle-light" className="size-4 text-destructive" />;
  if (estado === 'cancelled') return <Icon icon="ph:prohibit-light" className="size-4 text-muted-foreground" />;
  if (estado === 'captcha') return <Icon icon="ph:key-light" className="size-4 text-primary" />;
  return <Icon icon="ph:circle-notch-light" className="size-4 animate-spin text-primary" />;
}

const LEVEL_COLOR: Record<NonNullable<LogEntry['level']>, string> = {
  info: 'text-slate-300',
  ok: 'text-emerald-400',
  warn: 'text-amber-400',
  error: 'text-red-400',
};

function Resumen({ resultado }: { resultado: unknown }) {
  if (!resultado || typeof resultado !== 'object') return null;
  const r = resultado as Record<string, unknown>;
  if (typeof r.total === 'number') {
    return (
      <p className="text-sm">
        <span className="font-semibold">{r.total}</span> XML descargados.
      </p>
    );
  }
  if (typeof r.archivo === 'string') {
    return (
      <p className="font-mono text-xs text-muted-foreground break-all">{r.archivo}</p>
    );
  }
  return null;
}

export function JobProgress({ estado, log, resultado, error }: JobProgressProps) {
  if (estado === 'idle') return null;

  return (
    <Card className="space-y-3 p-4">
      <div className="flex items-center gap-2">
        <EstadoIcon estado={estado} />
        <span className="text-sm font-medium">{ESTADO_LABEL[estado]}</span>
      </div>

      {estado === 'done' && <Resumen resultado={resultado} />}
      {estado === 'error' && error && (
        <p className="text-sm text-destructive">{error}</p>
      )}

      {/* Log estilo terminal */}
      <div className="max-h-56 overflow-y-auto rounded-md bg-[#0A1628] p-3 font-mono text-[11px] leading-relaxed">
        {log.length === 0 ? (
          <span className="text-slate-500">Sin eventos todavía…</span>
        ) : (
          log.map((l, i) => (
            <div key={i} className="whitespace-pre-wrap">
              <span className="text-slate-500">{l.t}</span>{' '}
              <span className={cn(LEVEL_COLOR[l.level ?? 'info'])}>{l.msg}</span>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

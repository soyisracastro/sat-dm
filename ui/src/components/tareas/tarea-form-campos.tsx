'use client';

import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { nombreCortoEmpresa, PRIORIDADES, TIPO_TAREA_META } from '@/lib/tareas';
import type { Empresa, TareaPrioridad, TareaTipo } from '@/lib/types';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Campos compartidos entre el modal "Nueva tarea" y el drawer de edición.
// Radix Select no acepta value="": la opción "Sin empresa" usa el sentinel
// GENERAL y los callers traducen a null.
// ---------------------------------------------------------------------------

export const EMPRESA_GENERAL = 'general';

export function CampoEmpresa({
  valor,
  onChange,
  empresas,
}: {
  /** RFC o EMPRESA_GENERAL. */
  valor: string;
  onChange: (v: string) => void;
  empresas: Empresa[];
}) {
  const activas = empresas
    .filter((e) => !e.archived_at)
    .sort((a, b) => a.nombre.localeCompare(b.nombre, 'es'));
  return (
    <div className="space-y-2">
      <Label>Empresa</Label>
      <Select value={valor} onValueChange={onChange}>
        <SelectTrigger className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={EMPRESA_GENERAL}>Sin empresa (general)</SelectItem>
          {activas.map((e) => (
            <SelectItem key={e.rfc} value={e.rfc}>
              {nombreCortoEmpresa(e.nombre)}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

export function CampoFecha({
  valor,
  onChange,
}: {
  valor: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor="tarea-fecha">Fecha límite</Label>
      <Input
        id="tarea-fecha"
        type="date"
        value={valor}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  );
}

export function CampoTipo({
  valor,
  onChange,
}: {
  valor: TareaTipo;
  onChange: (v: TareaTipo) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>Tipo</Label>
      <Select value={valor} onValueChange={(v) => onChange(v as TareaTipo)}>
        <SelectTrigger className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(Object.entries(TIPO_TAREA_META) as [TareaTipo, { label: string }][]).map(
            ([tipo, meta]) => (
              <SelectItem key={tipo} value={tipo}>
                {meta.label}
              </SelectItem>
            ),
          )}
        </SelectContent>
      </Select>
    </div>
  );
}

export function CampoPrioridad({
  valor,
  onChange,
}: {
  valor: TareaPrioridad;
  onChange: (v: TareaPrioridad) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>Prioridad</Label>
      <div className="grid grid-cols-3 gap-1 rounded-lg bg-secondary p-1">
        {PRIORIDADES.map((p) => (
          <button
            key={p.valor}
            type="button"
            onClick={() => onChange(p.valor)}
            className={cn(
              'flex items-center justify-center gap-1.5 rounded-md px-2 py-1.5 text-[12.5px] font-semibold transition-colors',
              valor === p.valor
                ? 'bg-card text-foreground shadow-xs'
                : 'text-muted-foreground hover:text-foreground',
            )}
          >
            <span
              className={cn(
                'size-2 rounded-full',
                p.valor === 'alta' && 'bg-destructive',
                p.valor === 'media' && 'bg-warning',
                p.valor === 'baja' && 'bg-input',
              )}
            />
            {p.label}
          </button>
        ))}
      </div>
    </div>
  );
}

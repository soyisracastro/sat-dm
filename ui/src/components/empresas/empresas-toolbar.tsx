'use client';

import { cn } from '@/lib/utils';
import { tipoPersona } from '@/lib/empresa-visual';
import {
  ORDENES,
  type FiltroEstado,
  type FiltroTipo,
  type OrdenEmpresas,
} from '@/lib/empresas-filtro';
import type { Empresa } from '@/lib/types';
import { Icon } from '@/components/ui/icon';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface EmpresasToolbarProps {
  /** Empresas de la vista actual (antes de filtrar), para los contadores. */
  empresas: Empresa[];
  q: string;
  onQ: (q: string) => void;
  tipo: FiltroTipo;
  onTipo: (t: FiltroTipo) => void;
  estado: FiltroEstado;
  onEstado: (e: FiltroEstado) => void;
  orden: OrdenEmpresas;
  onOrden: (o: OrdenEmpresas) => void;
  /** false = sin filtro de estado (vista de archivadas). */
  conEstado?: boolean;
}

/**
 * Toolbar de la lista de Empresas: búsqueda por nombre/RFC, segmentado
 * Todas/Morales/Físicas con contadores, filtro de estado y orden.
 */
export function EmpresasToolbar({
  empresas,
  q,
  onQ,
  tipo,
  onTipo,
  estado,
  onEstado,
  orden,
  onOrden,
  conEstado = true,
}: EmpresasToolbarProps) {
  const nPM = empresas.filter((e) => tipoPersona(e.rfc) === 'PM').length;
  const nPF = empresas.length - nPM;

  return (
    <div className="flex flex-wrap items-center gap-2.5">
      {/* Búsqueda */}
      <div className="flex h-9 min-w-[200px] flex-1 basis-60 items-center gap-2 rounded-lg border border-input bg-card px-2.5 text-muted-foreground transition-colors focus-within:border-ring">
        <Icon icon="ph:magnifying-glass-light" className="size-4 shrink-0" />
        <input
          value={q}
          onChange={(e) => onQ(e.target.value)}
          placeholder="Buscar por nombre o RFC…"
          className="min-w-0 flex-1 bg-transparent text-[13px] text-foreground outline-none placeholder:text-muted-foreground/70"
        />
        {q && (
          <button
            type="button"
            onClick={() => onQ('')}
            title="Limpiar"
            className="rounded p-0.5 transition-colors hover:bg-secondary hover:text-foreground"
          >
            <Icon icon="ph:x-light" className="size-3.5" />
          </button>
        )}
      </div>

      {/* Tipo (segmentado con contadores) */}
      <div className="inline-flex gap-0.5 rounded-lg bg-secondary p-[3px]">
        <SegBtn on={tipo === 'todas'} onClick={() => onTipo('todas')} label="Todas" count={empresas.length} />
        <SegBtn on={tipo === 'PM'} onClick={() => onTipo('PM')} label="Morales" count={nPM} />
        <SegBtn on={tipo === 'PF'} onClick={() => onTipo('PF')} label="Físicas" count={nPF} />
      </div>

      {/* Estado */}
      {conEstado && (
        <Select value={estado} onValueChange={(v) => onEstado(v as FiltroEstado)}>
          <SelectTrigger className="h-9 w-auto min-w-[150px] text-[12.5px]">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="todos">Todos los estados</SelectItem>
            <SelectItem value="atencion">Requieren atención</SelectItem>
            <SelectItem value="aldia">Al día</SelectItem>
          </SelectContent>
        </Select>
      )}

      {/* Orden */}
      <Select value={orden} onValueChange={(v) => onOrden(v as OrdenEmpresas)}>
        <SelectTrigger className="h-9 w-auto min-w-[170px] text-[12.5px]">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {(Object.entries(ORDENES) as [OrdenEmpresas, string][]).map(([k, label]) => (
            <SelectItem key={k} value={k}>
              Ordenar: {label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

function SegBtn({
  on,
  onClick,
  label,
  count,
}: {
  on: boolean;
  onClick: () => void;
  label: string;
  count: number;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        'inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-[12.5px] font-semibold transition-colors',
        on ? 'bg-card text-primary shadow-xs' : 'text-muted-foreground hover:text-foreground',
      )}
    >
      {label}
      <span
        className={cn(
          'rounded-full px-1.5 text-[11px] font-bold tabular-nums',
          on ? 'bg-accent text-primary' : 'bg-secondary text-muted-foreground',
        )}
      >
        {count}
      </span>
    </button>
  );
}

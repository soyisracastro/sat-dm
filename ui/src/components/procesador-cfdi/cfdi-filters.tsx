'use client';

import { useState } from 'react';

import { cn } from '@/lib/utils';
import { Card } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import { Icon } from '@/components/ui/icon';
import type { CfdiFiltros, CfdiTipo } from '@/lib/types';

interface Props {
  filtros: CfdiFiltros;
  setFiltro: <K extends keyof CfdiFiltros>(key: K, value: CfdiFiltros[K]) => void;
  reset: () => void;
  filtrosActivos: number;
}

const TIPOS: { value: CfdiTipo | 'todos'; label: string }[] = [
  { value: 'todos', label: 'Todos' },
  { value: 'I', label: 'Ingreso' },
  { value: 'E', label: 'Egreso' },
  { value: 'P', label: 'Pago' },
  { value: 'N', label: 'Nómina' },
  { value: 'T', label: 'Traslado' },
];

const DIRECCIONES: { value: 'todos' | 'E' | 'R'; label: string }[] = [
  { value: 'todos', label: 'Ambos' },
  { value: 'R', label: 'Recibidos' },
  { value: 'E', label: 'Emitidos' },
];

export function CfdiFiltersPanel({ filtros, setFiltro, reset, filtrosActivos }: Props) {
  const [open, setOpen] = useState(true);

  return (
    <Card className="gap-0 overflow-hidden py-0">
      {/* Encabezado-toggle: contador de filtros activos + nota cuando está
          colapsado, para saber de un vistazo si el listado está filtrado. */}
      <button
        type="button"
        className="flex w-full items-center justify-between gap-3.5 px-5 py-3.75 text-left transition-colors hover:bg-secondary"
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        <span className="inline-flex items-center gap-2 text-sm font-bold tracking-tight">
          <Icon icon="ph:funnel-light" className="size-4 text-foreground/70" />
          Filtros
          {filtrosActivos > 0 && (
            <span className="inline-flex h-5 min-w-5 items-center justify-center rounded-full bg-primary px-1.5 text-[11.5px] font-bold tabular-nums text-primary-foreground">
              {filtrosActivos}
            </span>
          )}
          {!open && (
            <span className="whitespace-nowrap text-xs font-medium text-muted-foreground">
              {filtrosActivos > 0
                ? '· el listado está filtrado'
                : '· mostrando todas las facturas'}
            </span>
          )}
        </span>
        <span className="inline-flex items-center gap-3">
          {filtrosActivos > 0 && (
            <span
              role="button"
              tabIndex={0}
              className="text-xs font-semibold text-primary hover:underline hover:underline-offset-2"
              onClick={(e) => {
                e.stopPropagation();
                reset();
              }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                  e.stopPropagation();
                  reset();
                }
              }}
            >
              Limpiar
            </span>
          )}
          <Icon
            icon="ph:caret-down-light"
            className={cn(
              'size-4 text-muted-foreground transition-transform',
              open && 'rotate-180',
            )}
          />
        </span>
      </button>

      {open && (
        <div className="grid grid-cols-1 gap-4 border-t px-5 pb-5 pt-4 md:grid-cols-2 lg:grid-cols-4">
          {/* Búsqueda */}
          <div className="space-y-2 lg:col-span-2">
            <Label htmlFor="busqueda">Búsqueda</Label>
            <Input
              id="busqueda"
              type="search"
              placeholder="UUID, RFC, nombre o folio…"
              value={filtros.busqueda ?? ''}
              onChange={(e) => setFiltro('busqueda', e.target.value || null)}
            />
          </div>

          {/* Tipo */}
          <div className="space-y-2">
            <Label>Tipo</Label>
            <Select
              value={filtros.tipo ?? 'todos'}
              onValueChange={(v) =>
                setFiltro('tipo', v === 'todos' ? null : (v as CfdiTipo))
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIPOS.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Dirección */}
          <div className="space-y-2">
            <Label>Dirección</Label>
            <Select
              value={filtros.direccion ?? 'todos'}
              onValueChange={(v) =>
                setFiltro('direccion', v === 'todos' ? null : (v as 'E' | 'R'))
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DIRECCIONES.map((d) => (
                  <SelectItem key={d.value} value={d.value}>
                    {d.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* Solo con errores */}
          <div className="flex items-end gap-2 pb-1">
            <Switch
              id="solo-errores"
              checked={filtros.solo_con_errores}
              onCheckedChange={(v) => setFiltro('solo_con_errores', v)}
            />
            <Label htmlFor="solo-errores" className="text-sm">
              Solo con advertencias
            </Label>
          </div>

          {/* Fechas */}
          <div className="space-y-2">
            <Label htmlFor="desde">Desde</Label>
            <Input
              id="desde"
              type="date"
              value={filtros.desde ?? ''}
              onChange={(e) => setFiltro('desde', e.target.value || null)}
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="hasta">Hasta</Label>
            <Input
              id="hasta"
              type="date"
              value={filtros.hasta ?? ''}
              onChange={(e) => setFiltro('hasta', e.target.value || null)}
            />
          </div>

          {/* Montos */}
          <div className="space-y-2">
            <Label htmlFor="monto-min">Monto mín.</Label>
            <Input
              id="monto-min"
              type="number"
              step="0.01"
              value={filtros.monto_min ?? ''}
              onChange={(e) =>
                setFiltro('monto_min', e.target.value === '' ? null : Number(e.target.value))
              }
            />
          </div>
          <div className="space-y-2">
            <Label htmlFor="monto-max">Monto máx.</Label>
            <Input
              id="monto-max"
              type="number"
              step="0.01"
              value={filtros.monto_max ?? ''}
              onChange={(e) =>
                setFiltro('monto_max', e.target.value === '' ? null : Number(e.target.value))
              }
            />
          </div>
        </div>
      )}
    </Card>
  );
}

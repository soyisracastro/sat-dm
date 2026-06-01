'use client';

import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';
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
import type { NominaFiltros, TipoNomina } from '@/lib/types';

interface Props {
  filtros: NominaFiltros;
  setFiltro: <K extends keyof NominaFiltros>(key: K, value: NominaFiltros[K]) => void;
  reset: () => void;
  filtrosActivos: number;
}

const TIPO_OPTIONS: { value: TipoNomina | 'todos'; label: string }[] = [
  { value: 'todos', label: 'Todos' },
  { value: 'O', label: 'Ordinaria' },
  { value: 'E', label: 'Extraordinaria' },
];

const PERIODICIDAD_OPTIONS: { value: string; label: string }[] = [
  { value: 'todas', label: 'Todas' },
  { value: '01', label: 'Diario' },
  { value: '02', label: 'Semanal' },
  { value: '03', label: 'Catorcenal' },
  { value: '04', label: 'Quincenal' },
  { value: '05', label: 'Mensual' },
  { value: '06', label: 'Bimestral' },
  { value: '10', label: 'Decenal' },
];

export function NominaFiltersPanel({ filtros, setFiltro, reset, filtrosActivos }: Props) {
  const tipoValue: string = filtros.tipo_nomina ?? 'todos';
  const periodValue: string = filtros.periodicidad ?? 'todas';

  return (
    <Card>
      <CardContent className="space-y-4 pt-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-medium">
            <Icon icon="ph:funnel-light" className="size-4" />
            Filtros
            {filtrosActivos > 0 && (
              <span className="text-xs text-muted-foreground">
                ({filtrosActivos} activo{filtrosActivos > 1 ? 's' : ''})
              </span>
            )}
          </div>
          {filtrosActivos > 0 && (
            <Button variant="ghost" size="sm" onClick={reset}>
              <Icon icon="ph:x-light" className="size-3.5" />
              Limpiar
            </Button>
          )}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="space-y-2 lg:col-span-2">
            <Label htmlFor="busqueda">Búsqueda</Label>
            <Input
              id="busqueda"
              type="search"
              placeholder="RFC, NSS, CURP, nombre, núm. empleado…"
              value={filtros.busqueda ?? ''}
              onChange={(e) => setFiltro('busqueda', e.target.value || null)}
            />
          </div>

          <div className="space-y-2">
            <Label>Tipo de nómina</Label>
            <Select
              value={tipoValue}
              onValueChange={(v) =>
                setFiltro('tipo_nomina', v === 'todos' ? null : (v as TipoNomina))
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIPO_OPTIONS.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Periodicidad</Label>
            <Select
              value={periodValue}
              onValueChange={(v) =>
                setFiltro('periodicidad', v === 'todas' ? null : v)
              }
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {PERIODICIDAD_OPTIONS.map((s) => (
                  <SelectItem key={s.value} value={s.value}>
                    {s.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label htmlFor="desde">Desde (fecha pago)</Label>
            <Input
              id="desde"
              type="date"
              value={filtros.desde ?? ''}
              onChange={(e) => setFiltro('desde', e.target.value || null)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="hasta">Hasta (fecha pago)</Label>
            <Input
              id="hasta"
              type="date"
              value={filtros.hasta ?? ''}
              onChange={(e) => setFiltro('hasta', e.target.value || null)}
            />
          </div>

          <div className="flex items-end gap-3 lg:col-span-2">
            <div className="flex items-center gap-2">
              <Switch
                id="solo-errores"
                checked={filtros.solo_con_errores}
                onCheckedChange={(v) => setFiltro('solo_con_errores', v)}
              />
              <Label htmlFor="solo-errores" className="cursor-pointer text-sm">
                Solo recibos con warnings
              </Label>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

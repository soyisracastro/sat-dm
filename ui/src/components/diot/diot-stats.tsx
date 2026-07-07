'use client';

import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';
import type { FilaDiot } from '@/lib/types';

const FMT = new Intl.NumberFormat('es-MX');
const sum = (filas: FilaDiot[], clave: string) =>
  filas.reduce((acc, f) => acc + Number(f[clave] ?? 0), 0);

interface TileProps {
  icon: string;
  label: string;
  value: string;
  tone?: 'green' | 'amber';
}

function Tile({ icon, label, value, tone }: TileProps) {
  return (
    <div className="rounded-lg border bg-card p-4">
      <div className="flex items-center justify-between text-xs text-muted-foreground">
        <span>{label}</span>
        <Icon icon={icon} className="size-4" />
      </div>
      <div
        className={cn(
          'mt-1 text-2xl font-semibold tabular-nums',
          tone === 'green' && 'text-emerald-600 dark:text-emerald-500',
          tone === 'amber' && 'text-amber-600 dark:text-amber-500',
        )}
      >
        {value}
      </div>
    </div>
  );
}

/** Tarjetas de resumen del periodo: proveedores y totales de IVA. */
export function DiotStats({ filas }: { filas: FilaDiot[] }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      <Tile icon="ph:buildings-light" label="Proveedores" value={FMT.format(filas.length)} />
      <Tile icon="ph:receipt-light" label="Valor de actos 16%" value={`$${FMT.format(sum(filas, 'valor_16'))}`} />
      <Tile
        icon="ph:percent-light"
        label="IVA acreditable"
        value={`$${FMT.format(sum(filas, 'acred_excl_16'))}`}
        tone="green"
      />
      <Tile
        icon="ph:percent-light"
        label="IVA retenido"
        value={`$${FMT.format(sum(filas, 'iva_retenido'))}`}
        tone="amber"
      />
    </div>
  );
}

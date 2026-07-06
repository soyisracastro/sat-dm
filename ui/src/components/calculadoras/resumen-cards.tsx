import { formatCurrency } from '@/lib/formatting';
import { cn } from '@/lib/utils';

export interface ResumenCardItem {
  etiqueta: string;
  /** number → moneda es-MX; string → se muestra tal cual (tasas, factores). */
  valor: number | string;
  tono?: 'default' | 'positivo' | 'negativo';
}

const TONO_CLASES: Record<NonNullable<ResumenCardItem['tono']>, string> = {
  default: '',
  positivo: 'text-emerald-600 dark:text-emerald-400',
  negativo: 'text-red-600 dark:text-red-400',
};

/** Fila de tarjetas de totales (bruto / ISR / neto, etc.). */
export function ResumenCards({
  items,
  className,
}: {
  items: ResumenCardItem[];
  className?: string;
}) {
  if (items.length === 0) return null;
  return (
    <div
      className={cn(
        'grid grid-cols-[repeat(auto-fit,minmax(10rem,1fr))] gap-3',
        className,
      )}
    >
      {items.map((item) => (
        <div key={item.etiqueta} className="rounded-xl border bg-card px-4 py-3 shadow-sm">
          <p className="text-xs text-muted-foreground">{item.etiqueta}</p>
          <p
            className={cn(
              'mt-1 text-lg font-bold tabular-nums',
              TONO_CLASES[item.tono ?? 'default'],
            )}
          >
            {typeof item.valor === 'number' ? formatCurrency(item.valor) : item.valor}
          </p>
        </div>
      ))}
    </div>
  );
}

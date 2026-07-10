import Link from 'next/link';

import { Badge } from '@/components/ui/badge';
import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';

export type KpiTono = 'azul' | 'verde' | 'ambar' | 'neutro';

const TONO_ICONO: Record<KpiTono, string> = {
  azul: 'bg-primary/10 text-primary',
  verde: 'bg-success/10 text-success',
  ambar: 'bg-warning/10 text-warning',
  neutro: 'bg-secondary text-muted-foreground',
};

export interface KpiTendencia {
  texto: string;
  tono: 'positiva' | 'neutra';
  icono?: string;
}

interface KpiTileProps {
  icono: string;
  tono: KpiTono;
  /** Valor grande. Un string permite "—" para métricas aún no disponibles. */
  valor: string;
  etiqueta: string;
  href?: string;
  tendencia?: KpiTendencia;
  /** Número en ámbar (p. ej. e.firmas por vencer > 0). */
  valorEnAlerta?: boolean;
  /** Sustituye a la tendencia (p. ej. "Próximamente"). */
  badge?: string;
}

/** Tile de KPI del Panel Ejecutivo. Con `href` navega; sin él es informativo. */
export function KpiTile({
  icono,
  tono,
  valor,
  etiqueta,
  href,
  tendencia,
  valorEnAlerta,
  badge,
}: KpiTileProps) {
  const contenido = (
    <>
      <div className="flex items-center justify-between">
        <span
          className={cn(
            'flex size-8 items-center justify-center rounded-lg',
            TONO_ICONO[tono],
          )}
        >
          <Icon icon={icono} className="size-[18px]" />
        </span>
        {href && (
          <Icon
            icon="ph:arrow-right-light"
            className="size-4 -translate-x-1 text-muted-foreground/60 opacity-0 transition group-hover:translate-x-0 group-hover:opacity-100"
          />
        )}
      </div>
      <div>
        <div
          className={cn(
            'text-[28px] font-extrabold leading-none tracking-tight tabular-nums',
            valorEnAlerta && 'text-warning',
          )}
        >
          {valor}
        </div>
        <div className="mt-1.5 text-xs leading-snug text-muted-foreground">
          {etiqueta}
        </div>
      </div>
      {badge ? (
        <Badge variant="secondary" className="text-[10px]">
          {badge}
        </Badge>
      ) : (
        tendencia && (
          <div
            className={cn(
              'flex items-center gap-1 text-[11px] font-semibold',
              tendencia.tono === 'positiva'
                ? 'text-success'
                : 'text-muted-foreground/70',
            )}
          >
            {tendencia.icono && (
              <Icon icon={tendencia.icono} className="size-3" />
            )}
            {tendencia.texto}
          </div>
        )
      )}
    </>
  );

  const clases =
    'flex min-h-[104px] flex-col gap-2 rounded-xl border bg-card p-4 text-left';

  if (!href) {
    return <div className={clases}>{contenido}</div>;
  }
  return (
    <Link
      href={href}
      className={cn(
        clases,
        'group transition hover:border-input hover:shadow-sm',
      )}
    >
      {contenido}
    </Link>
  );
}

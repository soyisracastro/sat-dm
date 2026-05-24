import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { ValidacionSummary } from '@/hooks/use-validacion';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ValidacionSummaryProps {
  summary: ValidacionSummary;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ValidacionSummaryBadges({ summary }: ValidacionSummaryProps) {
  return (
    <div className="flex flex-wrap gap-3">
      <Badge
        className={cn(
          'px-3 py-1 text-sm',
          'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400',
        )}
      >
        Vigentes: {summary.vigentes}
      </Badge>

      <Badge
        className={cn(
          'px-3 py-1 text-sm',
          'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400',
        )}
      >
        Cancelados: {summary.cancelados}
      </Badge>

      <Badge
        className={cn(
          'px-3 py-1 text-sm',
          'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400',
        )}
      >
        No Encontrados: {summary.noEncontrados}
      </Badge>

      {summary.errores > 0 && (
        <Badge
          className={cn(
            'px-3 py-1 text-sm',
            'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400',
          )}
        >
          Errores: {summary.errores}
        </Badge>
      )}
    </div>
  );
}

import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import type { ValidarResult } from '@/lib/types';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface ValidacionResultsProps {
  results: ValidarResult[];
  onExportCsv: () => void;
}

// ---------------------------------------------------------------------------
// Badge color by estado
// ---------------------------------------------------------------------------

function estadoBadgeClasses(estado: string, error: string | null): string {
  if (error) {
    return 'bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400';
  }

  const lower = (estado ?? '').toLowerCase();

  if (lower.includes('vigente')) {
    return 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400';
  }
  if (lower.includes('cancelado')) {
    return 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400';
  }
  if (lower.includes('no encontrado') || lower === '') {
    return 'bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-400';
  }

  return 'bg-muted text-muted-foreground';
}

function estadoLabel(estado: string, error: string | null): string {
  if (error) return 'Error';
  if (!estado) return 'No Encontrado';
  return estado;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function ValidacionResults({ results, onExportCsv }: ValidacionResultsProps) {
  if (results.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {results.length} resultado{results.length !== 1 ? 's' : ''}
        </p>
        <Button variant="outline" size="sm" onClick={onExportCsv}>
          Exportar CSV
        </Button>
      </div>

      <ScrollArea className="max-h-[500px] overflow-auto rounded-md border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>UUID</TableHead>
              <TableHead>Estado</TableHead>
              <TableHead>Es Cancelable</TableHead>
              <TableHead>Estatus Cancelacion</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {results.map((r) => (
              <TableRow key={r.uuid}>
                <TableCell className="font-mono text-xs">{r.uuid}</TableCell>
                <TableCell>
                  <Badge className={cn('text-xs', estadoBadgeClasses(r.estado, r.error))}>
                    {estadoLabel(r.estado, r.error)}
                  </Badge>
                </TableCell>
                <TableCell className="text-xs">
                  {r.es_cancelable ?? '-'}
                </TableCell>
                <TableCell className="text-xs">
                  {r.estatus_cancelacion ?? '-'}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </ScrollArea>
    </div>
  );
}

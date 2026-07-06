import { Badge } from '@/components/ui/badge';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatCurrency } from '@/lib/formatting';
import type { ComparacionMetodosAguinaldo } from '@/lib/types';

/**
 * Tabla chica Ley (Art. 96 LISR) vs Reglamento (Art. 174 RLISR) con el método
 * recomendado (menor ISR) resaltado.
 */
export function ComparacionMetodos({
  comparacion,
}: {
  comparacion: ComparacionMetodosAguinaldo;
}) {
  const filas = [
    {
      clave: 'ley' as const,
      metodo: 'Ley (Art. 96 LISR)',
      isr: comparacion.metodo_ley.isr_calculado,
      tasa: comparacion.metodo_ley.tasa_efectiva,
    },
    {
      clave: 'reglamento' as const,
      metodo: 'Reglamento (Art. 174 RLISR)',
      isr: comparacion.metodo_reglamento.isr_calculado,
      tasa: comparacion.metodo_reglamento.tasa_efectiva,
    },
  ];
  const diferencia = Math.abs(comparacion.diferencia);

  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <h2 className="text-sm font-bold">Comparación de métodos de ISR</h2>
      <Table className="mt-2">
        <TableHeader>
          <TableRow>
            <TableHead>Método</TableHead>
            <TableHead className="text-right">ISR</TableHead>
            <TableHead className="text-right">Tasa efectiva</TableHead>
            <TableHead />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filas.map((fila) => {
            const recomendado = comparacion.metodo_recomendado === fila.clave;
            return (
              <TableRow key={fila.clave} className={recomendado ? 'bg-muted/40' : undefined}>
                <TableCell className={recomendado ? 'font-medium' : undefined}>
                  {fila.metodo}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {formatCurrency(fila.isr)}
                </TableCell>
                <TableCell className="text-right tabular-nums">
                  {fila.tasa.toFixed(2)}%
                </TableCell>
                <TableCell className="text-right">
                  {recomendado && <Badge variant="secondary">Recomendado</Badge>}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
      {diferencia > 0 && (
        <p className="mt-2 text-xs text-muted-foreground">
          Ahorro con el método{' '}
          {comparacion.metodo_recomendado === 'reglamento' ? 'Reglamento' : 'Ley'}:{' '}
          <span className="font-medium tabular-nums">{formatCurrency(diferencia)}</span>
        </p>
      )}
    </div>
  );
}

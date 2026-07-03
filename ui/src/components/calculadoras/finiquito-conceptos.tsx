import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatCurrency } from '@/lib/formatting';
import type {
  AguinaldoProporcional,
  PrimaVacacionalProporcional,
  SalarioDevengado,
  VacacionesProporcionales,
} from '@/lib/types';

interface FiniquitoConceptosTablaProps {
  titulo?: string;
  salarioDevengado: SalarioDevengado;
  aguinaldo: AguinaldoProporcional;
  vacaciones: VacacionesProporcionales;
  prima: PrimaVacacionalProporcional;
  subtotal: number;
  totalExento: number;
  totalGravado: number;
}

/**
 * Tabla de conceptos del finiquito (devengado / aguinaldo / vacaciones /
 * prima vacacional) con su parte exenta y gravada. La comparten las páginas
 * de finiquito y de liquidación.
 */
export function FiniquitoConceptosTabla({
  titulo = 'Conceptos del finiquito',
  salarioDevengado,
  aguinaldo,
  vacaciones,
  prima,
  subtotal,
  totalExento,
  totalGravado,
}: FiniquitoConceptosTablaProps) {
  return (
    <div className="rounded-xl border bg-card p-4 shadow-sm">
      <h2 className="text-sm font-bold">{titulo}</h2>
      <Table className="mt-2">
        <TableHeader>
          <TableRow>
            <TableHead>Concepto</TableHead>
            <TableHead className="text-right">Monto</TableHead>
            <TableHead className="text-right">Exento</TableHead>
            <TableHead className="text-right">Gravado</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          <TableRow>
            <TableCell>Salario devengado ({salarioDevengado.dias} días)</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(salarioDevengado.monto)}
            </TableCell>
            <TableCell className="text-right tabular-nums">{formatCurrency(0)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(salarioDevengado.monto)}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>
              Aguinaldo proporcional ({aguinaldo.dias_correspondientes.toFixed(2)} días)
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(aguinaldo.monto)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(aguinaldo.exento)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(aguinaldo.gravado)}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>
              Vacaciones proporcionales ({vacaciones.dias_correspondientes.toFixed(2)} de{' '}
              {vacaciones.dias_vacaciones_anuales} días)
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(vacaciones.monto)}
            </TableCell>
            <TableCell className="text-right tabular-nums">{formatCurrency(0)}</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(vacaciones.monto)}
            </TableCell>
          </TableRow>
          <TableRow>
            <TableCell>
              Prima vacacional ({(prima.porcentaje * 100).toFixed(0)}%)
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(prima.monto)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(prima.exento)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(prima.gravado)}
            </TableCell>
          </TableRow>
        </TableBody>
        <TableFooter>
          <TableRow>
            <TableCell>Subtotal</TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(subtotal)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(totalExento)}
            </TableCell>
            <TableCell className="text-right tabular-nums">
              {formatCurrency(totalGravado)}
            </TableCell>
          </TableRow>
        </TableFooter>
      </Table>
    </div>
  );
}

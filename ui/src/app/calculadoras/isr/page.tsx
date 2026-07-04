'use client';

import { Advertencias } from '@/components/calculadoras/advertencias';
import {
  CalculadoraShell,
  SinResultado,
} from '@/components/calculadoras/calculadora-shell';
import { ExportButtons } from '@/components/calculadoras/export-buttons';
import { MonedaInput } from '@/components/calculadoras/moneda-input';
import { ResumenCards } from '@/components/calculadoras/resumen-cards';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Switch } from '@/components/ui/switch';
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from '@/components/ui/table';
import { useCalculadora } from '@/hooks/use-calculadora';
import { formatCurrency } from '@/lib/formatting';
import type { CalculadoraInputs, PeriodicidadIsr } from '@/lib/types';

type Inputs = CalculadoraInputs<'isr'>;

const DEFAULTS: Inputs = {
  ingreso_gravado: 0,
  periodicidad: 'mensual',
  es_asimilado: false,
  mes: 2,
  anio: 2026,
};

const PERIODICIDADES: { valor: PeriodicidadIsr; label: string }[] = [
  { valor: 'diario', label: 'Diario' },
  { valor: 'semanal', label: 'Semanal' },
  { valor: 'decenal', label: 'Decenal' },
  { valor: 'quincenal', label: 'Quincenal' },
  { valor: 'mensual', label: 'Mensual' },
];

function esValido(inputs: Inputs): boolean {
  return inputs.ingreso_gravado > 0 && inputs.mes >= 1 && inputs.mes <= 12;
}

export default function IsrPage() {
  const calc = useCalculadora({ nombre: 'isr', defaults: DEFAULTS, esValido });
  const { inputs, setInput, resultado } = calc;
  const desglose = resultado?.desglose;

  return (
    <CalculadoraShell
      titulo="ISR de sueldos"
      descripcion="Retención de ISR del período (Art. 96 LISR) con subsidio para el empleo. Los asimilados a salarios no reciben subsidio."
      calculando={calc.calculando}
      acciones={
        <ExportButtons
          calculadora="isr"
          inputs={calc.inputs as unknown as Record<string, unknown>}
          habilitado={calc.resultado !== null}
        />
      }
      formulario={
        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="ingreso">Ingreso gravado del período</Label>
            <MonedaInput
              id="ingreso"
              value={inputs.ingreso_gravado > 0 ? inputs.ingreso_gravado : null}
              onChange={(v) => setInput('ingreso_gravado', v ?? 0)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Periodicidad</Label>
              <Select
                value={inputs.periodicidad}
                onValueChange={(v) => setInput('periodicidad', v as PeriodicidadIsr)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PERIODICIDADES.map((p) => (
                    <SelectItem key={p.valor} value={p.valor}>
                      {p.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Mes del pago</Label>
              <Select
                value={inputs.mes === 1 ? '1' : '2'}
                onValueChange={(v) => setInput('mes', parseInt(v, 10))}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="1">Enero</SelectItem>
                  <SelectItem value="2">Febrero a diciembre</SelectItem>
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                En enero el subsidio para el empleo es mayor.
              </p>
            </div>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2.5">
            <div className="space-y-0.5">
              <Label htmlFor="asimilado">Asimilado a salarios</Label>
              <p className="text-xs text-muted-foreground">
                Sin subsidio para el empleo (honorarios asimilados).
              </p>
            </div>
            <Switch
              id="asimilado"
              checked={inputs.es_asimilado}
              onCheckedChange={(v) => setInput('es_asimilado', v)}
            />
          </div>
        </div>
      }
      resultados={
        !resultado || !desglose ? (
          <SinResultado restaurando={calc.restaurando} />
        ) : (
          <>
            <Advertencias advertencias={calc.advertencias} />
            <ResumenCards
              items={[
                { etiqueta: 'ISR antes de subsidio', valor: resultado.isr_bruto },
                { etiqueta: 'Subsidio aplicado', valor: resultado.subsidio_aplicado },
                { etiqueta: 'ISR final', valor: resultado.isr_final, tono: 'negativo' },
                {
                  etiqueta: 'Ingreso neto',
                  valor: resultado.ingreso_neto,
                  tono: 'positivo',
                },
                {
                  etiqueta: 'Tasa efectiva',
                  valor: `${resultado.tasa_efectiva.toFixed(2)}%`,
                },
              ]}
            />
            <div className="rounded-xl border bg-card p-4 shadow-sm">
              <h2 className="text-sm font-bold">Desglose del tramo</h2>
              <Table className="mt-2">
                <TableBody>
                  <TableRow>
                    <TableCell>Límite inferior</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(desglose.limite_inferior)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Excedente del límite inferior</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(desglose.excedente_limite_inferior)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Tasa sobre el excedente</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {(desglose.tasa_marginal * 100).toFixed(2)}%
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Impuesto marginal</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(desglose.impuesto_marginal)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Cuota fija</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(desglose.cuota_fija)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>ISR antes de subsidio</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(desglose.isr_antes_subsidio)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Subsidio para el empleo</TableCell>
                    <TableCell className="text-right tabular-nums">
                      −{formatCurrency(desglose.subsidio)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell className="font-medium">ISR final</TableCell>
                    <TableCell className="text-right font-bold tabular-nums">
                      {formatCurrency(desglose.isr_final)}
                    </TableCell>
                  </TableRow>
                </TableBody>
              </Table>
              <p className="mt-2 text-xs text-muted-foreground">
                Tramo de la tarifa: {formatCurrency(desglose.rango_tarifa.limite_inferior)}
                {' – '}
                {desglose.rango_tarifa.limite_superior != null
                  ? formatCurrency(desglose.rango_tarifa.limite_superior)
                  : 'en adelante'}
                {' · '}
                {(desglose.rango_tarifa.porcentaje_sobre_excedente * 100).toFixed(2)}% sobre
                el excedente
              </p>
            </div>
          </>
        )
      }
    />
  );
}

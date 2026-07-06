'use client';

import { Advertencias } from '@/components/calculadoras/advertencias';
import {
  CalculadoraShell,
  SinResultado,
} from '@/components/calculadoras/calculadora-shell';
import { ExportButtons } from '@/components/calculadoras/export-buttons';
import { MonedaInput } from '@/components/calculadoras/moneda-input';
import { ResumenCards } from '@/components/calculadoras/resumen-cards';
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
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { useCalculadora, useIndicadores } from '@/hooks/use-calculadora';
import { formatCurrency } from '@/lib/formatting';
import type { CalculadoraInputs, TipoSalario } from '@/lib/types';

type Inputs = CalculadoraInputs<'sbc'>;

const DEFAULTS: Inputs = {
  salario: 0,
  tipo_salario: 'mensual',
  antiguedad_anios: 1,
  dias_aguinaldo: 15,
  prima_vacacional: 0.25,
  es_zona_fronteriza: false,
  anio: 2026,
};

export default function SbcPage() {
  const indicadores = useIndicadores(2026);

  // Umbral de salario mínimo en la unidad del input (esta calculadora
  // convierte mensual→diario con /30; el umbral mensual usa el mismo factor).
  // Un salario por debajo del mínimo no es base válida para cotizar (Art. 90 LFT).
  function umbralMinimo(inputs: Inputs): number | null {
    if (!indicadores) return null;
    const smgDiario = inputs.es_zona_fronteriza
      ? indicadores.smg_frontera
      : indicadores.smg_general;
    return inputs.tipo_salario === 'mensual' ? smgDiario * 30 : smgDiario;
  }

  function esValido(inputs: Inputs): boolean {
    if (
      inputs.salario <= 0 ||
      inputs.antiguedad_anios < 0 ||
      inputs.dias_aguinaldo < 15 ||
      inputs.prima_vacacional < 0.25 ||
      inputs.prima_vacacional > 1
    ) {
      return false;
    }
    const umbral = umbralMinimo(inputs);
    return umbral === null || inputs.salario >= umbral;
  }

  const calc = useCalculadora({ nombre: 'sbc', defaults: DEFAULTS, esValido });
  const { inputs, setInput, resultado } = calc;

  const primaPct = Number((inputs.prima_vacacional * 100).toFixed(2));
  const umbral = umbralMinimo(inputs);
  const debajoDelMinimo =
    umbral !== null && inputs.salario > 0 && inputs.salario < umbral;

  return (
    <CalculadoraShell
      titulo="Salario Base de Cotización"
      descripcion="Factor de integración con prestaciones mínimas de ley (o superiores) y SBC diario y mensual para cotizar en el IMSS."
      calculando={calc.calculando}
      acciones={
        <ExportButtons
          calculadora="sbc"
          inputs={calc.inputs as unknown as Record<string, unknown>}
          habilitado={calc.resultado !== null}
        />
      }
      formulario={
        <div className="space-y-4">
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="salario">Salario</Label>
              <MonedaInput
                id="salario"
                value={inputs.salario > 0 ? inputs.salario : null}
                onChange={(v) => setInput('salario', v ?? 0)}
              />
            </div>
            <div className="space-y-2">
              <Label>Tipo de salario</Label>
              <Select
                value={inputs.tipo_salario}
                onValueChange={(v) => setInput('tipo_salario', v as TipoSalario)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="mensual">Mensual</SelectItem>
                  <SelectItem value="diario">Diario</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          {debajoDelMinimo && (
            <p className="text-xs font-medium text-destructive">
              El salario es menor al mínimo{' '}
              {inputs.es_zona_fronteriza ? 'de la frontera norte' : 'general'}{' '}
              {inputs.tipo_salario === 'mensual' ? 'mensual' : 'diario'} (
              {formatCurrency(umbral)}). Pagar por debajo del mínimo es ilegal
              (Art. 90 LFT); no es base válida para determinar el SBC.
            </p>
          )}

          <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2.5">
            <div className="space-y-0.5">
              <Label htmlFor="zlfn">Zona Libre de la Frontera Norte</Label>
              <p className="text-xs text-muted-foreground">
                El salario mínimo de la ZLFN es mayor al del resto del país.
              </p>
            </div>
            <Switch
              id="zlfn"
              checked={inputs.es_zona_fronteriza}
              onCheckedChange={(v) => setInput('es_zona_fronteriza', v)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="antiguedad">Antigüedad (años cumplidos)</Label>
            <Input
              id="antiguedad"
              type="number"
              min={0}
              value={Number.isFinite(inputs.antiguedad_anios) ? inputs.antiguedad_anios : ''}
              onChange={(e) => setInput('antiguedad_anios', parseInt(e.target.value, 10) || 0)}
            />
            <p className="text-xs text-muted-foreground">
              Determina los días de vacaciones que integran el SBC.
            </p>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="dias-aguinaldo">Días de aguinaldo</Label>
              <Input
                id="dias-aguinaldo"
                type="number"
                min={15}
                value={inputs.dias_aguinaldo || ''}
                onChange={(e) =>
                  setInput('dias_aguinaldo', parseInt(e.target.value, 10) || 0)
                }
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="prima-vacacional">Prima vacacional (%)</Label>
              <Input
                id="prima-vacacional"
                type="number"
                min={25}
                max={100}
                step={1}
                value={primaPct || ''}
                onChange={(e) => {
                  const pct = Number(e.target.value);
                  setInput(
                    'prima_vacacional',
                    Number.isFinite(pct) ? Number((pct / 100).toFixed(4)) : 0,
                  );
                }}
              />
              <p className="text-xs text-muted-foreground">Mínimo de ley: 25%.</p>
            </div>
          </div>
        </div>
      }
      resultados={
        !resultado ? (
          <SinResultado restaurando={calc.restaurando} />
        ) : (
          <>
            <Advertencias advertencias={calc.advertencias} />
            {resultado.excede_tope && (
              <Advertencias
                advertencias={[
                  `El SBC calculado excede el tope de 25 UMA (${formatCurrency(resultado.tope_sbc)} diarios); se cotiza al tope.`,
                ]}
              />
            )}
            <ResumenCards
              items={[
                {
                  etiqueta: 'Factor de integración',
                  valor: resultado.factor_integracion.toFixed(4),
                },
                { etiqueta: 'SBC diario', valor: resultado.sbc_diario, tono: 'positivo' },
                { etiqueta: 'SBC mensual', valor: resultado.sbc_mensual },
              ]}
            />
            <div className="rounded-xl border bg-card p-4 shadow-sm">
              <h2 className="text-sm font-bold">Integración diaria</h2>
              <Table className="mt-2">
                <TableHeader>
                  <TableRow>
                    <TableHead>Concepto</TableHead>
                    <TableHead className="text-right">Base</TableHead>
                    <TableHead className="text-right">Integración diaria</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell>Salario diario</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {resultado.desglose.salario_base.dias} días
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.desglose.salario_base.integracion_diaria)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Aguinaldo</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {resultado.desglose.aguinaldo.dias} días
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.desglose.aguinaldo.integracion_diaria)}
                    </TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>Prima vacacional</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {resultado.desglose.prima_vacacional.dias_vacaciones} días ·{' '}
                      {resultado.desglose.prima_vacacional.porcentaje.toFixed(0)}%
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(
                        resultado.desglose.prima_vacacional.integracion_diaria,
                      )}
                    </TableCell>
                  </TableRow>
                </TableBody>
                <TableFooter>
                  <TableRow>
                    <TableCell colSpan={2}>Total integrado</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.desglose.total_integrado)}
                    </TableCell>
                  </TableRow>
                </TableFooter>
              </Table>
            </div>
          </>
        )
      }
    />
  );
}

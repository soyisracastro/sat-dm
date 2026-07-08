'use client';

import { Advertencias } from '@/components/calculadoras/advertencias';
import {
  CalculadoraShell,
  SinResultado,
} from '@/components/calculadoras/calculadora-shell';
import { ExportButtons } from '@/components/calculadoras/export-buttons';
import { FiniquitoConceptosTabla } from '@/components/calculadoras/finiquito-conceptos';
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
import { useCalculadora } from '@/hooks/use-calculadora';
import type { CalculadoraInputs, TipoSalario } from '@/lib/types';

type Inputs = CalculadoraInputs<'finiquito'>;

const DEFAULTS: Inputs = {
  salario: 0,
  tipo_salario: 'mensual',
  fecha_ingreso: '',
  fecha_baja: '',
  dias_aguinaldo: 15,
  prima_vacacional: 0.25,
  anio: 2026,
};

function esValido(inputs: Inputs): boolean {
  return (
    inputs.salario > 0 &&
    !!inputs.fecha_ingreso &&
    !!inputs.fecha_baja &&
    inputs.fecha_baja > inputs.fecha_ingreso &&
    inputs.dias_aguinaldo >= 15 &&
    inputs.prima_vacacional >= 0.25 &&
    inputs.prima_vacacional <= 1
  );
}

export default function FiniquitoPage() {
  const calc = useCalculadora({ nombre: 'finiquito', defaults: DEFAULTS, esValido });
  const { inputs, setInput, resultado } = calc;

  const primaPct = Number((inputs.prima_vacacional * 100).toFixed(2));

  return (
    <CalculadoraShell
      titulo="Finiquito"
      descripcion="Partes proporcionales al terminar la relación laboral: salario devengado, aguinaldo, vacaciones y prima vacacional, con su ISR."
      calculando={calc.calculando}
      acciones={
        <ExportButtons
          calculadora="finiquito"
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

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="fecha-ingreso">Fecha de ingreso</Label>
              <Input
                id="fecha-ingreso"
                type="date"
                value={inputs.fecha_ingreso}
                onChange={(e) => setInput('fecha_ingreso', e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="fecha-baja">Fecha de baja</Label>
              <Input
                id="fecha-baja"
                type="date"
                value={inputs.fecha_baja}
                onChange={(e) => setInput('fecha_baja', e.target.value)}
              />
            </div>
          </div>
          {inputs.fecha_ingreso &&
            inputs.fecha_baja &&
            inputs.fecha_baja <= inputs.fecha_ingreso && (
              <p className="text-xs text-red-600 dark:text-red-400">
                La fecha de baja debe ser posterior a la de ingreso.
              </p>
            )}

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
            </div>
          </div>
        </div>
      }
      resultados={
        !resultado ? (
          <SinResultado restaurando={calc.restaurando} icono="ph:receipt-light" />
        ) : (
          <>
            <Advertencias advertencias={calc.advertencias} />
            <p className="text-sm text-muted-foreground">
              Antigüedad: <span className="font-medium text-foreground">{resultado.antiguedad.texto}</span>
            </p>
            <ResumenCards
              items={[
                { etiqueta: 'Total bruto', valor: resultado.subtotal_bruto },
                { etiqueta: 'ISR retenido', valor: resultado.total_isr, tono: 'negativo' },
                { etiqueta: 'Neto a pagar', valor: resultado.total_neto, tono: 'positivo' },
              ]}
            />
            <FiniquitoConceptosTabla
              salarioDevengado={resultado.salario_devengado}
              aguinaldo={resultado.aguinaldo_proporcional}
              vacaciones={resultado.vacaciones_proporcionales}
              prima={resultado.prima_vacacional}
              subtotal={resultado.subtotal_bruto}
              totalExento={resultado.fiscal.total_exento}
              totalGravado={resultado.fiscal.total_gravado}
            />
          </>
        )
      }
    />
  );
}

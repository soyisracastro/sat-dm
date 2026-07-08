'use client';

import { Advertencias } from '@/components/calculadoras/advertencias';
import {
  CalculadoraShell,
  SinResultado,
} from '@/components/calculadoras/calculadora-shell';
import { ExportButtons } from '@/components/calculadoras/export-buttons';
import { ComparacionMetodos } from '@/components/calculadoras/comparacion-metodos';
import { DesglosePasos } from '@/components/calculadoras/desglose-pasos';
import { MonedaInput } from '@/components/calculadoras/moneda-input';
import { ResumenCards } from '@/components/calculadoras/resumen-cards';
import { ToggleRow } from '@/components/calculadoras/toggle-row';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { useCalculadora, useIndicadores } from '@/hooks/use-calculadora';
import { formatCurrency } from '@/lib/formatting';
import type { CalculadoraInputs, MetodoIsrAguinaldo, TipoSalario } from '@/lib/types';

type Inputs = CalculadoraInputs<'aguinaldo'>;

const DEFAULTS: Inputs = {
  salario: 0,
  tipo_salario: 'mensual',
  fecha_ingreso: '2026-01-01',
  dias_aguinaldo: 15,
  fecha_calculo: '2026-12-20',
  ingreso_ordinario_mensual: null,
  metodo_isr: 'ley',
  es_zona_fronteriza: false,
  anio: 2026,
};

export default function AguinaldoPage() {
  const indicadores = useIndicadores(2026);

  // Umbral de salario mínimo en la unidad del input (esta calculadora
  // convierte mensual→diario con /30.4). El aguinaldo se paga a un trabajador
  // activo: su salario vigente no puede estar por debajo del mínimo (Art. 90 LFT).
  function umbralMinimo(inputs: Inputs): number | null {
    if (!indicadores) return null;
    const smgDiario = inputs.es_zona_fronteriza
      ? indicadores.smg_frontera
      : indicadores.smg_general;
    return inputs.tipo_salario === 'mensual' ? smgDiario * 30.4 : smgDiario;
  }

  function esValido(inputs: Inputs): boolean {
    if (inputs.salario <= 0) return false;
    if (!inputs.fecha_ingreso) return false;
    if (inputs.dias_aguinaldo < 1) return false;
    // Con fecha de cálculo capturada, el ingreso debe ser anterior.
    if (inputs.fecha_calculo && inputs.fecha_ingreso > inputs.fecha_calculo) return false;
    const umbral = umbralMinimo(inputs);
    return umbral === null || inputs.salario >= umbral;
  }

  const calc = useCalculadora({ nombre: 'aguinaldo', defaults: DEFAULTS, esValido });
  const { inputs, setInput, resultado } = calc;

  const umbral = umbralMinimo(inputs);
  const debajoDelMinimo =
    umbral !== null && inputs.salario > 0 && inputs.salario < umbral;

  return (
    <CalculadoraShell
      titulo="Aguinaldo"
      descripcion="Aguinaldo proporcional del ejercicio 2026 con la parte exenta (30 UMA) y el ISR por Ley (Art. 96) o por Reglamento (Art. 174)."
      calculando={calc.calculando}
      acciones={
        <ExportButtons
          calculadora="aguinaldo"
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
              (Art. 90 LFT); no es base válida para calcular el aguinaldo.
            </p>
          )}

          <ToggleRow
            titulo="Zona Libre de la Frontera Norte"
            descripcion="El salario mínimo de la ZLFN es mayor al del resto del país."
            activo={inputs.es_zona_fronteriza}
            onCambiar={(v) => setInput('es_zona_fronteriza', v)}
          />

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
              <Label htmlFor="fecha-calculo">Fecha de cálculo</Label>
              <Input
                id="fecha-calculo"
                type="date"
                value={inputs.fecha_calculo ?? ''}
                onChange={(e) => setInput('fecha_calculo', e.target.value || null)}
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="dias-aguinaldo">Días de aguinaldo</Label>
              <Input
                id="dias-aguinaldo"
                type="number"
                min={1}
                value={inputs.dias_aguinaldo || ''}
                onChange={(e) =>
                  setInput('dias_aguinaldo', parseInt(e.target.value, 10) || 0)
                }
              />
              <p className="text-xs text-muted-foreground">Mínimo de ley: 15 días.</p>
            </div>
            <div className="space-y-2">
              <Label htmlFor="ingreso-ordinario">Ingreso ordinario mensual</Label>
              <MonedaInput
                id="ingreso-ordinario"
                value={inputs.ingreso_ordinario_mensual ?? null}
                onChange={(v) => setInput('ingreso_ordinario_mensual', v)}
                placeholder="Opcional"
              />
              <p className="text-xs text-muted-foreground">
                Sueldo mensual habitual; afina la retención de ISR del aguinaldo.
              </p>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Método de ISR</Label>
            <Select
              value={inputs.metodo_isr}
              onValueChange={(v) => setInput('metodo_isr', v as MetodoIsrAguinaldo)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="ley">Ley (Art. 96 LISR)</SelectItem>
                <SelectItem value="reglamento">Reglamento (Art. 174 RLISR)</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </div>
      }
      resultados={
        !resultado ? (
          <SinResultado restaurando={calc.restaurando} icono="ph:gift-light" />
        ) : (
          <>
            <Advertencias advertencias={calc.advertencias} />
            <ResumenCards
              items={[
                { etiqueta: 'Aguinaldo bruto', valor: resultado.aguinaldo_bruto },
                { etiqueta: 'Parte exenta', valor: resultado.parte_exenta },
                { etiqueta: 'Parte gravada', valor: resultado.parte_gravada },
                {
                  etiqueta: 'ISR retenido',
                  valor: resultado.isr_retenido,
                  tono: 'negativo',
                },
                {
                  etiqueta: 'Aguinaldo neto',
                  valor: resultado.aguinaldo_neto,
                  tono: 'positivo',
                },
              ]}
            />
            <p className="text-xs text-muted-foreground">
              {resultado.dias_trabajados} días trabajados · tasa efectiva de ISR{' '}
              {resultado.tasa_efectiva_isr.toFixed(2)}%
            </p>
            {resultado.comparacion_metodos && (
              <ComparacionMetodos comparacion={resultado.comparacion_metodos} />
            )}
            <DesglosePasos pasos={resultado.desglose?.pasos ?? []} />
          </>
        )
      }
    />
  );
}

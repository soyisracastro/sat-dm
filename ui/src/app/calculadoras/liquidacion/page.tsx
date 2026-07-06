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
import type { CalculadoraInputs, TipoSalario, TipoTerminacion } from '@/lib/types';

type Inputs = CalculadoraInputs<'liquidacion'>;

const DEFAULTS: Inputs = {
  salario: 0,
  tipo_salario: 'mensual',
  fecha_ingreso: '',
  fecha_baja: '',
  dias_aguinaldo: 15,
  prima_vacacional: 0.25,
  tipo_terminacion: 'DESPIDO_INJUSTIFICADO',
  es_zona_fronteriza: false,
  ultimo_sueldo_mensual: null,
  anio: 2026,
};

const TIPOS_ORDEN: TipoTerminacion[] = [
  'DESPIDO_INJUSTIFICADO',
  'RESCISION_ART51',
  'TERMINACION_COLECTIVA',
  'RENUNCIA_VOLUNTARIA',
];

// Fallback mientras cargan los indicadores del agente.
const LABELS_FALLBACK: Record<TipoTerminacion, string> = {
  DESPIDO_INJUSTIFICADO: 'Despido injustificado',
  RESCISION_ART51: 'Rescisión por el trabajador (Art. 51)',
  TERMINACION_COLECTIVA: 'Terminación colectiva',
  RENUNCIA_VOLUNTARIA: 'Renuncia voluntaria',
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

export default function LiquidacionPage() {
  const calc = useCalculadora({ nombre: 'liquidacion', defaults: DEFAULTS, esValido });
  const { inputs, setInput, resultado } = calc;
  const indicadores = useIndicadores(inputs.anio);

  const primaPct = Number((inputs.prima_vacacional * 100).toFixed(2));
  const tipoInfo = indicadores?.tipos_terminacion?.[inputs.tipo_terminacion];
  const indemnizacion = resultado?.indemnizacion ?? null;
  const fiscalIndemnizacion = resultado?.fiscal?.indemnizacion;

  return (
    <CalculadoraShell
      titulo="Liquidación"
      descripcion="Finiquito más indemnizaciones (tres meses, veinte días por año y prima de antigüedad) según el tipo de terminación, con la exención de 90 UMA por año y el ISR por tasa efectiva."
      calculando={calc.calculando}
      acciones={
        <ExportButtons
          calculadora="liquidacion"
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

          <div className="space-y-2">
            <Label>Tipo de terminación</Label>
            <Select
              value={inputs.tipo_terminacion}
              onValueChange={(v) => setInput('tipo_terminacion', v as TipoTerminacion)}
            >
              <SelectTrigger className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIPOS_ORDEN.map((tipo) => (
                  <SelectItem key={tipo} value={tipo}>
                    {indicadores?.tipos_terminacion?.[tipo]?.label ?? LABELS_FALLBACK[tipo]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {tipoInfo && (
              <p className="text-xs text-muted-foreground">
                {tipoInfo.descripcion} ({tipoInfo.fundamento_legal})
              </p>
            )}
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
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="ultimo-sueldo">Último sueldo mensual ordinario</Label>
            <MonedaInput
              id="ultimo-sueldo"
              value={inputs.ultimo_sueldo_mensual ?? null}
              onChange={(v) => setInput('ultimo_sueldo_mensual', v)}
              placeholder="Opcional"
            />
            <p className="text-xs text-muted-foreground">
              Base de la tasa efectiva de ISR de la indemnización; si se omite se usa el
              salario mensual.
            </p>
          </div>

          <div className="flex items-center justify-between gap-4 rounded-lg border px-3 py-2.5">
            <div className="space-y-0.5">
              <Label htmlFor="zona-fronteriza">Zona libre de la frontera norte</Label>
              <p className="text-xs text-muted-foreground">
                Usa el salario mínimo fronterizo para el tope de la prima de antigüedad.
              </p>
            </div>
            <Switch
              id="zona-fronteriza"
              checked={inputs.es_zona_fronteriza}
              onCheckedChange={(v) => setInput('es_zona_fronteriza', v)}
            />
          </div>
        </div>
      }
      resultados={
        !resultado ? (
          <SinResultado restaurando={calc.restaurando} />
        ) : (
          <>
            <Advertencias advertencias={calc.advertencias} />
            <p className="text-sm text-muted-foreground">
              Antigüedad:{' '}
              <span className="font-medium text-foreground">
                {resultado.antiguedad.texto}
              </span>
              {' · '}Salario diario integrado:{' '}
              <span className="font-medium tabular-nums text-foreground">
                {formatCurrency(resultado.salario_diario_integrado)}
              </span>{' '}
              (factor {resultado.factor_integracion.toFixed(4)})
            </p>
            <ResumenCards
              items={[
                { etiqueta: 'Total bruto', valor: resultado.total_bruto },
                { etiqueta: 'ISR total', valor: resultado.total_isr, tono: 'negativo' },
                { etiqueta: 'Neto a pagar', valor: resultado.total_neto, tono: 'positivo' },
              ]}
            />

            <FiniquitoConceptosTabla
              salarioDevengado={resultado.finiquito.salario_devengado}
              aguinaldo={resultado.finiquito.aguinaldo_proporcional}
              vacaciones={resultado.finiquito.vacaciones_proporcionales}
              prima={resultado.finiquito.prima_vacacional}
              subtotal={resultado.finiquito.subtotal}
              totalExento={resultado.finiquito.total_exento}
              totalGravado={resultado.finiquito.total_gravado}
            />

            {indemnizacion && (
              <div className="rounded-xl border bg-card p-4 shadow-sm">
                <h2 className="text-sm font-bold">Indemnización</h2>
                <Table className="mt-2">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Concepto</TableHead>
                      <TableHead className="text-right">Monto</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    <TableRow>
                      <TableCell>
                        Tres meses constitucionales
                        <span className="block text-xs text-muted-foreground">
                          {indemnizacion.tres_meses_constitucional.aplica
                            ? indemnizacion.tres_meses_constitucional.fundamento_legal
                            : 'No aplica para este tipo de terminación'}
                        </span>
                      </TableCell>
                      <TableCell className="text-right align-top tabular-nums">
                        {formatCurrency(indemnizacion.tres_meses_constitucional.monto)}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        Veinte días por año ({indemnizacion.veinte_dias_por_anio.anios_completos}{' '}
                        años)
                        <span className="block text-xs text-muted-foreground">
                          {indemnizacion.veinte_dias_por_anio.aplica
                            ? indemnizacion.veinte_dias_por_anio.fundamento_legal
                            : indemnizacion.veinte_dias_por_anio.razon_no_aplica}
                        </span>
                      </TableCell>
                      <TableCell className="text-right align-top tabular-nums">
                        {formatCurrency(indemnizacion.veinte_dias_por_anio.monto)}
                      </TableCell>
                    </TableRow>
                    <TableRow>
                      <TableCell>
                        Prima de antigüedad ({indemnizacion.prima_antiguedad.anios_servicio}{' '}
                        años × {indemnizacion.prima_antiguedad.dias_por_anio} días)
                        <span className="block text-xs text-muted-foreground">
                          {indemnizacion.prima_antiguedad.aplica
                            ? `${indemnizacion.prima_antiguedad.fundamento_legal} · salario topado a ${formatCurrency(indemnizacion.prima_antiguedad.salario_aplicable)}`
                            : indemnizacion.prima_antiguedad.razon_no_aplica}
                        </span>
                      </TableCell>
                      <TableCell className="text-right align-top tabular-nums">
                        {formatCurrency(indemnizacion.prima_antiguedad.monto)}
                      </TableCell>
                    </TableRow>
                  </TableBody>
                  <TableFooter>
                    <TableRow>
                      <TableCell>Subtotal indemnización</TableCell>
                      <TableCell className="text-right tabular-nums">
                        {formatCurrency(indemnizacion.subtotal)}
                      </TableCell>
                    </TableRow>
                  </TableFooter>
                </Table>
                <div className="mt-3 space-y-1 text-xs text-muted-foreground">
                  <p>
                    Exención (90 UMA por año de servicio):{' '}
                    <span className="tabular-nums">
                      {formatCurrency(indemnizacion.exencion)}
                    </span>
                    {' · '}Exento:{' '}
                    <span className="tabular-nums">{formatCurrency(indemnizacion.exento)}</span>
                    {' · '}Gravado:{' '}
                    <span className="tabular-nums">
                      {formatCurrency(indemnizacion.gravado)}
                    </span>
                  </p>
                  {fiscalIndemnizacion && (
                    <p>
                      ISR de la indemnización:{' '}
                      <span className="tabular-nums">
                        {formatCurrency(fiscalIndemnizacion.isr)}
                      </span>{' '}
                      {fiscalIndemnizacion.usa_tasa_efectiva
                        ? `con tasa efectiva de ${fiscalIndemnizacion.tasa_efectiva.toFixed(2)}% del último sueldo mensual (Art. 96 LISR, quinto párrafo)`
                        : 'con tarifa directa (la indemnización no excede el último sueldo mensual)'}
                    </p>
                  )}
                </div>
              </div>
            )}
          </>
        )
      }
    />
  );
}

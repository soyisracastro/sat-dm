'use client';

import { Advertencias } from '@/components/calculadoras/advertencias';
import {
  CalculadoraShell,
  SinResultado,
} from '@/components/calculadoras/calculadora-shell';
import { ExportButtons } from '@/components/calculadoras/export-buttons';
import { MonedaInput } from '@/components/calculadoras/moneda-input';
import { ResumenCards } from '@/components/calculadoras/resumen-cards';
import { ToggleRow } from '@/components/calculadoras/toggle-row';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
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
import type {
  CalculadoraInputs,
  ClaseRiesgo,
  PrestacionAdicional,
  TipoSalario,
} from '@/lib/types';

type Inputs = CalculadoraInputs<'carga-patronal'>;

const DEFAULTS: Inputs = {
  salario: 0,
  tipo_salario: 'mensual',
  antiguedad_anios: 1,
  es_zona_fronteriza: false,
  clase_riesgo: 'I',
  prima_riesgo_trabajo: null,
  codigo_estado: 'CDMX',
  tasa_impuesto_estatal: null,
  incluir_aguinaldo_mensual: true,
  incluir_vacaciones_mensual: true,
  prestaciones_adicionales: [],
  anio: 2026,
};

const CLASES_RIESGO: ClaseRiesgo[] = ['I', 'II', 'III', 'IV', 'V'];

export default function CargaPatronalPage() {
  const indicadores = useIndicadores(2026);

  // Umbral de salario mínimo en la unidad del input (esta calculadora
  // convierte mensual→diario con /30). Un salario por debajo del mínimo no es
  // un costo laboral válido (Art. 90 LFT).
  function umbralMinimo(inputs: Inputs): number | null {
    if (!indicadores) return null;
    const smgDiario = inputs.es_zona_fronteriza
      ? indicadores.smg_frontera
      : indicadores.smg_general;
    return inputs.tipo_salario === 'mensual' ? smgDiario * 30 : smgDiario;
  }

  function esValido(inputs: Inputs): boolean {
    if (inputs.salario <= 0 || inputs.antiguedad_anios < 0) return false;
    if (
      inputs.tasa_impuesto_estatal != null &&
      (inputs.tasa_impuesto_estatal < 0 || inputs.tasa_impuesto_estatal > 0.1)
    ) {
      return false;
    }
    if (inputs.prima_riesgo_trabajo != null && inputs.prima_riesgo_trabajo < 0) return false;
    const umbral = umbralMinimo(inputs);
    if (umbral !== null && inputs.salario < umbral) return false;
    // Prestaciones a medio capturar no deben disparar (ni persistir) el cálculo.
    return inputs.prestaciones_adicionales.every((p) => p.nombre.trim() !== '' && p.monto >= 0);
  }

  const calc = useCalculadora({ nombre: 'carga-patronal', defaults: DEFAULTS, esValido });
  const { inputs, setInput, setInputs, resultado } = calc;

  const estados = indicadores?.estados_isn ?? [];
  const estadoActual = estados.find((e) => e.codigo === inputs.codigo_estado);
  const primaClase = indicadores?.primas_riesgo?.[inputs.clase_riesgo];
  const umbral = umbralMinimo(inputs);
  const debajoDelMinimo =
    umbral !== null && inputs.salario > 0 && inputs.salario < umbral;

  const tasaPct =
    inputs.tasa_impuesto_estatal != null
      ? Number((inputs.tasa_impuesto_estatal * 100).toFixed(4))
      : null;

  function actualizarPrestacion(idx: number, patch: Partial<PrestacionAdicional>) {
    setInputs((prev) => ({
      ...prev,
      prestaciones_adicionales: prev.prestaciones_adicionales.map((p, i) =>
        i === idx ? { ...p, ...patch } : p,
      ),
    }));
  }

  return (
    <CalculadoraShell
      titulo="Carga patronal"
      descripcion="Costo real mensual y anual de un empleado: cuotas IMSS, Infonavit, impuesto sobre nómina y prestaciones, más el neto que recibe el trabajador."
      calculando={calc.calculando}
      acciones={
        <ExportButtons
          calculadora="carga-patronal"
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
              (Art. 90 LFT); no es base válida para calcular la carga patronal.
            </p>
          )}

          <ToggleRow
            titulo="Zona Libre de la Frontera Norte"
            descripcion="El salario mínimo de la ZLFN es mayor al del resto del país."
            activo={inputs.es_zona_fronteriza}
            onCambiar={(v) => setInput('es_zona_fronteriza', v)}
          />

          <div className="space-y-2">
            <Label htmlFor="antiguedad">Antigüedad (años cumplidos)</Label>
            <Input
              id="antiguedad"
              type="number"
              min={0}
              value={Number.isFinite(inputs.antiguedad_anios) ? inputs.antiguedad_anios : ''}
              onChange={(e) => setInput('antiguedad_anios', parseInt(e.target.value, 10) || 0)}
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Clase de riesgo (IMSS)</Label>
              <Select
                value={inputs.clase_riesgo}
                onValueChange={(v) => setInput('clase_riesgo', v as ClaseRiesgo)}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CLASES_RIESGO.map((clase) => (
                    <SelectItem key={clase} value={clase}>
                      Clase {clase}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {indicadores?.descripcion_clases_riesgo?.[inputs.clase_riesgo] && (
                <p className="text-xs text-muted-foreground">
                  {indicadores.descripcion_clases_riesgo[inputs.clase_riesgo]}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="prima-riesgo">Prima de riesgo (%)</Label>
              <Input
                id="prima-riesgo"
                type="number"
                min={0}
                step={0.00001}
                value={inputs.prima_riesgo_trabajo ?? ''}
                placeholder={
                  primaClase != null ? `${(primaClase * 100).toFixed(5)} (prima media)` : ''
                }
                onChange={(e) => {
                  const n = Number(e.target.value);
                  setInput(
                    'prima_riesgo_trabajo',
                    e.target.value === '' || !Number.isFinite(n) ? null : n,
                  );
                }}
              />
              <p className="text-xs text-muted-foreground">
                Vacío → prima media de la clase.
              </p>
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label>Estado (impuesto sobre nómina)</Label>
              <Select
                value={inputs.codigo_estado}
                disabled={estados.length === 0}
                onValueChange={(v) => {
                  const estado = estados.find((e) => e.codigo === v);
                  setInputs((prev) => ({
                    ...prev,
                    codigo_estado: v,
                    // Precarga la tasa nominal del estado; queda editable.
                    tasa_impuesto_estatal: estado?.tasa_nomina ?? prev.tasa_impuesto_estatal,
                  }));
                }}
              >
                <SelectTrigger className="w-full">
                  <SelectValue
                    placeholder={estados.length === 0 ? 'Cargando…' : undefined}
                  />
                </SelectTrigger>
                <SelectContent>
                  {estados.length === 0 ? (
                    <SelectItem value={inputs.codigo_estado}>
                      {inputs.codigo_estado}
                    </SelectItem>
                  ) : (
                    estados.map((estado) => (
                      <SelectItem key={estado.codigo} value={estado.codigo}>
                        {estado.nombre}
                      </SelectItem>
                    ))
                  )}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label htmlFor="tasa-isn">Tasa ISN (%)</Label>
              <Input
                id="tasa-isn"
                type="number"
                min={0}
                max={10}
                step={0.1}
                value={tasaPct ?? ''}
                placeholder={
                  estadoActual ? (estadoActual.tasa_nomina * 100).toFixed(2) : ''
                }
                onChange={(e) => {
                  const pct = Number(e.target.value);
                  setInput(
                    'tasa_impuesto_estatal',
                    e.target.value === '' || !Number.isFinite(pct)
                      ? null
                      : Number((pct / 100).toFixed(6)),
                  );
                }}
              />
              <p className="text-xs text-muted-foreground">
                Vacío → tasa nominal del estado.
              </p>
            </div>
          </div>

          <div className="space-y-3 rounded-lg border px-3 py-2.5">
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="incluir-aguinaldo">Incluir aguinaldo prorrateado</Label>
              <Switch
                id="incluir-aguinaldo"
                checked={inputs.incluir_aguinaldo_mensual}
                onCheckedChange={(v) => setInput('incluir_aguinaldo_mensual', v)}
              />
            </div>
            <div className="flex items-center justify-between gap-4">
              <Label htmlFor="incluir-vacaciones">Incluir prima vacacional prorrateada</Label>
              <Switch
                id="incluir-vacaciones"
                checked={inputs.incluir_vacaciones_mensual}
                onCheckedChange={(v) => setInput('incluir_vacaciones_mensual', v)}
              />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Prestaciones adicionales</Label>
            {inputs.prestaciones_adicionales.map((prestacion, idx) => (
              <div key={idx} className="flex items-center gap-2">
                <Input
                  aria-label="Nombre de la prestación"
                  placeholder="Vales de despensa"
                  className="min-w-0 flex-1"
                  value={prestacion.nombre}
                  onChange={(e) => actualizarPrestacion(idx, { nombre: e.target.value })}
                />
                <div className="w-28 shrink-0">
                  <MonedaInput
                    aria-label="Monto de la prestación"
                    value={prestacion.monto > 0 ? prestacion.monto : null}
                    onChange={(v) => actualizarPrestacion(idx, { monto: v ?? 0 })}
                  />
                </div>
                <Select
                  value={prestacion.tipo}
                  onValueChange={(v) =>
                    actualizarPrestacion(idx, { tipo: v as PrestacionAdicional['tipo'] })
                  }
                >
                  <SelectTrigger className="w-28 shrink-0">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="mensual">Mensual</SelectItem>
                    <SelectItem value="anual">Anual</SelectItem>
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  aria-label="Quitar prestación"
                  onClick={() =>
                    setInputs((prev) => ({
                      ...prev,
                      prestaciones_adicionales: prev.prestaciones_adicionales.filter(
                        (_, i) => i !== idx,
                      ),
                    }))
                  }
                >
                  <Icon icon="ph:trash-light" className="size-4" />
                </Button>
              </div>
            ))}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() =>
                setInputs((prev) => ({
                  ...prev,
                  prestaciones_adicionales: [
                    ...prev.prestaciones_adicionales,
                    { nombre: '', monto: 0, tipo: 'mensual' },
                  ],
                }))
              }
            >
              <Icon icon="ph:plus-light" className="size-4" />
              Agregar prestación
            </Button>
          </div>
        </div>
      }
      resultados={
        !resultado ? (
          <SinResultado restaurando={calc.restaurando} icono="ph:factory-light" />
        ) : (
          <>
            <Advertencias advertencias={calc.advertencias} />
            <ResumenCards
              items={[
                {
                  etiqueta: 'Costo total mensual',
                  valor: resultado.costo_total_mensual,
                  tono: 'negativo',
                },
                { etiqueta: 'Costo total anual', valor: resultado.costo_total_anual },
                {
                  etiqueta: 'Carga patronal mensual',
                  valor: resultado.carga_patronal_mensual,
                },
                {
                  etiqueta: 'Salario neto del empleado',
                  valor: resultado.salario_neto,
                  tono: 'positivo',
                },
              ]}
            />
            <p className="text-xs text-muted-foreground">
              SBC diario {formatCurrency(resultado.sbc)} (mensual{' '}
              {formatCurrency(resultado.sbc_mensual)}) · prima de riesgo{' '}
              {resultado.prima_riesgo_aplicada.toFixed(5)}% · ISN{' '}
              {(resultado.tasa_estatal_aplicada * 100).toFixed(2)}% · ISR del empleado{' '}
              {formatCurrency(resultado.isr_empleado)}
            </p>
            <div className="rounded-xl border bg-card p-4 shadow-sm">
              <h2 className="text-sm font-bold">Desglose de conceptos</h2>
              <Table className="mt-2">
                <TableHeader>
                  <TableRow>
                    <TableHead>Concepto</TableHead>
                    <TableHead className="text-right">Mensual</TableHead>
                    <TableHead className="text-right">Anual</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {resultado.desglose.conceptos.map((concepto) => (
                    <TableRow key={concepto.nombre}>
                      <TableCell className="whitespace-normal">
                        {concepto.nombre}
                        <span className="block text-xs text-muted-foreground">
                          {concepto.descripcion}
                        </span>
                      </TableCell>
                      <TableCell className="text-right align-top tabular-nums">
                        {formatCurrency(concepto.monto_mensual)}
                      </TableCell>
                      <TableCell className="text-right align-top tabular-nums">
                        {formatCurrency(concepto.monto_anual)}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
                <TableFooter>
                  <TableRow>
                    <TableCell>Costo total</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.costo_total_mensual)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.costo_total_anual)}
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

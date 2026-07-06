'use client';

import { Advertencias } from '@/components/calculadoras/advertencias';
import {
  CalculadoraShell,
  SinResultado,
} from '@/components/calculadoras/calculadora-shell';
import { ExportButtons } from '@/components/calculadoras/export-buttons';
import { MonedaInput } from '@/components/calculadoras/moneda-input';
import { ResumenCards } from '@/components/calculadoras/resumen-cards';
import { Badge } from '@/components/ui/badge';
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
import { RFC_GENERAL, useCalculadora } from '@/hooks/use-calculadora';
import { formatCurrency, formatDate } from '@/lib/formatting';
import type { CalculadoraInputs, TrabajadorPtuRequest } from '@/lib/types';
import { Fragment, useEffect } from 'react';

type Inputs = CalculadoraInputs<'ptu'>;

const EJERCICIOS = [2021, 2022, 2023, 2024, 2025];

function nuevoTrabajador(): TrabajadorPtuRequest {
  return {
    nombre: '',
    salario_diario: 0,
    dias_trabajados: 365,
    percepcion_anual: 0,
    rfc: '',
    curp: '',
    nss: '',
    es_confianza: false,
    ptu_anio_1: 0,
    ptu_anio_2: 0,
    ptu_anio_3: 0,
    ingreso_mensual_ordinario: 0,
    isr_mensual_ordinario: 0,
  };
}

const DEFAULTS: Inputs = {
  utilidad_fiscal: 0,
  ejercicio: 2025,
  nombre: '',
  rfc_empresa: '',
  ptu_no_cobrada: 0,
  tipo_persona: 'Moral',
  fecha_pago: null,
  criterio_exencion: 'UMA',
  trabajadores: [nuevoTrabajador()],
};

function esValido(inputs: Inputs): boolean {
  if (inputs.utilidad_fiscal <= 0 || inputs.ptu_no_cobrada < 0) return false;
  if (inputs.trabajadores.length < 1) return false;
  return inputs.trabajadores.every(
    (t) =>
      t.salario_diario > 0 &&
      t.dias_trabajados >= 1 &&
      t.dias_trabajados <= 366 &&
      t.percepcion_anual > 0 &&
      t.ptu_anio_1 >= 0 &&
      t.ptu_anio_2 >= 0 &&
      t.ptu_anio_3 >= 0 &&
      t.ingreso_mensual_ordinario >= 0 &&
      t.isr_mensual_ordinario >= 0,
  );
}

/** Input numérico compacto para las celdas de la tabla de trabajadores. */
function CeldaNumero({
  valor,
  onCambio,
  ancho = 'w-24',
  ariaLabel,
}: {
  valor: number;
  onCambio: (n: number) => void;
  ancho?: string;
  ariaLabel: string;
}) {
  return (
    <Input
      type="number"
      min={0}
      aria-label={ariaLabel}
      className={`h-8 ${ancho} text-right tabular-nums md:text-xs`}
      value={valor || ''}
      onChange={(e) => {
        const n = Number(e.target.value);
        onCambio(Number.isFinite(n) ? n : 0);
      }}
    />
  );
}

export default function PtuPage() {
  const calc = useCalculadora({
    nombre: 'ptu',
    defaults: DEFAULTS,
    esValido,
    manual: true,
  });
  const { inputs, setInput, setInputs, resultado, rfcActivo, restaurando } = calc;

  // El tipo de persona se deduce del RFC de la empresa activa (13 caracteres =
  // física, 12 = moral); sin empresa activa se asume moral. La fecha de pago
  // no se captura: aquí solo se calcula el reparto — la fecha límite legal se
  // muestra como referencia.
  const sinEmpresa = rfcActivo === RFC_GENERAL;
  const tipoDerivado: Inputs['tipo_persona'] =
    !sinEmpresa && rfcActivo.length === 13 ? 'Física' : 'Moral';

  useEffect(() => {
    if (restaurando) return;
    if (inputs.tipo_persona !== tipoDerivado || inputs.fecha_pago !== null) {
      setInputs((prev) => ({ ...prev, tipo_persona: tipoDerivado, fecha_pago: null }));
    }
  }, [restaurando, tipoDerivado, inputs.tipo_persona, inputs.fecha_pago, setInputs]);

  const anioPago = inputs.ejercicio + 1;
  const fechaLimite =
    tipoDerivado === 'Moral' ? `${anioPago}-05-30` : `${anioPago}-06-29`;

  function actualizarTrabajador(idx: number, patch: Partial<TrabajadorPtuRequest>) {
    setInputs((prev) => ({
      ...prev,
      trabajadores: prev.trabajadores.map((t, i) => (i === idx ? { ...t, ...patch } : t)),
    }));
  }

  const valido = esValido(inputs);

  return (
    <CalculadoraShell
      titulo="PTU"
      descripcion="Reparto de utilidades (Art. 123 constitucional y 117-131 LFT): bolsas por días y por salarios, tope de tres meses / promedio de tres años, exención de 15 UMA y comparación del ISR por Art. 96 vs Art. 174."
      unaColumna
      calculando={calc.calculando}
      acciones={
        <ExportButtons
          calculadora="ptu"
          inputs={calc.inputs as unknown as Record<string, unknown>}
          habilitado={calc.resultado !== null}
          conRecibos
        />
      }
      formulario={
        <div className="space-y-6">
          {/* Datos de la empresa */}
          <div className="space-y-3">
            <h2 className="text-sm font-bold">Datos de la empresa</h2>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label>Ejercicio</Label>
                <Select
                  value={String(inputs.ejercicio)}
                  onValueChange={(v) => setInput('ejercicio', parseInt(v, 10))}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {EJERCICIOS.map((anio) => (
                      <SelectItem key={anio} value={String(anio)}>
                        {anio} (se paga en {anio + 1})
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Criterio de exención</Label>
                <Select
                  value={inputs.criterio_exencion}
                  onValueChange={(v) => setInput('criterio_exencion', v as 'UMA' | 'SMG')}
                >
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="UMA">UMA (criterio del SAT)</SelectItem>
                    <SelectItem value="SMG">Salario mínimo (criterio PRODECON)</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  La exención es de 15 días: el SAT la calcula con UMA; PRODECON sostiene
                  que procede con salario mínimo (más favorable al trabajador).
                </p>
              </div>
              <div className="space-y-2">
                <Label htmlFor="utilidad">Utilidad fiscal del ejercicio</Label>
                <MonedaInput
                  id="utilidad"
                  value={inputs.utilidad_fiscal > 0 ? inputs.utilidad_fiscal : null}
                  onChange={(v) => setInput('utilidad_fiscal', v ?? 0)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="ptu-no-cobrada">PTU no cobrada del año anterior</Label>
                <MonedaInput
                  id="ptu-no-cobrada"
                  value={inputs.ptu_no_cobrada > 0 ? inputs.ptu_no_cobrada : null}
                  onChange={(v) => setInput('ptu_no_cobrada', v ?? 0)}
                />
              </div>
            </div>
            <p className="text-xs text-muted-foreground">
              Persona {tipoDerivado === 'Moral' ? 'moral' : 'física'}
              {sinEmpresa
                ? ' (sin empresa activa; se asume moral)'
                : ' — según el RFC de la empresa activa'}
              {' · '}fecha límite legal de pago: {formatDate(fechaLimite)}.
            </p>
          </div>

          {/* Trabajadores */}
          <div className="space-y-3">
            <div className="flex items-center justify-between gap-4">
              <h2 className="text-sm font-bold">
                Trabajadores ({inputs.trabajadores.length})
              </h2>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() =>
                  setInputs((prev) => ({
                    ...prev,
                    trabajadores: [...prev.trabajadores, nuevoTrabajador()],
                  }))
                }
              >
                <Icon icon="ph:plus-light" className="size-4" />
                Agregar trabajador
              </Button>
            </div>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Nombre</TableHead>
                  <TableHead className="text-right">Salario diario</TableHead>
                  <TableHead className="text-right">Días</TableHead>
                  <TableHead className="text-right">Percepción anual</TableHead>
                  <TableHead className="text-center">Confianza</TableHead>
                  <TableHead className="text-right">PTU año -1</TableHead>
                  <TableHead className="text-right">PTU año -2</TableHead>
                  <TableHead className="text-right">PTU año -3</TableHead>
                  <TableHead className="text-right">Ingreso mensual</TableHead>
                  <TableHead className="text-right">ISR mensual</TableHead>
                  <TableHead />
                </TableRow>
              </TableHeader>
              <TableBody>
                {inputs.trabajadores.map((t, idx) => (
                  <TableRow key={idx}>
                    <TableCell>
                      <Input
                        aria-label="Nombre del trabajador"
                        placeholder={`Trabajador ${idx + 1}`}
                        className="h-8 w-40 md:text-xs"
                        value={t.nombre}
                        onChange={(e) => actualizarTrabajador(idx, { nombre: e.target.value })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="Salario diario"
                        valor={t.salario_diario}
                        onCambio={(n) => actualizarTrabajador(idx, { salario_diario: n })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="Días trabajados"
                        ancho="w-16"
                        valor={t.dias_trabajados}
                        onCambio={(n) => actualizarTrabajador(idx, { dias_trabajados: n })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="Percepción anual"
                        ancho="w-28"
                        valor={t.percepcion_anual}
                        onCambio={(n) => actualizarTrabajador(idx, { percepcion_anual: n })}
                      />
                    </TableCell>
                    <TableCell className="text-center">
                      <Switch
                        size="sm"
                        aria-label="Trabajador de confianza"
                        checked={t.es_confianza}
                        onCheckedChange={(v) => actualizarTrabajador(idx, { es_confianza: v })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="PTU del año anterior"
                        valor={t.ptu_anio_1}
                        onCambio={(n) => actualizarTrabajador(idx, { ptu_anio_1: n })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="PTU de hace dos años"
                        valor={t.ptu_anio_2}
                        onCambio={(n) => actualizarTrabajador(idx, { ptu_anio_2: n })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="PTU de hace tres años"
                        valor={t.ptu_anio_3}
                        onCambio={(n) => actualizarTrabajador(idx, { ptu_anio_3: n })}
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="Ingreso mensual ordinario"
                        valor={t.ingreso_mensual_ordinario}
                        onCambio={(n) =>
                          actualizarTrabajador(idx, { ingreso_mensual_ordinario: n })
                        }
                      />
                    </TableCell>
                    <TableCell className="text-right">
                      <CeldaNumero
                        ariaLabel="ISR mensual ordinario"
                        valor={t.isr_mensual_ordinario}
                        onCambio={(n) =>
                          actualizarTrabajador(idx, { isr_mensual_ordinario: n })
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon-sm"
                        aria-label="Eliminar trabajador"
                        disabled={inputs.trabajadores.length === 1}
                        onClick={() =>
                          setInputs((prev) => ({
                            ...prev,
                            trabajadores: prev.trabajadores.filter((_, i) => i !== idx),
                          }))
                        }
                      >
                        <Icon icon="ph:trash-light" className="size-4" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            <p className="text-xs text-muted-foreground">
              «PTU año -1/-2/-3»: PTU cobrada en los tres años anteriores (para el tope del
              promedio). «Ingreso/ISR mensual»: nómina ordinaria del mes de pago (para el
              ISR Art. 96 vs Art. 174).
            </p>
          </div>

          <Button
            type="button"
            onClick={() => void calc.calcular()}
            disabled={!valido || calc.calculando}
          >
            {calc.calculando ? (
              <>
                <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
                Calculando…
              </>
            ) : (
              <>
                <Icon icon="ph:calculator-light" className="size-4" />
                Calcular PTU
              </>
            )}
          </Button>
        </div>
      }
      resultados={
        !resultado ? (
          <SinResultado restaurando={calc.restaurando} />
        ) : (
          <>
            <Advertencias advertencias={calc.advertencias} />
            <ResumenCards
              items={[
                { etiqueta: 'PTU a repartir', valor: resultado.empresa.ptu_a_repartir },
                { etiqueta: 'PTU real (con topes)', valor: resultado.totales.ptu_real },
                {
                  etiqueta: 'ISR recomendado',
                  valor: resultado.totales.isr_recomendado,
                  tono: 'negativo',
                },
                {
                  etiqueta: 'Neta a pagar',
                  valor: resultado.totales.ptu_neta_a_pagar,
                  tono: 'positivo',
                },
              ]}
            />
            <p className="text-xs text-muted-foreground">
              Fecha límite de pago: {formatDate(resultado.config.fecha_limite_pago)} ·
              exención por trabajador{' '}
              {formatCurrency(resultado.config.exencion_por_trabajador)} (
              {resultado.config.criterio_exencion}) · bolsa por días{' '}
              {formatCurrency(resultado.empresa.bolsa_dias)} · bolsa por salarios{' '}
              {formatCurrency(resultado.empresa.bolsa_salarios)}
            </p>

            <div className="rounded-xl border bg-card p-4 shadow-sm">
              <h2 className="text-sm font-bold">Reparto por trabajador</h2>
              <Table className="mt-2">
                <TableHeader>
                  <TableRow>
                    <TableHead>Trabajador</TableHead>
                    <TableHead className="text-right">PTU bruta</TableHead>
                    <TableHead className="text-right">Tope</TableHead>
                    <TableHead className="text-right">PTU real</TableHead>
                    <TableHead className="text-right">Exenta</TableHead>
                    <TableHead className="text-right">Gravada</TableHead>
                    <TableHead className="text-right">ISR Art. 96</TableHead>
                    <TableHead className="text-right">ISR Art. 174</TableHead>
                    <TableHead className="text-center">Recomendado</TableHead>
                    <TableHead className="text-right">Neta</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {resultado.trabajadores.map((t, idx) => (
                    <Fragment key={`${t.nombre}-${idx}`}>
                      <TableRow>
                        <TableCell>
                          {t.nombre || `Trabajador ${idx + 1}`}
                          {t.es_confianza && (
                            <span className="block text-xs text-muted-foreground">
                              Confianza
                              {t.salario_tope_confianza != null &&
                                ` · salario topado a ${formatCurrency(t.salario_tope_confianza)}`}
                            </span>
                          )}
                        </TableCell>
                        <TableCell className="text-right align-top tabular-nums">
                          {formatCurrency(t.ptu_bruta)}
                        </TableCell>
                        <TableCell className="text-right align-top tabular-nums">
                          {formatCurrency(t.monto_maximo)}
                        </TableCell>
                        <TableCell className="text-right align-top tabular-nums">
                          {formatCurrency(t.ptu_real)}
                        </TableCell>
                        <TableCell className="text-right align-top tabular-nums">
                          {formatCurrency(t.ptu_exenta)}
                        </TableCell>
                        <TableCell className="text-right align-top tabular-nums">
                          {formatCurrency(t.ptu_gravada)}
                        </TableCell>
                        <TableCell className="text-right align-top tabular-nums">
                          {formatCurrency(t.art96.isr_ptu)}
                        </TableCell>
                        <TableCell className="text-right align-top tabular-nums">
                          {formatCurrency(t.art174.isr_ptu)}
                        </TableCell>
                        <TableCell className="text-center align-top">
                          <Badge variant="secondary">
                            {t.comparacion.metodo_recomendado === 'art174'
                              ? 'Art. 174'
                              : 'Art. 96'}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right align-top font-medium tabular-nums">
                          {formatCurrency(t.comparacion.ptu_neta_final)}
                        </TableCell>
                      </TableRow>
                      {t.advertencias.length > 0 && (
                        <TableRow className="hover:bg-transparent">
                          <TableCell
                            colSpan={10}
                            className="whitespace-normal py-1.5 text-xs text-amber-700 dark:text-amber-300"
                          >
                            {t.advertencias.join(' · ')}
                          </TableCell>
                        </TableRow>
                      )}
                    </Fragment>
                  ))}
                </TableBody>
                <TableFooter>
                  <TableRow>
                    <TableCell>Totales</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.totales.ptu_bruta)}
                    </TableCell>
                    <TableCell />
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.totales.ptu_real)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.totales.ptu_exenta)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.totales.ptu_gravada)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.totales.isr_art96)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.totales.isr_art174)}
                    </TableCell>
                    <TableCell />
                    <TableCell className="text-right tabular-nums">
                      {formatCurrency(resultado.totales.ptu_neta_a_pagar)}
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

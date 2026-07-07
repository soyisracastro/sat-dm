'use client';

import { Fragment, useState } from 'react';

import { Icon } from '@/components/ui/icon';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableFooter,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { cn } from '@/lib/utils';
import type { CatalogosDiot, FilaDiot, HallazgoDiot } from '@/lib/types';

// Columnas de trabajo visibles: los montos que el prellenado llena desde los
// CFDIs. El resto de los 54 campos (fronteras, importaciones, proporciones,
// no acreditable) se edita en la fila expandida, agrupado por sección.
const COLUMNAS_MONTO = [
  { clave: 'valor_16', label: 'Valor 16%' },
  { clave: 'dev_16', label: 'Devoluciones' },
  { clave: 'acred_excl_16', label: 'IVA acreditable' },
  { clave: 'iva_retenido', label: 'IVA retenido' },
] as const;

const SECCIONES_EXPANDIDA: { seccion: string; titulo: string }[] = [
  { seccion: 'valores', titulo: 'Valor de los actos o actividades' },
  { seccion: 'iva_acreditable', titulo: 'IVA acreditable' },
  { seccion: 'iva_no_acreditable', titulo: 'IVA no acreditable' },
  { seccion: 'adicionales', titulo: 'Datos adicionales' },
];

interface Props {
  filas: FilaDiot[];
  catalogos: CatalogosDiot | null;
  errores: HallazgoDiot[];
  advertencias: HallazgoDiot[];
  onCampo: (index: number, campo: string, valor: string | number) => void;
  onEliminar: (index: number) => void;
}

function aEntero(texto: string): number {
  const n = parseInt(texto.replace(/[^\d]/g, ''), 10);
  return Number.isNaN(n) ? 0 : n;
}

const FMT = new Intl.NumberFormat('es-MX');

function InputMonto({
  valor,
  onChange,
  invalido,
  ariaLabel,
}: {
  valor: unknown;
  onChange: (v: number) => void;
  invalido?: boolean;
  ariaLabel: string;
}) {
  return (
    <Input
      inputMode="numeric"
      aria-label={ariaLabel}
      className={cn(
        'h-8 w-28 text-right tabular-nums',
        invalido && 'border-destructive focus-visible:ring-destructive',
      )}
      value={String(Number(valor ?? 0))}
      onChange={(e) => onChange(aEntero(e.target.value))}
      onFocus={(e) => e.target.select()}
    />
  );
}

/**
 * Tabla editable de renglones DIOT: una fila por proveedor con los montos de
 * trabajo inline; la fila expandida edita datos del tercero y los 54 campos
 * completos por sección. Sin ResourceList: esto es captura, no lectura.
 */
export function TablaDiot({ filas, catalogos, errores, advertencias, onCampo, onEliminar }: Props) {
  const [abiertas, setAbiertas] = useState<Set<number>>(new Set());

  const porFila = (lista: HallazgoDiot[], i: number) => lista.filter((h) => h.fila === i);
  const camposInvalidos = (i: number) =>
    new Set(porFila(errores, i).map((e) => e.campo).filter(Boolean) as string[]);

  const toggle = (i: number) =>
    setAbiertas((prev) => {
      const next = new Set(prev);
      if (next.has(i)) next.delete(i);
      else next.add(i);
      return next;
    });

  const totales = COLUMNAS_MONTO.map(({ clave }) =>
    filas.reduce((acc, f) => acc + Number(f[clave] ?? 0), 0),
  );

  const operacionesDe = (tercero: string): string[] =>
    catalogos?.operaciones_por_tercero[tercero] ?? [];

  return (
    <div className="overflow-x-auto rounded-lg border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="w-8" />
            <TableHead>RFC / Proveedor</TableHead>
            <TableHead>Tercero</TableHead>
            <TableHead>Operación</TableHead>
            {COLUMNAS_MONTO.map((c) => (
              <TableHead key={c.clave} className="text-right">
                {c.label}
              </TableHead>
            ))}
            <TableHead className="w-8" />
          </TableRow>
        </TableHeader>
        <TableBody>
          {filas.map((fila, i) => {
            const invalidos = camposInvalidos(i);
            const conError = porFila(errores, i).length > 0;
            const avisos = porFila(advertencias, i);
            const abierta = abiertas.has(i);
            return (
              <Fragment key={i}>
                <TableRow className={cn(conError && 'bg-destructive/5')}>
                  <TableCell className="pr-0">
                    <button
                      type="button"
                      onClick={() => toggle(i)}
                      aria-label={abierta ? 'Contraer renglón' : 'Expandir renglón'}
                      className="text-muted-foreground hover:text-foreground"
                    >
                      <Icon
                        icon={abierta ? 'ph:caret-down-light' : 'ph:caret-right-light'}
                        className="size-4"
                      />
                    </button>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <div>
                        <Input
                          aria-label="RFC del proveedor"
                          placeholder={fila.tipo_tercero === '05' ? 'RFC (opcional)' : 'RFC'}
                          className={cn(
                            'h-8 w-40 font-mono uppercase',
                            invalidos.has('rfc') && 'border-destructive',
                          )}
                          value={fila.rfc}
                          onChange={(e) => onCampo(i, 'rfc', e.target.value.toUpperCase())}
                        />
                        {(fila.nombre || fila.num_cfdis) && (
                          <p className="mt-0.5 max-w-40 truncate text-xs text-muted-foreground">
                            {fila.nombre}
                            {fila.num_cfdis ? ` · ${fila.num_cfdis} CFDIs` : ''}
                          </p>
                        )}
                      </div>
                      {(conError || avisos.length > 0 || fila.estimado) && (
                        <span
                          title={[
                            ...porFila(errores, i).map((e) => e.mensaje),
                            ...avisos.map((a) => a.mensaje),
                          ].join('\n')}
                          aria-label="Ver avisos del renglón"
                        >
                          <Icon
                            icon={conError ? 'ph:warning-circle-light' : 'ph:warning-light'}
                            className={cn('size-4', conError ? 'text-destructive' : 'text-amber-500')}
                          />
                        </span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Select
                      value={fila.tipo_tercero}
                      onValueChange={(v) => {
                        onCampo(i, 'tipo_tercero', v);
                        // La operación válida depende del tercero: resetea al default.
                        const ops = operacionesDe(v);
                        if (!ops.includes(fila.tipo_operacion)) {
                          onCampo(i, 'tipo_operacion', ops[ops.length - 1] ?? '');
                        }
                        if (v === '15') onCampo(i, 'rfc', 'XAXX010101000');
                      }}
                    >
                      <SelectTrigger className="h-8 w-32" aria-label="Tipo de tercero">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {Object.entries(catalogos?.tipo_tercero ?? {}).map(([clave, label]) => (
                          <SelectItem key={clave} value={clave}>
                            {clave} · {label.replace('Proveedor ', '')}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  <TableCell>
                    <Select
                      value={fila.tipo_operacion}
                      onValueChange={(v) => onCampo(i, 'tipo_operacion', v)}
                    >
                      <SelectTrigger
                        className={cn('h-8 w-44', invalidos.has('tipo_operacion') && 'border-destructive')}
                        aria-label="Tipo de operación"
                      >
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {operacionesDe(fila.tipo_tercero).map((clave) => (
                          <SelectItem key={clave} value={clave}>
                            {clave} · {catalogos?.tipo_operacion[clave] ?? clave}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </TableCell>
                  {COLUMNAS_MONTO.map(({ clave, label }) => (
                    <TableCell key={clave} className="text-right">
                      <InputMonto
                        ariaLabel={`${label} del renglón ${i + 1}`}
                        valor={fila[clave]}
                        invalido={invalidos.has(clave)}
                        onChange={(v) => onCampo(i, clave, v)}
                      />
                    </TableCell>
                  ))}
                  <TableCell>
                    <button
                      type="button"
                      onClick={() => onEliminar(i)}
                      aria-label={`Eliminar renglón ${i + 1}`}
                      className="text-muted-foreground hover:text-destructive"
                    >
                      <Icon icon="ph:trash-light" className="size-4" />
                    </button>
                  </TableCell>
                </TableRow>
                {abierta && (
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableCell colSpan={9} className="p-4">
                      <FilaExpandida
                        fila={fila}
                        index={i}
                        catalogos={catalogos}
                        invalidos={invalidos}
                        onCampo={onCampo}
                      />
                    </TableCell>
                  </TableRow>
                )}
              </Fragment>
            );
          })}
        </TableBody>
        {filas.length > 0 && (
          <TableFooter>
            <TableRow>
              <TableCell colSpan={4}>
                {filas.length} proveedor{filas.length === 1 ? '' : 'es'}
              </TableCell>
              {totales.map((t, i) => (
                <TableCell key={COLUMNAS_MONTO[i].clave} className="text-right tabular-nums">
                  {FMT.format(t)}
                </TableCell>
              ))}
              <TableCell />
            </TableRow>
          </TableFooter>
        )}
      </Table>
    </div>
  );
}

/** Editor completo del renglón: datos del extranjero + 54 campos por sección. */
function FilaExpandida({
  fila,
  index,
  catalogos,
  invalidos,
  onCampo,
}: {
  fila: FilaDiot;
  index: number;
  catalogos: CatalogosDiot | null;
  invalidos: Set<string>;
  onCampo: (index: number, campo: string, valor: string | number) => void;
}) {
  const esExtranjero = fila.tipo_tercero === '05';
  const camposDe = (seccion: string) =>
    (catalogos?.campos ?? []).filter((c) => c.seccion === seccion && c.tipo === 'entero');

  return (
    <div className="space-y-4 text-sm">
      {/* Datos del tercero extranjero + manifiesto */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {esExtranjero && (
          <>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Núm. de identificación fiscal</span>
              <Input
                className={cn('h-8', invalidos.has('id_fiscal') && 'border-destructive')}
                value={fila.id_fiscal}
                onChange={(e) => onCampo(index, 'id_fiscal', e.target.value)}
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Nombre del extranjero</span>
              <Input
                className={cn('h-8', invalidos.has('nombre_extranjero') && 'border-destructive')}
                value={fila.nombre_extranjero}
                onChange={(e) => onCampo(index, 'nombre_extranjero', e.target.value)}
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">País de residencia fiscal</span>
              <Select value={fila.pais || undefined} onValueChange={(v) => onCampo(index, 'pais', v)}>
                <SelectTrigger
                  className={cn('h-8', invalidos.has('pais') && 'border-destructive')}
                  aria-label="País de residencia fiscal"
                >
                  <SelectValue placeholder="Selecciona país" />
                </SelectTrigger>
                <SelectContent>
                  {Object.entries(catalogos?.paises ?? {}).map(([clave, nombre]) => (
                    <SelectItem key={clave} value={clave}>
                      {clave} · {nombre}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </label>
            {fila.pais === 'ZZZ' && (
              <label className="space-y-1">
                <span className="text-xs text-muted-foreground">Lugar de jurisdicción fiscal</span>
                <Input
                  className={cn('h-8', invalidos.has('lugar_jurisdiccion') && 'border-destructive')}
                  value={fila.lugar_jurisdiccion}
                  onChange={(e) => onCampo(index, 'lugar_jurisdiccion', e.target.value)}
                />
              </label>
            )}
          </>
        )}
        <label className="space-y-1">
          <span className="text-xs text-muted-foreground">Manifiesto de efectos fiscales</span>
          <Select value={fila.manifiesto} onValueChange={(v) => onCampo(index, 'manifiesto', v)}>
            <SelectTrigger
              className={cn('h-8', invalidos.has('manifiesto') && 'border-destructive')}
              aria-label="Manifiesto de efectos fiscales"
            >
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {Object.entries(catalogos?.manifiesto ?? { '01': 'Sí', '02': 'No' }).map(
                ([clave, label]) => (
                  <SelectItem key={clave} value={clave}>
                    {clave} · {label}
                  </SelectItem>
                ),
              )}
            </SelectContent>
          </Select>
        </label>
      </div>

      {/* Los 54 campos por sección (montos enteros). */}
      {SECCIONES_EXPANDIDA.map(({ seccion, titulo }) => (
        <details key={seccion} open={seccion === 'valores'} className="rounded-md border px-3 py-2">
          <summary className="cursor-pointer select-none text-xs font-medium text-muted-foreground">
            {titulo}
          </summary>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {camposDe(seccion).map((campo) => (
              <label key={campo.clave} className="flex items-center justify-between gap-2">
                <span className="text-xs text-muted-foreground">{campo.etiqueta}</span>
                <InputMonto
                  ariaLabel={campo.etiqueta}
                  valor={fila[campo.clave]}
                  invalido={invalidos.has(campo.clave)}
                  onChange={(v) => onCampo(index, campo.clave, v)}
                />
              </label>
            ))}
          </div>
        </details>
      ))}
    </div>
  );
}

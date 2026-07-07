'use client';

import { useState } from 'react';
import { Dialog as DialogPrimitive } from 'radix-ui';

import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { cn } from '@/lib/utils';
import { MontoInput } from '@/components/diot/monto-input';
import type { CampoDiotMeta, CatalogosDiot, FilaDiot, HallazgoDiot } from '@/lib/types';

const FMT = new Intl.NumberFormat('es-MX');

const SECCIONES: { seccion: CampoDiotMeta['seccion']; titulo: string; icono: string }[] = [
  { seccion: 'valores', titulo: 'Valor de los actos o actividades', icono: 'ph:receipt-light' },
  { seccion: 'iva_acreditable', titulo: 'IVA acreditable', icono: 'ph:percent-light' },
  { seccion: 'iva_no_acreditable', titulo: 'IVA no acreditable', icono: 'ph:percent-light' },
  { seccion: 'adicionales', titulo: 'Datos adicionales', icono: 'ph:info-light' },
];

interface Props {
  index: number | null;
  filas: FilaDiot[];
  catalogos: CatalogosDiot | null;
  errores: HallazgoDiot[];
  onCampo: (index: number, campo: string, valor: string | number) => void;
  onClose: () => void;
}

/** Panel lateral con el detalle completo de un renglón (los 54 campos). */
export function DetalleDrawer({ index, filas, catalogos, errores, onCampo, onClose }: Props) {
  const abierto = index !== null;
  const fila = abierto ? filas[index] : null;

  return (
    <DialogPrimitive.Root open={abierto} onOpenChange={(o) => !o && onClose()}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50 data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className="fixed inset-y-0 right-0 z-50 flex w-full max-w-md flex-col bg-background shadow-lg outline-none duration-200 data-[state=closed]:animate-out data-[state=closed]:slide-out-to-right data-[state=open]:animate-in data-[state=open]:slide-in-from-right"
          aria-describedby={undefined}
        >
          {fila && index !== null && (
            <DrawerContenido
              fila={fila}
              index={index}
              catalogos={catalogos}
              errores={errores}
              onCampo={onCampo}
              onClose={onClose}
            />
          )}
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function DrawerContenido({
  fila,
  index,
  catalogos,
  errores,
  onCampo,
  onClose,
}: {
  fila: FilaDiot;
  index: number;
  catalogos: CatalogosDiot | null;
  errores: HallazgoDiot[];
  onCampo: (index: number, campo: string, valor: string | number) => void;
  onClose: () => void;
}) {
  const invalidos = new Set(
    errores.filter((e) => e.fila === index && e.campo).map((e) => e.campo as string),
  );
  const set = (campo: string, valor: string | number) => onCampo(index, campo, valor);

  const esExtranjero = fila.tipo_tercero === '05';
  const terceroLabel = catalogos?.tipo_tercero[fila.tipo_tercero] ?? fila.tipo_tercero;

  const camposDe = (seccion: string) =>
    (catalogos?.campos ?? []).filter((c) => c.seccion === seccion && c.tipo === 'entero');

  const totalAcreditable = camposDe('iva_acreditable').reduce(
    (acc, c) => acc + Number(fila[c.clave] ?? 0),
    0,
  );

  return (
    <>
      {/* Encabezado */}
      <div className="flex items-start justify-between gap-3 border-b p-5">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Icon icon="ph:files-light" className="size-3.5" />
            Detalle · renglón {index + 1}
          </div>
          <DialogPrimitive.Title className="mt-1 truncate text-base font-semibold">
            {fila.nombre || 'Proveedor sin nombre'}
          </DialogPrimitive.Title>
          <p className="mt-0.5 truncate text-xs text-muted-foreground">
            {fila.rfc || 'RFC pendiente'} · {terceroLabel}
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Cerrar"
          className="rounded-md p-1 text-muted-foreground hover:bg-accent hover:text-foreground"
        >
          <Icon icon="ph:x-light" className="size-4" />
        </button>
      </div>

      {/* Cuerpo */}
      <div className="flex-1 overflow-y-auto p-5">
        {/* Datos del extranjero (solo tercero 05) */}
        {esExtranjero && (
          <div className="mb-4 grid gap-3">
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Núm. de identificación fiscal</span>
              <Input
                className={cn('h-8', invalidos.has('id_fiscal') && 'border-destructive')}
                value={fila.id_fiscal}
                onChange={(e) => set('id_fiscal', e.target.value)}
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">Nombre del extranjero</span>
              <Input
                className={cn('h-8', invalidos.has('nombre_extranjero') && 'border-destructive')}
                value={fila.nombre_extranjero}
                onChange={(e) => set('nombre_extranjero', e.target.value)}
              />
            </label>
            <label className="space-y-1">
              <span className="text-xs text-muted-foreground">País de residencia fiscal</span>
              <Select value={fila.pais || undefined} onValueChange={(v) => set('pais', v)}>
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
                  onChange={(e) => set('lugar_jurisdiccion', e.target.value)}
                />
              </label>
            )}
          </div>
        )}

        {/* Manifiesto de efectos fiscales */}
        <div className="mb-4 flex items-center justify-between gap-3 rounded-lg border bg-muted/30 px-3 py-2.5">
          <div className="min-w-0">
            <p className="text-sm font-medium">Manifiesto de efectos fiscales</p>
            <p className="text-xs text-muted-foreground">
              Indica si el CFDI surte efectos fiscales para esta declaración.
            </p>
          </div>
          <Select value={fila.manifiesto} onValueChange={(v) => set('manifiesto', v)}>
            <SelectTrigger
              className={cn('h-8 w-32 shrink-0', invalidos.has('manifiesto') && 'border-destructive')}
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
        </div>

        {/* Secciones colapsables de montos */}
        <div className="divide-y rounded-lg border">
          {SECCIONES.map(({ seccion, titulo, icono }) => (
            <SeccionMontos
              key={seccion}
              titulo={titulo}
              icono={icono}
              campos={camposDe(seccion)}
              fila={fila}
              invalidos={invalidos}
              onCampo={set}
            />
          ))}
        </div>
        <p className="mt-3 text-xs text-muted-foreground">
          Los montos del 16% y el IVA retenido se sincronizan con las columnas de la tabla. El
          resto aplica solo si tuviste región fronteriza, importaciones o IVA no acreditable.
        </p>
      </div>

      {/* Pie */}
      <div className="flex items-center justify-between gap-3 border-t p-4">
        <span className="text-xs text-muted-foreground">
          IVA acreditable <b className="text-foreground">${FMT.format(totalAcreditable)}</b> ·
          retenido <b className="text-foreground">${FMT.format(Number(fila.iva_retenido ?? 0))}</b>
        </span>
        <Button size="sm" onClick={onClose}>
          <Icon icon="ph:check-circle-light" className="size-4" />
          Listo
        </Button>
      </div>
    </>
  );
}

function SeccionMontos({
  titulo,
  icono,
  campos,
  fila,
  invalidos,
  onCampo,
}: {
  titulo: string;
  icono: string;
  campos: CampoDiotMeta[];
  fila: FilaDiot;
  invalidos: Set<string>;
  onCampo: (campo: string, valor: string | number) => void;
}) {
  const conValor = campos.filter((c) => Number(fila[c.clave] ?? 0) > 0).length;
  const tieneError = campos.some((c) => invalidos.has(c.clave));
  // Abierta si ya trae montos o si tiene un error que corregir.
  const [open, setOpen] = useState(conValor > 0 || tieneError);

  return (
    <div>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left"
      >
        <span className="flex items-center gap-2 text-sm font-medium">
          <Icon icon={icono} className="size-4 text-muted-foreground" />
          {titulo}
        </span>
        <span className="flex items-center gap-3">
          <span className={cn('text-xs', conValor > 0 ? 'text-foreground' : 'text-muted-foreground')}>
            {conValor > 0 ? `${conValor} con valor` : 'sin capturar'}
          </span>
          <Icon
            icon="ph:caret-down-light"
            className={cn('size-4 text-muted-foreground transition-transform', open && 'rotate-180')}
          />
        </span>
      </button>
      {open && (
        <div className="space-y-2 px-3 pb-3">
          {campos.map((campo) => (
            <div key={campo.clave} className="flex items-center justify-between gap-3">
              <span className="text-xs text-muted-foreground">{campo.etiqueta}</span>
              <MontoInput
                ariaLabel={campo.etiqueta}
                valor={fila[campo.clave]}
                invalido={invalidos.has(campo.clave)}
                onChange={(v) => onCampo(campo.clave, v)}
                className="w-32 shrink-0"
              />
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

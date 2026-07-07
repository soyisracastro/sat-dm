'use client';

import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { CargarXmlDialog } from '@/components/diot/cargar-xml-dialog';

const PASOS = [
  { n: 1, titulo: 'Descarga tus CFDIs', detalle: 'Recibidos del periodo' },
  { n: 2, titulo: 'Prellena y ajusta', detalle: 'Revisa montos por proveedor' },
  { n: 3, titulo: 'Genera el TXT', detalle: 'Carga masiva en el SAT' },
];

interface Props {
  onPrellenar: () => void;
  prellenando: boolean;
  onCargado: () => void;
}

/** Estado vacío con guía de 3 pasos y accesos a prellenar / cargar XMLs. */
export function DiotEmpty({ onPrellenar, prellenando, onCargado }: Props) {
  return (
    <div className="flex flex-col items-center rounded-lg border border-dashed p-10 text-center">
      <div className="flex size-14 items-center justify-center rounded-full bg-muted">
        <Icon icon="ph:file-text-light" className="size-7 text-muted-foreground" />
      </div>
      <h3 className="mt-4 text-base font-medium">Sin renglones para este periodo</h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
        Prellena desde los CFDIs recibidos que ya cargaste en Comprobantes, sube XMLs aquí
        mismo, o captura los proveedores a mano.
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        <Button size="sm" onClick={onPrellenar} disabled={prellenando}>
          <Icon
            icon={prellenando ? 'ph:circle-notch-light' : 'ph:sparkle-light'}
            className={prellenando ? 'size-4 animate-spin' : 'size-4'}
          />
          Prellenar desde comprobantes
        </Button>
        <CargarXmlDialog onCargado={onCargado} />
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-center gap-2">
        {PASOS.map((paso, i) => (
          <div key={paso.n} className="flex items-center gap-2">
            <div className="flex items-center gap-2 rounded-lg border bg-card px-3 py-2 text-left">
              <span className="flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                {paso.n}
              </span>
              <span>
                <span className="block text-sm font-medium">{paso.titulo}</span>
                <span className="block text-xs text-muted-foreground">{paso.detalle}</span>
              </span>
            </div>
            {i < PASOS.length - 1 && (
              <Icon icon="ph:arrow-right-light" className="size-4 text-muted-foreground" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

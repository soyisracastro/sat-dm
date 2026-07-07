'use client';

import { Fragment } from 'react';

import {
  PartesBuilder,
  VistaPrevia,
  valorSegmento,
} from '@/components/organizador/builder-partes';
import { Icon } from '@/components/ui/icon';
import { NIVELES_CUSTOM } from '@/lib/constants';

interface EstructuraCustomBuilderProps {
  /** Segmentos en orden, de la carpeta raíz hacia adentro (tokens o "txt:Texto"). */
  niveles: string[];
  onChange: (niveles: string[]) => void;
  /** RFC de la empresa activa; se muestra en la vista previa del token "rfc". */
  rfcEmpresa?: string;
}

/**
 * Builder de la estructura personalizada del organizador: paleta de variables
 * del CFDI, niveles reordenables por arrastre y vista previa tipo Finder.
 */
export function EstructuraCustomBuilder({
  niveles,
  onChange,
  rfcEmpresa,
}: EstructuraCustomBuilderProps) {
  return (
    <PartesBuilder
      items={niveles}
      onChange={onChange}
      catalogo={NIVELES_CUSTOM}
      titulo="Niveles de carpeta"
      contador={(n) =>
        `${n} ${n === 1 ? 'nivel' : 'niveles'} · de afuera hacia adentro`
      }
      hint="Toca un segmento para agregarlo. Arrastra las filas para reordenar los niveles."
      paletaLabel="Agrega niveles"
      iconoFila="ph:folder-light"
      vacioTexto="Aún no hay niveles. Agrega uno abajo."
      preview={
        <VistaPrevia>
          <PathPreview segmentos={niveles} rfcEmpresa={rfcEmpresa} vacioAviso />
        </VistaPrevia>
      }
    />
  );
}

interface PathPreviewProps {
  segmentos: string[];
  rfcEmpresa?: string;
  /** Con true, la lista vacía muestra un aviso en lugar de solo el archivo. */
  vacioAviso?: boolean;
}

/** Ruta de ejemplo tipo Finder: carpetas → factura.xml. */
export function PathPreview({ segmentos, rfcEmpresa, vacioAviso }: PathPreviewProps) {
  if (segmentos.length === 0 && vacioAviso) {
    return (
      <div className="rounded-lg border border-dashed bg-card px-3 py-2.5 text-xs text-muted-foreground/70">
        Agrega al menos un nivel para ver la ruta resultante.
      </div>
    );
  }
  return (
    <div className="flex flex-wrap items-center gap-x-0.5 gap-y-1 rounded-lg border bg-card px-3 py-2.5 font-mono text-xs">
      {segmentos.map((seg, i) => (
        <Fragment key={i}>
          {i > 0 && <Separador />}
          <span className="inline-flex items-center gap-1 whitespace-nowrap">
            <Icon icon="ph:folder-light" className="size-3.5 text-primary" />
            {valorSegmento(seg, NIVELES_CUSTOM, rfcEmpresa)}
          </span>
        </Fragment>
      ))}
      {segmentos.length > 0 && <Separador />}
      <span className="inline-flex items-center gap-1 whitespace-nowrap text-muted-foreground">
        <Icon icon="ph:file-text-light" className="size-3.5" />
        factura.xml
      </span>
    </div>
  );
}

function Separador() {
  return (
    <Icon
      icon="ph:caret-right-light"
      className="mx-0.5 size-3 shrink-0 text-muted-foreground/40"
    />
  );
}

interface VistaPreviaEstructuraProps {
  /** Valor del preset ("rfc_emisor/anio/mes", "plano", …). */
  estructura: string;
  rfcEmpresa?: string;
}

/** Vista previa de un preset del Select (sin builder). */
export function VistaPreviaEstructura({
  estructura,
  rfcEmpresa,
}: VistaPreviaEstructuraProps) {
  const segmentos = estructura === 'plano' ? [] : estructura.split('/');
  return (
    <VistaPrevia>
      <PathPreview segmentos={segmentos} rfcEmpresa={rfcEmpresa} />
    </VistaPrevia>
  );
}

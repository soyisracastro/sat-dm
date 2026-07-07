'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Icon } from '@/components/ui/icon';
import { CfdiUploader } from '@/components/procesador-cfdi/cfdi-uploader';

interface Props {
  /** Llamado tras cada carga exitosa (la página re-prellena el periodo). */
  onCargado: () => void;
  variant?: 'outline' | 'default';
}

/**
 * "Cargar XMLs…" directo en la pantalla DIOT: alimenta el mismo buffer por
 * empresa del procesador (deduplicación por UUID y validación de empresa
 * incluidas) sin obligar a navegar a Comprobantes. Al cerrar, el padre
 * re-prellena el periodo para sumar los proveedores nuevos.
 */
export function CargarXmlDialog({ onCargado, variant = 'outline' }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant={variant} size="sm">
          <Icon icon="ph:upload-simple-light" className="size-4" />
          Cargar XMLs
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Cargar XMLs para la DIOT</DialogTitle>
          <DialogDescription>
            Arrastra archivos o examina una carpeta. Los CFDIs se agregan al buffer de la
            empresa activa (sin duplicar folios ya cargados) y el periodo se vuelve a
            prellenar con los proveedores nuevos.
          </DialogDescription>
        </DialogHeader>
        <CfdiUploader bareback onCargado={onCargado} />
      </DialogContent>
    </Dialog>
  );
}

'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { CfdiUploader } from '@/components/procesador-cfdi/cfdi-uploader';

interface Props {
  /** Llamado tras cada carga exitosa para refrescar tabla/stats del padre. */
  onCargado: () => void;
}

/**
 * Botón que abre un modal con el uploader. Reemplaza el uploader inline una
 * vez que el buffer ya tiene CFDIs — así el listado/tabla son lo primero a la
 * vista y el "Cargar más" es una acción explícita.
 */
export function CfdiCargarMasButton({ onCargado }: Props) {
  const [open, setOpen] = useState(false);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm">
          <Icon icon="ph:upload-light" className="size-4" />
          Cargar más XMLs
        </Button>
      </DialogTrigger>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>Cargar más XMLs</DialogTitle>
          <DialogDescription>
            Arrastra archivos, examina una carpeta o importa los que ya descargó el agente
            para la empresa activa. Los XMLs se acumulan hasta que pulses Borrar.
          </DialogDescription>
        </DialogHeader>
        <CfdiUploader bareback onCargado={onCargado} />
      </DialogContent>
    </Dialog>
  );
}

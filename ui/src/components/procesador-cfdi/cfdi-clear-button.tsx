'use client';

import { ReactNode, useState } from 'react';
import { toast } from 'sonner';

import { useServer } from '@/providers/server-provider';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { mensajeDeError } from '@/lib/errores';

interface Props {
  /**
   * Total de items que se borrarán; se interpola en la descripción default.
   * Ignorado si se pasa `descripcion` custom.
   */
  total?: number;
  /**
   * Descripción custom del dialog. Por default usa "los {total} CFDIs cargados",
   * pero la página de Pagos pasa una descripción más precisa que aclara que
   * borra TODO el buffer (incluyendo PPDs + complementos del procesador CFDI).
   */
  descripcion?: ReactNode;
  /** Callback tras borrar exitoso. */
  onBorrado: () => void;
}

export function CfdiClearButton({ total = 0, descripcion, onBorrado }: Props) {
  const { apiClient } = useServer();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);

  async function confirmar() {
    setBusy(true);
    try {
      await apiClient.procesadorBorrar();
      toast.success('Procesador vaciado');
      setOpen(false);
      onBorrado();
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusy(false);
    }
  }

  const descripcionFinal = descripcion ?? (
    <>
      Esto eliminará los {total.toLocaleString('es-MX')} CFDIs cargados y los filtros
      activos. La acción no se puede deshacer.
    </>
  );

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="destructive" size="sm">
          <Icon icon="ph:trash-light" className="size-4" />
          Borrar todo
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>¿Vaciar el procesador?</DialogTitle>
          <DialogDescription>{descripcionFinal}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button variant="outline" onClick={() => setOpen(false)} disabled={busy}>
            Cancelar
          </Button>
          <Button variant="destructive" onClick={confirmar} disabled={busy}>
            {busy ? (
              <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
            ) : (
              <Icon icon="ph:trash-light" className="size-4" />
            )}
            Sí, vaciar
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

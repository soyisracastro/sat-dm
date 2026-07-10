'use client';

import { useEffect, useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Icon } from '@/components/ui/icon';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { toast } from 'sonner';

import { mensajeDeError } from '@/lib/errores';
import type { Empresa, TareaCrearRequest, TareaPrioridad, TareaTipo } from '@/lib/types';
import {
  CampoEmpresa,
  CampoFecha,
  CampoPrioridad,
  CampoTipo,
  EMPRESA_GENERAL,
} from '@/components/tareas/tarea-form-campos';

interface NuevaTareaDialogProps {
  open: boolean;
  onClose: () => void;
  empresas: Empresa[];
  onCrear: (req: TareaCrearRequest) => Promise<unknown>;
}

/** Modal "Nueva tarea": título, empresa opcional, fecha, tipo y prioridad. */
export function NuevaTareaDialog({
  open,
  onClose,
  empresas,
  onCrear,
}: NuevaTareaDialogProps) {
  const [titulo, setTitulo] = useState('');
  const [rfc, setRfc] = useState(EMPRESA_GENERAL);
  const [fecha, setFecha] = useState('');
  const [tipo, setTipo] = useState<TareaTipo>('manual');
  const [prioridad, setPrioridad] = useState<TareaPrioridad>('media');
  const [guardando, setGuardando] = useState(false);

  useEffect(() => {
    if (!open) {
      setTitulo('');
      setRfc(EMPRESA_GENERAL);
      setFecha('');
      setTipo('manual');
      setPrioridad('media');
      setGuardando(false);
    }
  }, [open]);

  async function crear() {
    if (!titulo.trim() || guardando) return;
    setGuardando(true);
    try {
      await onCrear({
        titulo: titulo.trim(),
        rfc: rfc === EMPRESA_GENERAL ? null : rfc,
        tipo,
        prioridad,
        fecha: fecha || null,
      });
      onClose();
    } catch (e) {
      toast.error(mensajeDeError(e));
      setGuardando(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nueva tarea</DialogTitle>
          <DialogDescription>
            Ponle empresa si aplica, o déjala general. Se guarda solo para ti.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="tarea-titulo">¿Qué necesitas hacer?</Label>
            <Input
              id="tarea-titulo"
              autoFocus
              value={titulo}
              onChange={(e) => setTitulo(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && crear()}
              placeholder="Ej. Presentar DIOT de junio"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <CampoEmpresa valor={rfc} onChange={setRfc} empresas={empresas} />
            <CampoFecha valor={fecha} onChange={setFecha} />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <CampoTipo valor={tipo} onChange={setTipo} />
            <CampoPrioridad valor={prioridad} onChange={setPrioridad} />
          </div>

          <Button
            className="w-full"
            onClick={crear}
            disabled={!titulo.trim() || guardando}
          >
            <Icon icon="ph:plus-light" className="size-4" />
            {guardando ? 'Creando…' : 'Crear tarea'}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

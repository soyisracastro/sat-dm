'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import { useServer } from '@/providers/server-provider';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';

interface Props {
  /** Llamado tras una validación exitosa para refrescar el listado. */
  onValidado: () => void;
}

export function CfdiValidarButton({ onValidado }: Props) {
  const { apiClient } = useServer();
  const [busy, setBusy] = useState(false);

  async function validar() {
    setBusy(true);
    try {
      const r = await apiClient.procesadorValidarSat();
      if (r.validados === 0) {
        toast.info('No hay CFDIs pendientes de validar contra el SAT.');
      } else {
        toast.success(
          `${r.validados} validados — ${r.vigentes} vigentes, ${r.cancelados} cancelados` +
            (r.no_encontrados > 0 ? `, ${r.no_encontrados} no encontrados` : '') +
            (r.errores > 0 ? `, ${r.errores} con error` : ''),
        );
        onValidado();
      }
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      toast.error(`Error validando: ${msg}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button variant="outline" size="sm" onClick={validar} disabled={busy}>
      <Icon
        icon={busy ? 'ph:circle-notch-light' : 'ph:shield-check-light'}
        className={busy ? 'size-4 animate-spin' : 'size-4'}
      />
      Validar contra SAT
    </Button>
  );
}

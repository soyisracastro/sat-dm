'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import { useServer } from '@/providers/server-provider';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import type { NominaFiltros } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

interface Props {
  /** RFC de la empresa activa: el export sale de SU buffer. */
  rfc: string;
  filtros: Partial<NominaFiltros>;
}

function descargarBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

export function NominaExportButton({ rfc, filtros }: Props) {
  const { apiClient } = useServer();
  const [busy, setBusy] = useState(false);

  async function exportar() {
    setBusy(true);
    try {
      const blob = await apiClient.procesadorNominaExportar(rfc, filtros);
      const fecha = new Date().toISOString().slice(0, 10);
      descargarBlob(blob, `nomina_${fecha}.xlsx`);
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button size="sm" onClick={exportar} disabled={busy}>
      <Icon
        icon={busy ? 'ph:circle-notch-light' : 'ph:download-simple-light'}
        className={busy ? 'size-4 animate-spin' : 'size-4'}
      />
      Exportar Excel
    </Button>
  );
}

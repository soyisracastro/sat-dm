'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import { useServer } from '@/providers/server-provider';
import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Icon } from '@/components/ui/icon';
import type { CfdiFiltros } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

interface Props {
  filtros: Partial<CfdiFiltros>;
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

export function CfdiExportButtons({ filtros }: Props) {
  const { apiClient } = useServer();
  const [busy, setBusy] = useState<'xlsx' | 'csv' | null>(null);

  async function exportar(formato: 'xlsx' | 'csv') {
    setBusy(formato);
    try {
      const blob = await apiClient.procesadorExportar(formato, filtros);
      const fecha = new Date().toISOString().slice(0, 10);
      descargarBlob(blob, `cfdis_${fecha}.${formato}`);
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusy(null);
    }
  }

  const cargando = busy !== null;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button size="sm" disabled={cargando}>
          <Icon
            icon={cargando ? 'ph:circle-notch-light' : 'ph:download-simple-light'}
            className={cargando ? 'size-4 animate-spin' : 'size-4'}
          />
          Exportar
          <Icon icon="ph:caret-down-light" className="size-3" />
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuLabel>Formato</DropdownMenuLabel>
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => exportar('xlsx')} disabled={cargando}>
          <Icon icon="ph:file-xls-light" className="size-4" />
          Excel
        </DropdownMenuItem>
        <DropdownMenuItem onSelect={() => exportar('csv')} disabled={cargando}>
          <Icon icon="ph:file-csv-light" className="size-4" />
          CSV
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

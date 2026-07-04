'use client';

import Link from 'next/link';
import { useState } from 'react';
import { toast } from 'sonner';

import { useAuth } from '@/providers/auth-provider';
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
import type { CalculadoraNombre } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

type Formato = 'xlsx' | 'pdf' | 'recibos-ptu';

interface Props {
  calculadora: CalculadoraNombre;
  /** Inputs actuales (el backend recalcula desde ellos — fuente única). */
  inputs: Record<string, unknown>;
  /** true cuando hay un resultado válido que exportar. */
  habilitado: boolean;
  /** Muestra la opción "Recibos por trabajador" (solo PTU). */
  conRecibos?: boolean;
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

/**
 * Botón de exportación de un cálculo (Excel / PDF / recibos PTU).
 *
 * Función premium: sin `premium_features_unlocked` el botón se muestra con
 * candado y lleva a /suscripcion — el cálculo en pantalla sigue siendo libre.
 */
export function ExportButtons({ calculadora, inputs, habilitado, conRecibos = false }: Props) {
  const { apiClient } = useServer();
  const { license } = useAuth();
  const [busy, setBusy] = useState<Formato | null>(null);

  const esPremium = license?.premium_features_unlocked === true;

  if (!esPremium) {
    return (
      <Button size="sm" variant="outline" asChild>
        <Link href="/suscripcion" title="Exportar es una función premium">
          <Icon icon="ph:lock-simple-light" className="size-4" />
          Exportar (Premium)
        </Link>
      </Button>
    );
  }

  async function exportar(formato: Formato) {
    setBusy(formato);
    try {
      // El RFC es solo para el auto-guardado del estado; el export no lo usa.
      const { rfc: _rfc, ...inputsLimpios } = inputs;
      const blob = await apiClient.calculadoraExportar(formato, calculadora, inputsLimpios);
      const ext = formato === 'xlsx' ? 'xlsx' : 'pdf';
      const base = formato === 'recibos-ptu' ? 'recibos-ptu' : calculadora;
      descargarBlob(blob, `${base}.${ext}`);
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
        <Button size="sm" disabled={cargando || !habilitado}>
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
        <DropdownMenuItem onSelect={() => exportar('pdf')} disabled={cargando}>
          <Icon icon="ph:file-pdf-light" className="size-4" />
          PDF
        </DropdownMenuItem>
        {conRecibos && (
          <>
            <DropdownMenuSeparator />
            <DropdownMenuItem onSelect={() => exportar('recibos-ptu')} disabled={cargando}>
              <Icon icon="ph:printer-light" className="size-4" />
              Recibos por trabajador (PDF)
            </DropdownMenuItem>
          </>
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}

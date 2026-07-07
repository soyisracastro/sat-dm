'use client';

import Link from 'next/link';
import { useState } from 'react';
import { toast } from 'sonner';

import { useAuth } from '@/providers/auth-provider';
import { useServer } from '@/providers/server-provider';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { mensajeDeError } from '@/lib/errores';

interface Props {
  rfc: string;
  periodo: string;
  /** true cuando hay renglones y ningún error duro. */
  habilitado: boolean;
  /** Cantidad de errores duros (para el title del botón deshabilitado). */
  numErrores: number;
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
 * Descarga el TXT de carga masiva. Función premium: sin
 * `premium_features_unlocked` el botón lleva a /suscripcion — ver y editar la
 * tabla sigue siendo libre.
 */
export function ExportTxtButton({ rfc, periodo, habilitado, numErrores }: Props) {
  const { apiClient } = useServer();
  const { license } = useAuth();
  const [busy, setBusy] = useState(false);

  const esPremium = license?.premium_features_unlocked === true;

  if (!esPremium) {
    return (
      <Button size="sm" variant="outline" asChild>
        <Link href="/suscripcion" title="Generar el TXT es una función premium">
          <Icon icon="ph:lock-simple-light" className="size-4" />
          Generar TXT (Premium)
        </Link>
      </Button>
    );
  }

  async function exportar() {
    setBusy(true);
    try {
      const blob = await apiClient.diotExportar(rfc, periodo);
      descargarBlob(blob, `${rfc}_diot_${periodo}.txt`);
      toast.success(
        'DIOT generada. Verifica el archivo subiéndolo a la aplicación DIOT del SAT.',
        { id: 'diot-exportar' },
      );
    } catch (e) {
      toast.error(mensajeDeError(e), { id: 'diot-exportar' });
    } finally {
      setBusy(false);
    }
  }

  return (
    <Button
      size="sm"
      onClick={exportar}
      disabled={busy || !habilitado}
      title={
        numErrores > 0
          ? `Corrige ${numErrores} error${numErrores === 1 ? '' : 'es'} antes de generar`
          : undefined
      }
    >
      <Icon
        icon={busy ? 'ph:circle-notch-light' : 'ph:download-simple-light'}
        className={busy ? 'size-4 animate-spin' : 'size-4'}
      />
      Generar TXT
    </Button>
  );
}

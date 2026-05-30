'use client';

import { useCallback } from 'react';
import Link from 'next/link';

import { PageHeading } from '@/components/layout/page-heading';
import { PortalDescargaForm } from '@/components/descarga/portal-descarga-form';
import { PortalDescargasRecientes } from '@/components/descarga/portal-descargas-recientes';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';
import { useServer } from '@/providers/server-provider';
import { useEmpresas } from '@/hooks/use-empresas';
import { useHistorial } from '@/hooks/use-historial';
import { metodoPortalPreferido } from '@/lib/empresa-metodo';

export default function DescargaRapidaPage() {
  const { isConnected } = useServer();
  const { empresas } = useEmpresas();
  const { descargas, refresh: refreshHistorial } = useHistorial();

  // Empresa activa = la marcada como default en el catálogo del agente. Esta
  // página NO permite cambiarla aquí; eso se hace desde /empresas.
  const empresaActiva = empresas.find((e) => e.default);
  const metodo = metodoPortalPreferido(empresaActiva);
  const tieneFiel = !!empresaActiva?.metodos.includes('fiel');

  // Al terminar un job exitoso, refrescamos el historial → la lista
  // `PortalDescargasRecientes` (que consume `descargas` por prop) se actualiza
  // sin recargar la página.
  const onJobDone = useCallback(() => {
    refreshHistorial();
  }, [refreshHistorial]);

  const description = !empresaActiva
    ? 'Selecciona una empresa activa en Empresas para descargar sus CFDIs.'
    : metodo
      ? 'CFDIs directos del portal del SAT, sin esperar al Web Service. Limitada a la cuota diaria del portal.'
      : 'Esta empresa no tiene credenciales registradas.';

  return (
    <div className="space-y-6">
      <PageHeading
        title="Descarga rápida"
        description={description}
        action={
          <Button variant="outline" size="sm" asChild>
            <Link href="/descarga">
              <Icon icon="ph:arrow-left-light" className="size-4" />
              Volver a Descargar CFDIs
            </Link>
          </Button>
        }
      />

      {/* Server not connected */}
      {!isConnected && (
        <Alert variant="destructive">
          <Icon icon="ph:warning-circle-light" className="size-4" />
          <AlertTitle>Servidor no disponible</AlertTitle>
          <AlertDescription>
            No se puede conectar al servidor Python en localhost:8787.
            Asegurate de que este ejecutandose.
          </AlertDescription>
        </Alert>
      )}

      {/* Sin empresa activa o sin credenciales */}
      {isConnected && (!empresaActiva || !metodo) && (
        <Alert>
          <Icon icon="ph:info-light" className="size-4" />
          <AlertTitle>
            {empresaActiva
              ? 'Esta empresa no tiene método de autenticación'
              : 'Sin empresa activa'}
          </AlertTitle>
          <AlertDescription>
            Agrega tu <strong>e.firma</strong> (recomendado — descarga sin captcha) o tu{' '}
            <strong>CIEC</strong> (descarga directa con captcha) en{' '}
            <Link href="/empresas" className="font-medium underline underline-offset-2">
              Empresas
            </Link>
            .
          </AlertDescription>
        </Alert>
      )}

      {/* Caso normal: hay empresa activa con método */}
      {isConnected && empresaActiva && metodo && (
        <>
          {/* CTA recíproco: Web Service para volúmenes grandes (solo aplica a FIEL). */}
          {tieneFiel && (
            <Card className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="space-y-1 text-sm">
                <div className="flex items-center gap-2 font-medium">
                  <Icon icon="ph:cloud-arrow-down-light" className="size-4" />
                  ¿Volúmenes grandes?
                </div>
                <p className="text-xs text-muted-foreground">
                  Descarga masiva por el Web Service oficial con tu e.firma. Sin cuota diaria,
                  pero la solicitud puede tardar 24–72 h en resolverse.
                </p>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href="/descarga">
                  Web Service
                  <Icon icon="ph:arrow-right-light" className="size-4" />
                </Link>
              </Button>
            </Card>
          )}

          <PortalDescargaForm empresa={empresaActiva} onJobDone={onJobDone} />

          <PortalDescargasRecientes rfc={empresaActiva.rfc} descargas={descargas} />
        </>
      )}
    </div>
  );
}

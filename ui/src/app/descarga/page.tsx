'use client';

import { AlertCircleIcon, RotateCcwIcon } from 'lucide-react';

import { PageHeading } from '@/components/layout/page-heading';
import { DescargaForm } from '@/components/descarga/descarga-form';
import { PollingDisplay } from '@/components/descarga/polling-display';
import { PackageList } from '@/components/descarga/package-list';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useServer } from '@/providers/server-provider';
import { useDescarga } from '@/hooks/use-descarga';

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DescargaPage() {
  const { isConnected, fielStatus } = useServer();
  const {
    state,
    requestId,
    codEstado,
    mensaje,
    numeroCfdis,
    packageIds,
    archivosDescargados,
    error,
    solicitar,
    descargar,
    reset,
  } = useDescarga();

  const fielLoaded = fielStatus.loaded;
  const isRequesting = state === 'requesting';
  const showForm = state === 'idle' || state === 'error' || isRequesting;
  const showPolling = state === 'polling' || isRequesting || state === 'ready';
  const showPackages = state === 'ready' || state === 'downloading' || state === 'done';

  return (
    <div className="space-y-6">
      <PageHeading
        title="Descarga Masiva"
        description="Descarga CFDIs (XMLs) del Web Service oficial del SAT usando tu e-firma (FIEL)."
        action={
          state !== 'idle' ? (
            <Button variant="outline" size="sm" onClick={reset}>
              <RotateCcwIcon className="size-4" />
              Nueva solicitud
            </Button>
          ) : undefined
        }
      />

      {/* Server not connected */}
      {!isConnected && (
        <Alert variant="destructive">
          <AlertCircleIcon className="size-4" />
          <AlertTitle>Servidor no disponible</AlertTitle>
          <AlertDescription>
            No se puede conectar al servidor Python en localhost:8787.
            Asegurate de que este ejecutandose.
          </AlertDescription>
        </Alert>
      )}

      {/* FIEL not loaded */}
      {isConnected && !fielLoaded && (
        <Alert>
          <AlertCircleIcon className="size-4" />
          <AlertTitle>e-Firma no cargada</AlertTitle>
          <AlertDescription>
            Debes cargar tu e-firma (FIEL) antes de solicitar una descarga masiva.
            Ve a la seccion de Configuracion para cargar tus archivos .cer y .key.
          </AlertDescription>
        </Alert>
      )}

      {/* Error */}
      {error && (
        <Alert variant="destructive">
          <AlertCircleIcon className="size-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Form */}
      {showForm && (
        <DescargaForm
          onSubmit={solicitar}
          isLoading={isRequesting}
          disabled={!isConnected || !fielLoaded}
        />
      )}

      {/* Polling status */}
      {showPolling && (
        <PollingDisplay
          requestId={requestId}
          codEstado={codEstado}
          mensaje={mensaje}
          numeroCfdis={numeroCfdis}
          isPolling={state === 'polling' || isRequesting}
        />
      )}

      {/* Package list and download */}
      {showPackages && (
        <PackageList
          packageIds={packageIds}
          onDescargar={descargar}
          isDownloading={state === 'downloading'}
          archivosDescargados={archivosDescargados}
        />
      )}
    </div>
  );
}

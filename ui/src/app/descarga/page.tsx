'use client';

import { useCallback, useEffect } from 'react';

import { Icon } from '@/components/ui/icon';

import { PageHeading } from '@/components/layout/page-heading';
import { DescargaForm, type DescargaFormParams } from '@/components/descarga/descarga-form';
import { PollingDisplay } from '@/components/descarga/polling-display';
import { PackageList } from '@/components/descarga/package-list';
import { SolicitudesList } from '@/components/descarga/solicitudes-list';
import { Alert, AlertTitle, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { useServer } from '@/providers/server-provider';
import { useDescarga } from '@/hooks/use-descarga';
import { useSolicitudes } from '@/hooks/use-solicitudes';

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function DescargaPage() {
  const { isConnected, fielStatus, apiClient } = useServer();
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
  const {
    solicitudes,
    loading: loadingSolicitudes,
    refresh: refreshSolicitudes,
  } = useSolicitudes(fielStatus.rfc);

  // Refresca el historial de solicitudes en cada cambio del flujo (nueva solicitud,
  // poll que avanza el estado, descarga completada) para que la lista esté al día.
  useEffect(() => {
    refreshSolicitudes();
  }, [state, codEstado, requestId, refreshSolicitudes]);

  // Expande "Ambos" en dos solicitudes (E + R). Las previas se mandan por el cliente
  // directo (quedan persistidas en el catálogo y aparecen en la lista); la última
  // entra al active flow (polling + auto-descarga) por el hook.
  const handleSubmit = useCallback(
    async (params: DescargaFormParams) => {
      const tipos: ('E' | 'R')[] =
        params.tipo_comprobante === 'A' ? ['E', 'R'] : [params.tipo_comprobante];
      const previas = tipos.slice(0, -1);
      const ultima = tipos[tipos.length - 1];
      // Previas en paralelo, ignorando errores individuales (la lista los reflejará si llegaron).
      await Promise.all(
        previas.map((t) =>
          apiClient
            .solicitar({
              fecha_inicio: params.fecha_inicio,
              fecha_fin: params.fecha_fin,
              tipo_solicitud: params.tipo_solicitud,
              tipo_comprobante: t,
            })
            .catch(() => null),
        ),
      );
      // Última solicitud por el hook → entra al flujo activo (polling + auto-descarga).
      await solicitar({
        fecha_inicio: params.fecha_inicio,
        fecha_fin: params.fecha_fin,
        tipo_solicitud: params.tipo_solicitud,
        tipo_comprobante: ultima,
      });
      refreshSolicitudes();
    },
    [apiClient, solicitar, refreshSolicitudes],
  );

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
              <Icon icon="ph:arrow-counter-clockwise-light" className="size-4" />
              Nueva solicitud
            </Button>
          ) : undefined
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

      {/* FIEL not loaded */}
      {isConnected && !fielLoaded && (
        <Alert>
          <Icon icon="ph:warning-circle-light" className="size-4" />
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
          <Icon icon="ph:warning-circle-light" className="size-4" />
          <AlertTitle>Error</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Form */}
      {showForm && (
        <DescargaForm
          onSubmit={handleSubmit}
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
          numeroCfdis={numeroCfdis}
        />
      )}

      {/* Solicitudes recientes — historial WS de la empresa activa */}
      {fielLoaded && (
        <SolicitudesList
          solicitudes={solicitudes}
          loading={loadingSolicitudes}
        />
      )}
    </div>
  );
}

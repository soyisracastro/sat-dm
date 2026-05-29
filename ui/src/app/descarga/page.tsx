'use client';

import { useCallback, useEffect, useState } from 'react';
import Link from 'next/link';

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
import { useEmpresas } from '@/hooks/use-empresas';

/**
 * Convierte errores técnicos de requests al SAT (timeouts, conexión rota,
 * SSL roto) en mensajes amigables. Para errores no reconocidos devuelve
 * el original.
 */
function traducirError(raw: string | null): string {
  if (!raw) return '';
  if (/timeout|timed out|read timeout|max retries|ConnectionError|EAI_AGAIN|ECONNRESET/i.test(raw)) {
    return 'El SAT no respondió a tiempo. Esto pasa cuando su Web Service está saturado o caído. Inténtalo de nuevo en unos minutos.';
  }
  if (/SSL|certificate/i.test(raw)) {
    return 'Falló la conexión segura con el SAT. Suele ser intermitente — inténtalo de nuevo.';
  }
  return raw;
}

/**
 * Detecta si el mensaje (raw o traducido o envuelto en "No se pudo
 * solicitar X: ...") apunta a un problema del lado del SAT. En ese caso
 * vale la pena sugerir la alternativa CIEC para quien tenga prisa.
 */
function esErrorDelSat(texto: string | null | undefined): boolean {
  if (!texto) return false;
  return /SAT no respondió|conexión segura|saturado|caído|timeout|timed out|max retries|ConnectionError|SSL|certificate/i.test(
    texto,
  );
}

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
  const { empresas } = useEmpresas();
  const empresaActiva = empresas.find((e) => e.rfc === fielStatus.rfc);
  const tieneCiec = !!empresaActiva?.metodos.includes('ciec');

  // Flag de "submit en curso": cubre la ventana entre que el usuario hace
  // click y el hook setea state='requesting'. Antes solo R o E (solo) tenían
  // feedback inmediato porque el hook arrancaba primero; en "Ambos" se
  // disparaba primero la previa via apiClient directo y la UI se quedaba
  // sin cambio durante 5–10s, dando la impresión de que nada pasaba.
  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  // Refresca el historial de solicitudes en cada cambio del flujo (nueva solicitud,
  // poll que avanza el estado, descarga completada) para que la lista esté al día.
  useEffect(() => {
    refreshSolicitudes();
  }, [state, codEstado, requestId, refreshSolicitudes]);

  // Descarga una solicitud desde la lista (sin tocar el active flow): pega directo
  // al agente y refresca para que el estado pase a "Descargada". Sirve cuando el
  // active flow se movió a otra solicitud y dejó atrás una en "Lista", o cuando el
  // usuario quiere re-bajar el ZIP de una ya descargada.
  const handleDescargarFromList = useCallback(
    async (idSolicitud: string) => {
      await apiClient.descargar(idSolicitud);
      refreshSolicitudes();
    },
    [apiClient, refreshSolicitudes],
  );

  // Borra la solicitud del catálogo local. Si era la del flujo activo, reseteamos
  // el hook (no queremos seguir polleando un id que ya no existe).
  const handleEliminarFromList = useCallback(
    async (idSolicitud: string) => {
      if (!fielStatus.rfc) return;
      await apiClient.deleteSolicitud(fielStatus.rfc, idSolicitud);
      if (requestId === idSolicitud) reset();
      refreshSolicitudes();
    },
    [apiClient, fielStatus.rfc, refreshSolicitudes, requestId, reset],
  );

  // Expande "Ambos" en dos solicitudes (E + R). El hook arranca PRIMERO con la
  // "última" (R) para que setState('requesting') aplique de inmediato y el
  // botón se desactive sin esperar al SAT. La "previa" (E) sale en paralelo
  // por apiClient directo; queda en el catálogo y aparece en la lista.
  const handleSubmit = useCallback(
    async (params: DescargaFormParams) => {
      setSubmitError(null);
      setSubmitting(true);
      try {
        const tipos: ('E' | 'R')[] =
          params.tipo_comprobante === 'A' ? ['E', 'R'] : [params.tipo_comprobante];
        const previas = tipos.slice(0, -1);
        const ultima = tipos[tipos.length - 1];

        // 1) Última por el hook (sin await): el setState síncrono del hook se
        //    aplica antes del primer yield → botón se desactiva instantáneo.
        const ultimaPromise = solicitar({
          fecha_inicio: params.fecha_inicio,
          fecha_fin: params.fecha_fin,
          tipo_solicitud: params.tipo_solicitud,
          tipo_comprobante: ultima,
        });

        // 2) Previas por apiClient directo, capturando errores individualmente
        //    para poder mostrarlos en el Alert (no swallowarlos en silencio).
        const previasPromise = Promise.all(
          previas.map(async (t) => {
            try {
              await apiClient.solicitar({
                fecha_inicio: params.fecha_inicio,
                fecha_fin: params.fecha_fin,
                tipo_solicitud: params.tipo_solicitud,
                tipo_comprobante: t,
              });
              return null;
            } catch (e) {
              const msg = e instanceof Error ? e.message : String(e);
              console.warn('[descarga/previa]', t, e);
              return { tipo: t, msg };
            }
          }),
        );

        const [, previasResults] = await Promise.all([ultimaPromise, previasPromise]);
        refreshSolicitudes();

        const previaErrors = previasResults.filter(
          (r): r is { tipo: 'E' | 'R'; msg: string } => r !== null,
        );
        if (previaErrors.length > 0) {
          const tipos = previaErrors
            .map((r) => (r.tipo === 'E' ? 'Emitidos' : 'Recibidos'))
            .join(' y ');
          setSubmitError(
            `No se pudo solicitar ${tipos}: ${traducirError(previaErrors[0].msg)}`,
          );
        }
      } catch (e) {
        const msg = e instanceof Error ? e.message : String(e);
        console.error('[descarga/submit]', e);
        setSubmitError(traducirError(msg));
      } finally {
        setSubmitting(false);
      }
    },
    [apiClient, solicitar, refreshSolicitudes],
  );

  const fielLoaded = fielStatus.loaded;
  const isRequesting = state === 'requesting' || submitting;
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
      {(error || submitError) && (() => {
        const esSat = esErrorDelSat(submitError || error);
        const mensaje = esSat
          ? 'El SAT no está respondiendo como se debe. Inténtalo más tarde.'
          : submitError || traducirError(error);
        return (
          <Alert variant="destructive">
            <Icon icon="ph:warning-circle-light" className="size-4" />
            <AlertTitle>Error</AlertTitle>
            <AlertDescription className="space-y-2">
              <div>{mensaje}</div>
              {esSat && tieneCiec && (
                <div>
                  También puedes descargar con la CIEC (limitada a 500 XML por día).{' '}
                  <Link
                    href="/nueva-descarga"
                    className="font-medium underline underline-offset-2"
                  >
                    Clic aquí
                  </Link>
                  .
                </div>
              )}
            </AlertDescription>
          </Alert>
        );
      })()}

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
          onDescargar={handleDescargarFromList}
          onEliminar={handleEliminarFromList}
        />
      )}
    </div>
  );
}

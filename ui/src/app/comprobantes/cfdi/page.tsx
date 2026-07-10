'use client';

import { useCallback } from 'react';
import Link from 'next/link';
import { toast } from 'sonner';

import { PageHeading } from '@/components/layout/page-heading';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { CfdiCargarMasButton } from '@/components/procesador-cfdi/cfdi-cargar-mas-button';
import { CfdiClearButton } from '@/components/procesador-cfdi/cfdi-clear-button';
import { CfdiDiotCounter } from '@/components/procesador-cfdi/cfdi-diot-counter';
import { CfdiExportButtons } from '@/components/procesador-cfdi/cfdi-export-buttons';
import { CfdiFiltersPanel } from '@/components/procesador-cfdi/cfdi-filters';
import { CfdiReportes } from '@/components/procesador-cfdi/cfdi-reportes';
import { CfdiStats } from '@/components/procesador-cfdi/cfdi-stats';
import { CfdiTable } from '@/components/procesador-cfdi/cfdi-table';
import { CfdiUploader } from '@/components/procesador-cfdi/cfdi-uploader';
import { CfdiValidarButton } from '@/components/procesador-cfdi/cfdi-validar-button';
import { ProcesadorEstado } from '@/components/shared/procesador-estado';
import { ProcesadorSinEmpresa } from '@/components/shared/procesador-sin-empresa';
import { useProcesadorCfdi } from '@/hooks/use-procesador-cfdi';
import { mensajeDeError } from '@/lib/errores';
import type { CfdiFlagsPatch } from '@/lib/types';
import { useServer } from '@/providers/server-provider';

export default function ProcesadorCfdiPage() {
  const {
    filtros,
    setFiltro,
    reset,
    filtrosActivos,
    page,
    setPage,
    pageSize,
    data,
    stats,
    loading,
    error,
    recargar,
    hidratado,
    rfcActivo,
    sinEmpresa,
  } = useProcesadorCfdi();
  const { apiClient } = useServer();

  const total = data?.total ?? 0;
  // Buffer "vacío" = NO hay CFDIs de la empresa en la DB. Si los hay pero los
  // filtros los excluyen, NO es buffer vacío — la tabla muestra "sin resultados"
  // y los filtros siguen visibles para que el usuario los ajuste.
  const bufferVacio = hidratado && stats !== null && stats.total_global === 0;

  // La tabla pinta el cambio optimista; recargar() es la única fuente de
  // verdad después (refresca lista + stats: contador y filtro DIOT activo).
  // En error, la data fresca revierte lo optimista y se avisa con un toast.
  const actualizarFlags = useCallback(
    async (uuid: string, patch: CfdiFlagsPatch) => {
      if (!rfcActivo) return;
      try {
        await apiClient.procesadorActualizarCfdi(rfcActivo, uuid, patch);
      } catch (e) {
        toast.error(`No se pudo actualizar el comprobante: ${mensajeDeError(e)}`);
      } finally {
        recargar();
      }
    },
    [apiClient, rfcActivo, recargar],
  );

  return (
    <div className="space-y-6">
      <PageHeading
        title="Procesador de CFDI"
        description="Carga XMLs, filtra, clasifica deducibilidad y prepara tus facturas para la DIOT."
        action={
          <Button variant="outline" size="sm" asChild>
            <Link href="/comprobantes">
              <Icon icon="ph:arrow-left-light" className="size-4" />
              Comprobantes
            </Link>
          </Button>
        }
      />

      {/* Sin empresa activa el hook no consulta nada: el buffer vive POR empresa. */}
      {sinEmpresa || !rfcActivo ? (
        <ProcesadorSinEmpresa listo={sinEmpresa} />
      ) : (
        <ProcesadorEstado
          stats={stats}
          error={error}
          loading={loading}
          onReintentar={recargar}
        >
          {/* Empty state: buffer vacío → uploader grande, sin filtros ni reportes. */}
          {bufferVacio && <CfdiUploader onCargado={recargar} />}

          {/* Estado normal: hay CFDIs en el buffer de la empresa. */}
          {!bufferVacio && stats !== null && (
            <>
              {/* Acciones */}
              <div className="flex flex-wrap items-center justify-end gap-2">
                <CfdiValidarButton rfc={rfcActivo} onValidado={recargar} />
                <CfdiCargarMasButton onCargado={recargar} />
                <CfdiExportButtons rfc={rfcActivo} filtros={filtros} />
                <CfdiClearButton
                  rfc={rfcActivo}
                  total={stats.total_comprobantes}
                  onBorrado={recargar}
                />
              </div>

              <CfdiStats stats={stats} />

              <CfdiFiltersPanel
                filtros={filtros}
                setFiltro={setFiltro}
                reset={reset}
                filtrosActivos={filtrosActivos}
              />

              <div className="space-y-2">
                <CfdiDiotCounter stats={stats} />
                <CfdiTable
                  data={data}
                  page={page}
                  pageSize={pageSize}
                  loading={loading}
                  onPage={setPage}
                  onFlags={actualizarFlags}
                />
                <div className="flex items-start gap-2 text-xs text-muted-foreground">
                  <Icon icon="ph:info-light" className="mt-0.5 size-4 shrink-0" />
                  <span>
                    Al generar la DIOT solo se incluyen las operaciones con el interruptor
                    activado. Puedes excluir manualmente cualquier comprobante; los
                    complementos de pago no aplican. La generación del TXT vive en la
                    pantalla DIOT.
                  </span>
                </div>
              </div>

              {total > 0 && <CfdiReportes rfc={rfcActivo} filtros={filtros} />}
            </>
          )}
        </ProcesadorEstado>
      )}
    </div>
  );
}

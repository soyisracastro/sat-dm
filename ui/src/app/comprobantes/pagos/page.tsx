'use client';

import Link from 'next/link';

import { PageHeading } from '@/components/layout/page-heading';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { CfdiCargarMasButton } from '@/components/procesador-cfdi/cfdi-cargar-mas-button';
import { CfdiClearButton } from '@/components/procesador-cfdi/cfdi-clear-button';
import { CfdiUploader } from '@/components/procesador-cfdi/cfdi-uploader';
import { CfdiValidarButton } from '@/components/procesador-cfdi/cfdi-validar-button';
import { PagosFiltersPanel } from '@/components/procesador-pagos/pagos-filters';
import { PagosHuerfanosTable } from '@/components/procesador-pagos/pagos-huerfanos-table';
import { PagosIncidenciasPue } from '@/components/procesador-pagos/pagos-incidencias-pue';
import { PagosExportButton } from '@/components/procesador-pagos/pagos-export-button';
import { PagosPPDTable } from '@/components/procesador-pagos/pagos-ppd-table';
import { PagosStatsCards } from '@/components/procesador-pagos/pagos-stats';
import { useProcesadorPagos } from '@/hooks/use-procesador-pagos';

export default function ProcesadorPagosPage() {
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
    recargar,
    hidratado,
  } = useProcesadorPagos();

  // Empty state = no hay facturas PPD ni complementos cargados en el buffer
  // (no es lo mismo que "filtros muy restrictivos" — eso lo maneja la tabla).
  const bufferVacio = hidratado && stats !== null && stats.total_global_ppd === 0;

  return (
    <div className="space-y-6">
      <PageHeading
        title="Procesador de Pagos"
        description="Concilia facturas PPD con sus complementos de pago. Detecta huérfanos, extemporáneos e incidencias PUE."
        action={
          <Button variant="outline" size="sm" asChild>
            <Link href="/comprobantes">
              <Icon icon="ph:arrow-left-light" className="size-4" />
              Comprobantes
            </Link>
          </Button>
        }
      />

      {/* Empty state: usa el mismo CfdiUploader del procesador CFDI. */}
      {bufferVacio && <CfdiUploader onCargado={recargar} />}

      {/* Estado normal: hay PPDs en el buffer. */}
      {!bufferVacio && stats !== null && (
        <>
          <PagosStatsCards stats={stats} />

          <div className="flex flex-wrap items-center justify-end gap-2">
            <CfdiValidarButton onValidado={recargar} />
            <CfdiCargarMasButton onCargado={recargar} />
            <PagosExportButton filtros={filtros} />
            <CfdiClearButton
              onBorrado={recargar}
              descripcion={
                <>
                  Esto vaciará <strong>todo el procesador de comprobantes</strong>: las{' '}
                  {stats.total_global_ppd.toLocaleString('es-MX')} facturas PPD, sus{' '}
                  {stats.total_pagos.toLocaleString('es-MX')} complementos de pago, y los
                  CFDIs cargados en el procesador de CFDI. Los filtros activos también se
                  restablecen. La acción no se puede deshacer.
                </>
              }
            />
          </div>

          <PagosFiltersPanel
            filtros={filtros}
            setFiltro={setFiltro}
            reset={reset}
            filtrosActivos={filtrosActivos}
          />

          <PagosPPDTable
            data={data}
            page={page}
            pageSize={pageSize}
            loading={loading}
            onPage={setPage}
          />

          <PagosIncidenciasPue filtros={filtros} />
          <PagosHuerfanosTable filtros={filtros} />
        </>
      )}
    </div>
  );
}

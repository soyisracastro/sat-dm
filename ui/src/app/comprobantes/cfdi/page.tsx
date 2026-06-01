'use client';

import Link from 'next/link';

import { PageHeading } from '@/components/layout/page-heading';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { CfdiCargarMasButton } from '@/components/procesador-cfdi/cfdi-cargar-mas-button';
import { CfdiClearButton } from '@/components/procesador-cfdi/cfdi-clear-button';
import { CfdiExportButtons } from '@/components/procesador-cfdi/cfdi-export-buttons';
import { CfdiFiltersPanel } from '@/components/procesador-cfdi/cfdi-filters';
import { CfdiReportes } from '@/components/procesador-cfdi/cfdi-reportes';
import { CfdiStats } from '@/components/procesador-cfdi/cfdi-stats';
import { CfdiTable } from '@/components/procesador-cfdi/cfdi-table';
import { CfdiUploader } from '@/components/procesador-cfdi/cfdi-uploader';
import { CfdiValidarButton } from '@/components/procesador-cfdi/cfdi-validar-button';
import { useProcesadorCfdi } from '@/hooks/use-procesador-cfdi';

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
    recargar,
    hidratado,
  } = useProcesadorCfdi();

  const total = data?.total ?? 0;
  // Buffer "vacío" = NO hay CFDIs en la DB del todo. Si los hay pero los filtros
  // los excluyen, NO es buffer vacío — la tabla muestra "sin resultados" y los
  // filtros siguen visibles para que el usuario los ajuste.
  const bufferVacio = hidratado && stats !== null && stats.total_global === 0;

  return (
    <div className="space-y-6">
      <PageHeading
        title="Procesador de CFDI"
        description="Carga XMLs, filtra y genera reportes. Lo cargado se guarda hasta que pulses Borrar."
        action={
          <Button variant="outline" size="sm" asChild>
            <Link href="/comprobantes">
              <Icon icon="ph:arrow-left-light" className="size-4" />
              Comprobantes
            </Link>
          </Button>
        }
      />

      {/* Empty state: buffer vacío → uploader grande, sin filtros ni reportes. */}
      {bufferVacio && <CfdiUploader onCargado={recargar} />}

      {/* Estado normal: hay CFDIs en el buffer. */}
      {!bufferVacio && stats !== null && (
        <>
          {/* Acciones */}
          <div className="flex flex-wrap items-center justify-end gap-2">
            <CfdiValidarButton onValidado={recargar} />
            <CfdiCargarMasButton onCargado={recargar} />
            <CfdiExportButtons filtros={filtros} />
            <CfdiClearButton total={stats.total_comprobantes} onBorrado={recargar} />
          </div>

          <CfdiStats stats={stats} />

          <CfdiFiltersPanel
            filtros={filtros}
            setFiltro={setFiltro}
            reset={reset}
            filtrosActivos={filtrosActivos}
          />

          <CfdiTable
            data={data}
            page={page}
            pageSize={pageSize}
            loading={loading}
            onPage={setPage}
          />

          {total > 0 && <CfdiReportes filtros={filtros} />}
        </>
      )}
    </div>
  );
}

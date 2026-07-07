'use client';

import { useState } from 'react';

import { PageHeading } from '@/components/layout/page-heading';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Icon } from '@/components/ui/icon';
import { CargarXmlDialog } from '@/components/diot/cargar-xml-dialog';
import { ExportTxtButton } from '@/components/diot/export-txt-button';
import { SelectorPeriodo } from '@/components/diot/selector-periodo';
import { TablaDiot } from '@/components/diot/tabla-diot';
import { ProcesadorSinEmpresa } from '@/components/shared/procesador-sin-empresa';
import { useDiot } from '@/hooks/use-diot';

export default function DiotPage() {
  const {
    rfcActivo,
    periodo,
    setPeriodo,
    filas,
    errores,
    advertencias,
    origen,
    resumen,
    catalogos,
    cargando,
    guardando,
    prellenando,
    setCampo,
    agregarFila,
    eliminarFila,
    prellenar,
  } = useDiot();

  const [confirmarPrellenado, setConfirmarPrellenado] = useState(false);

  // Re-prellenar pisa los renglones de origen CFDI. Si el último guardado fue
  // una edición manual, se confirma antes (los agregados a mano sobreviven).
  const prellenarConConfirmacion = () => {
    if (origen === 'manual' && filas.length > 0) setConfirmarPrellenado(true);
    else void prellenar();
  };

  const sinEstado = !cargando && filas.length === 0;

  return (
    <div className="space-y-6">
      <PageHeading
        title="DIOT"
        description="Declaración Informativa de Operaciones con Terceros: prellena desde tus CFDIs, ajusta y genera el TXT de carga masiva."
      />

      {!rfcActivo ? (
        <ProcesadorSinEmpresa listo={!cargando} />
      ) : (
        <>
          {/* Barra de acciones */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <SelectorPeriodo periodo={periodo} onChange={setPeriodo} disabled={cargando} />
            <div className="flex flex-wrap items-center gap-2">
              {guardando && (
                <span className="text-xs text-muted-foreground">Guardando…</span>
              )}
              <Button
                variant="outline"
                size="sm"
                onClick={prellenarConConfirmacion}
                disabled={cargando || prellenando}
              >
                <Icon
                  icon={prellenando ? 'ph:circle-notch-light' : 'ph:sparkle-light'}
                  className={prellenando ? 'size-4 animate-spin' : 'size-4'}
                />
                Prellenar desde comprobantes
              </Button>
              <CargarXmlDialog onCargado={() => void prellenar()} />
              <Button variant="outline" size="sm" onClick={agregarFila} disabled={cargando}>
                <Icon icon="ph:plus-light" className="size-4" />
                Agregar proveedor
              </Button>
              <ExportTxtButton
                rfc={rfcActivo}
                periodo={periodo}
                habilitado={filas.length > 0 && errores.length === 0}
                numErrores={errores.length}
              />
            </div>
          </div>

          {/* Avisos */}
          {(resumen?.cfdis_sin_desglose ?? 0) > 0 && (
            <Alert variant="warning">
              <Icon icon="ph:warning-light" className="size-4" />
              <AlertTitle>Bases estimadas</AlertTitle>
              <AlertDescription>
                {resumen!.cfdis_sin_desglose} CFDIs se cargaron con una versión anterior de la
                app y no traen el desglose de IVA por tasa: la base al 16% se estimó desde el
                IVA. Vuelve a cargar esos XMLs en Comprobantes para el dato exacto.
              </AlertDescription>
            </Alert>
          )}
          {errores.length > 0 && (
            <Alert variant="destructive">
              <Icon icon="ph:warning-circle-light" className="size-4" />
              <AlertTitle>
                {errores.length} error{errores.length === 1 ? '' : 'es'} que bloquean el TXT
              </AlertTitle>
              <AlertDescription>
                <ul className="list-disc pl-4">
                  {errores.slice(0, 6).map((e, i) => (
                    <li key={i}>{e.mensaje}</li>
                  ))}
                  {errores.length > 6 && <li>… y {errores.length - 6} más</li>}
                </ul>
              </AlertDescription>
            </Alert>
          )}

          {/* Tabla o empty-state */}
          {sinEstado ? (
            <div className="rounded-lg border border-dashed p-10 text-center">
              <Icon
                icon="ph:file-text-light"
                className="mx-auto size-10 text-muted-foreground"
              />
              <h3 className="mt-3 text-sm font-medium">Sin renglones para este periodo</h3>
              <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground">
                Prellena desde los CFDIs recibidos que ya cargaste en Comprobantes, sube XMLs
                aquí mismo, o captura los proveedores a mano.
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                <Button size="sm" onClick={() => void prellenar()} disabled={prellenando}>
                  <Icon
                    icon={prellenando ? 'ph:circle-notch-light' : 'ph:sparkle-light'}
                    className={prellenando ? 'size-4 animate-spin' : 'size-4'}
                  />
                  Prellenar desde comprobantes
                </Button>
                <CargarXmlDialog onCargado={() => void prellenar()} />
              </div>
            </div>
          ) : (
            !cargando && (
              <>
                <TablaDiot
                  filas={filas}
                  catalogos={catalogos}
                  errores={errores}
                  advertencias={advertencias}
                  onCampo={setCampo}
                  onEliminar={eliminarFila}
                />
                <p className="text-xs text-muted-foreground">
                  Criterio del prellenado: CFDIs recibidos emitidos en el periodo (las notas de
                  crédito van a devoluciones). Todo es editable antes de generar el TXT;
                  verifica el archivo subiéndolo a la aplicación DIOT del SAT.
                </p>
              </>
            )
          )}

          {/* Confirmación de re-prellenado sobre ediciones manuales */}
          <Dialog open={confirmarPrellenado} onOpenChange={setConfirmarPrellenado}>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>¿Volver a prellenar el periodo?</DialogTitle>
                <DialogDescription>
                  Los renglones prellenados desde CFDIs se regenerarán y tus ajustes sobre
                  ellos se perderán. Los proveedores que agregaste a mano se conservan.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setConfirmarPrellenado(false)}>
                  Cancelar
                </Button>
                <Button
                  onClick={() => {
                    setConfirmarPrellenado(false);
                    void prellenar();
                  }}
                >
                  Prellenar
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </>
      )}
    </div>
  );
}

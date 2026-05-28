'use client';

import { useState } from 'react';

import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PackageListProps {
  packageIds: string[];
  onDescargar: () => void;
  isDownloading: boolean;
  archivosDescargados: string[];
  /** CFDIs encontrados (para el resumen: "N CFDIs en M paquetes"). */
  numeroCfdis?: number | null;
}

// Máximo de archivos a renderizar en la lista (una descarga grande puede traer miles).
const MAX_ARCHIVOS_VISIBLES = 200;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PackageList({
  packageIds,
  onDescargar,
  isDownloading,
  archivosDescargados,
  numeroCfdis,
}: PackageListProps) {
  const [verIds, setVerIds] = useState(false);

  const hasPaquetes = packageIds.length > 0;
  const hasArchivos = archivosDescargados.length > 0;

  if (!hasPaquetes && !hasArchivos) return null;

  const nPaquetes = packageIds.length;
  const plural = nPaquetes !== 1;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Icon icon="ph:package-light" className="size-5" />
          {hasArchivos ? 'Descarga completada' : 'Paquetes disponibles'}
        </CardTitle>
        {!hasArchivos && (
          <CardDescription>
            {numeroCfdis != null && numeroCfdis > 0
              ? `${numeroCfdis.toLocaleString('es-MX')} CFDIs en ${nPaquetes} paquete${plural ? 's' : ''}. `
              : `${nPaquetes} paquete${plural ? 's' : ''} listo${plural ? 's' : ''}. `}
            El SAT divide la descarga en varios paquetes; se descargan todos juntos.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Paquetes listos: acción primero (siempre visible), IDs colapsados */}
        {hasPaquetes && !hasArchivos && (
          <>
            <Button
              onClick={onDescargar}
              disabled={isDownloading}
              className="w-full sm:w-auto"
            >
              {isDownloading ? (
                <>
                  <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
                  Descargando...
                </>
              ) : (
                <>
                  <Icon icon="ph:download-simple-light" className="size-4" />
                  Descargar Todo ({nPaquetes})
                </>
              )}
            </Button>

            <div className="space-y-2">
              <button
                type="button"
                onClick={() => setVerIds((v) => !v)}
                className="flex items-center gap-1 text-sm font-medium text-muted-foreground hover:text-foreground"
              >
                <Icon
                  icon="ph:caret-right-light"
                  className={cn('size-4 transition-transform', verIds && 'rotate-90')}
                />
                {verIds ? 'Ocultar' : 'Ver'} IDs de paquetes ({nPaquetes})
              </button>
              {verIds && (
                <ScrollArea className="h-48 rounded-md border">
                  <div className="space-y-1 p-2">
                    {packageIds.map((id) => (
                      <div
                        key={id}
                        className="flex items-center gap-2 rounded bg-muted px-3 py-1.5"
                      >
                        <Icon icon="ph:package-light" className="size-3.5 shrink-0 text-muted-foreground" />
                        <code className="truncate font-mono text-xs">{id}</code>
                      </div>
                    ))}
                  </div>
                </ScrollArea>
              )}
            </div>
          </>
        )}

        {/* Downloaded files */}
        {hasArchivos && (
          <>
            <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 dark:border-green-900 dark:bg-green-950/30">
              <div className="flex items-center gap-2">
                <Icon icon="ph:check-circle-light" className="size-4 text-green-600 dark:text-green-400" />
                <p className="text-sm font-medium text-green-800 dark:text-green-300">
                  Se descargaron {archivosDescargados.length.toLocaleString('es-MX')} archivo
                  {archivosDescargados.length !== 1 ? 's' : ''} exitosamente.
                </p>
              </div>
            </div>

            <Separator />

            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">
                Archivos descargados
              </p>
              <ScrollArea className="h-60 rounded-md border">
                <div className="space-y-1 p-2">
                  {archivosDescargados.slice(0, MAX_ARCHIVOS_VISIBLES).map((archivo) => (
                    <div
                      key={archivo}
                      className="flex items-center gap-2 rounded px-3 py-1.5 text-sm hover:bg-muted"
                    >
                      <Icon icon="ph:file-light" className="size-3.5 shrink-0 text-muted-foreground" />
                      <span className="truncate font-mono text-xs">{archivo}</span>
                      <Badge variant="secondary" className="ml-auto shrink-0 text-[10px]">
                        XML
                      </Badge>
                    </div>
                  ))}
                  {archivosDescargados.length > MAX_ARCHIVOS_VISIBLES && (
                    <p className="px-3 py-2 text-xs text-muted-foreground">
                      … y {(archivosDescargados.length - MAX_ARCHIVOS_VISIBLES).toLocaleString('es-MX')} archivo
                      {archivosDescargados.length - MAX_ARCHIVOS_VISIBLES !== 1 ? 's' : ''} más.
                    </p>
                  )}
                </div>
              </ScrollArea>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

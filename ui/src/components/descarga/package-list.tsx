'use client';

import {
  DownloadIcon,
  PackageIcon,
  FileIcon,
  CheckCircle2Icon,
  Loader2Icon,
} from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Separator } from '@/components/ui/separator';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PackageListProps {
  packageIds: string[];
  onDescargar: () => void;
  isDownloading: boolean;
  archivosDescargados: string[];
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PackageList({
  packageIds,
  onDescargar,
  isDownloading,
  archivosDescargados,
}: PackageListProps) {
  const hasPaquetes = packageIds.length > 0;
  const hasArchivos = archivosDescargados.length > 0;

  if (!hasPaquetes && !hasArchivos) return null;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <PackageIcon className="size-5" />
          {hasArchivos ? 'Descarga completada' : 'Paquetes disponibles'}
        </CardTitle>
        {!hasArchivos && (
          <CardDescription>
            {packageIds.length} paquete{packageIds.length !== 1 ? 's' : ''} listo
            {packageIds.length !== 1 ? 's' : ''} para descargar.
          </CardDescription>
        )}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Package IDs */}
        {hasPaquetes && !hasArchivos && (
          <>
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">
                IDs de paquetes
              </p>
              <ScrollArea className="max-h-40">
                <div className="space-y-1">
                  {packageIds.map((id) => (
                    <div
                      key={id}
                      className="flex items-center gap-2 rounded bg-muted px-3 py-1.5"
                    >
                      <PackageIcon className="size-3.5 shrink-0 text-muted-foreground" />
                      <code className="font-mono text-xs">{id}</code>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>

            <Button
              onClick={onDescargar}
              disabled={isDownloading}
              className="w-full sm:w-auto"
            >
              {isDownloading ? (
                <>
                  <Loader2Icon className="size-4 animate-spin" />
                  Descargando...
                </>
              ) : (
                <>
                  <DownloadIcon className="size-4" />
                  Descargar Todo
                </>
              )}
            </Button>
          </>
        )}

        {/* Downloaded files */}
        {hasArchivos && (
          <>
            <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 dark:border-green-900 dark:bg-green-950/30">
              <div className="flex items-center gap-2">
                <CheckCircle2Icon className="size-4 text-green-600 dark:text-green-400" />
                <p className="text-sm font-medium text-green-800 dark:text-green-300">
                  Se descargaron {archivosDescargados.length} archivo
                  {archivosDescargados.length !== 1 ? 's' : ''} exitosamente.
                </p>
              </div>
            </div>

            <Separator />

            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">
                Archivos descargados
              </p>
              <ScrollArea className="max-h-60">
                <div className="space-y-1">
                  {archivosDescargados.map((archivo) => (
                    <div
                      key={archivo}
                      className="flex items-center gap-2 rounded px-3 py-1.5 text-sm hover:bg-muted"
                    >
                      <FileIcon className="size-3.5 shrink-0 text-muted-foreground" />
                      <span className="truncate font-mono text-xs">{archivo}</span>
                      <Badge variant="secondary" className="ml-auto shrink-0 text-[10px]">
                        XML
                      </Badge>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}

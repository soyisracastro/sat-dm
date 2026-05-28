'use client';

import { useCallback } from 'react';

import { Badge } from '@/components/ui/badge';
import { Icon } from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { COD_ESTADO_LABELS } from '@/lib/constants';
import { formatNumber } from '@/lib/formatting';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface PollingDisplayProps {
  requestId: string | null;
  codEstado: number | null;
  mensaje: string | null;
  numeroCfdis: number | null;
  isPolling: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function PollingDisplay({
  requestId,
  codEstado,
  mensaje,
  numeroCfdis,
  isPolling,
}: PollingDisplayProps) {
  const handleCopy = useCallback(() => {
    if (requestId) {
      navigator.clipboard.writeText(requestId);
    }
  }, [requestId]);

  if (!requestId) return null;

  const estadoInfo = codEstado !== null ? COD_ESTADO_LABELS.get(codEstado) : null;
  const isReady = codEstado === 3;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          {isPolling ? (
            <Icon icon="ph:circle-notch-light" className="size-5 animate-spin text-blue-500" />
          ) : isReady ? (
            <Icon icon="ph:check-circle-light" className="size-5 text-green-500" />
          ) : (
            <Icon icon="ph:file-text-light" className="size-5" />
          )}
          Estado de la solicitud
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Request ID */}
        <div className="space-y-1">
          <p className="text-sm font-medium text-muted-foreground">ID de Solicitud</p>
          <div className="flex items-center gap-2">
            <code className="rounded bg-muted px-2 py-1 font-mono text-sm">
              {requestId}
            </code>
            <Button
              variant="ghost"
              size="icon-xs"
              onClick={handleCopy}
              title="Copiar al portapapeles"
            >
              <Icon icon="ph:clipboard-text-light" className="size-3.5" />
            </Button>
          </div>
        </div>

        {/* Estado badge */}
        {estadoInfo && (
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">Estado</p>
            <div className="flex items-center gap-3">
              <Badge className={estadoInfo.color}>
                {estadoInfo.label}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {estadoInfo.description}
              </span>
            </div>
          </div>
        )}

        {/* Mensaje from SAT */}
        {mensaje && (
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">Mensaje</p>
            <p className="text-sm">{mensaje}</p>
          </div>
        )}

        {/* Numero de CFDIs */}
        {numeroCfdis !== null && numeroCfdis > 0 && (
          <div className="space-y-1">
            <p className="text-sm font-medium text-muted-foreground">CFDIs encontrados</p>
            <p className="text-lg font-semibold">{formatNumber(numeroCfdis)}</p>
          </div>
        )}

        {/* Ready message */}
        {isReady && (
          <div className="rounded-md border border-green-200 bg-green-50 px-4 py-3 dark:border-green-900 dark:bg-green-950/30">
            <p className="text-sm font-medium text-green-800 dark:text-green-300">
              Los paquetes estan listos para descargar.
            </p>
          </div>
        )}

        {/* Polling indicator */}
        {isPolling && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Icon icon="ph:circle-notch-light" className="size-3.5 animate-spin" />
            Verificando estado... (consulta automatica cada 15 segundos)
          </div>
        )}
      </CardContent>
    </Card>
  );
}

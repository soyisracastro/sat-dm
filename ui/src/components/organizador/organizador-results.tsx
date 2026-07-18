'use client';

import { useState } from 'react';

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import type { OrganizadorResult, DeduplicarResult } from '@/lib/types';
import { formatNumber } from '@/lib/formatting';

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface OrganizadorResultsProps {
  result: OrganizadorResult | DeduplicarResult | null;
}

// ---------------------------------------------------------------------------
// Type guard
// ---------------------------------------------------------------------------

function isDeduplicarResult(
  r: OrganizadorResult | DeduplicarResult,
): r is DeduplicarResult {
  return 'duplicados_encontrados' in r;
}

// ---------------------------------------------------------------------------
// Stat card
// ---------------------------------------------------------------------------

function StatCard({ label, value }: { label: string; value: number }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center justify-center py-4">
        <span className="text-2xl font-bold">{formatNumber(value)}</span>
        <span className="mt-1 text-xs text-muted-foreground">{label}</span>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export function OrganizadorResults({ result }: OrganizadorResultsProps) {
  const [errorsExpanded, setErrorsExpanded] = useState(false);

  if (!result) return null;

  const errores = result.errores ?? [];
  const deOtroRfc = !isDeduplicarResult(result) ? (result.de_otro_rfc ?? 0) : 0;

  return (
    <div className="space-y-4">
      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
        {isDeduplicarResult(result) ? (
          <>
            <StatCard label="Archivos analizados" value={result.archivos_analizados} />
            <StatCard label="Duplicados encontrados" value={result.duplicados_encontrados} />
            <StatCard label="Duplicados eliminados" value={result.duplicados_eliminados} />
          </>
        ) : (
          <>
            <StatCard label="Archivos procesados" value={result.archivos_procesados} />
            <StatCard label="Archivos movidos" value={result.archivos_movidos} />
            <StatCard label="Archivos omitidos" value={result.archivos_omitidos} />
          </>
        )}
      </div>

      {deOtroRfc > 0 && (
        <p className="text-xs text-muted-foreground">
          {formatNumber(deOtroRfc)} factura{deOtroRfc !== 1 ? 's' : ''} de otros
          RFC se quedaron en su lugar. Para organizarlas, activa la empresa a la
          que pertenecen y vuelve a correr el organizador.
        </p>
      )}

      {/* Errors */}
      {errores.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <div className="flex items-center justify-between">
              <CardTitle className="text-sm text-destructive">
                {errores.length} error{errores.length !== 1 ? 'es' : ''}
              </CardTitle>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setErrorsExpanded((v) => !v)}
              >
                {errorsExpanded ? 'Ocultar' : 'Mostrar'}
              </Button>
            </div>
          </CardHeader>
          {errorsExpanded && (
            <CardContent>
              <ul className="max-h-60 space-y-1 overflow-auto text-xs text-muted-foreground">
                {errores.map((err, i) => (
                  <li key={i} className="rounded bg-muted px-2 py-1 font-mono">
                    {err}
                  </li>
                ))}
              </ul>
            </CardContent>
          )}
        </Card>
      )}
    </div>
  );
}

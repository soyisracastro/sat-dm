'use client';

import { PageHeading } from '@/components/layout/page-heading';
import { ValidacionInput } from '@/components/validacion/validacion-input';
import { ValidacionProgress } from '@/components/validacion/validacion-progress';
import { ValidacionSummaryBadges } from '@/components/validacion/validacion-summary';
import { ValidacionResults } from '@/components/validacion/validacion-results';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useValidacion } from '@/hooks/use-validacion';
import type { CfdiValidarInput } from '@/lib/types';

export default function ValidacionPage() {
  const {
    validate,
    isValidating,
    progress,
    results,
    summary,
    exportCsv,
    reset,
  } = useValidacion();

  const handleValidar = (cfdis: CfdiValidarInput[]) => {
    validate(cfdis);
  };

  return (
    <div className="space-y-6">
      <PageHeading
        title="Validacion CFDI"
        description="Consulta el estado de tus CFDIs en el servicio publico del SAT."
        action={
          results.length > 0 ? (
            <button
              onClick={reset}
              className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            >
              Nueva consulta
            </button>
          ) : undefined
        }
      />

      <Alert>
        <AlertDescription>
          No requiere e-firma — usa el servicio publico del SAT.
        </AlertDescription>
      </Alert>

      {/* Input phase */}
      {!isValidating && results.length === 0 && (
        <ValidacionInput onValidar={handleValidar} isValidating={isValidating} />
      )}

      {/* Validating phase */}
      {isValidating && (
        <ValidacionProgress progress={progress} total={results.length > 0 ? results.length : 0} />
      )}

      {/* Results phase */}
      {summary && <ValidacionSummaryBadges summary={summary} />}

      {results.length > 0 && (
        <ValidacionResults results={results} onExportCsv={exportCsv} />
      )}
    </div>
  );
}

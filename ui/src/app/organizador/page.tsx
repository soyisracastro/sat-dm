'use client';

import { PageHeading } from '@/components/layout/page-heading';
import { OrganizadorForm } from '@/components/organizador/organizador-form';
import { OrganizadorResults } from '@/components/organizador/organizador-results';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useOrganizador } from '@/hooks/use-organizador';

export default function OrganizadorPage() {
  const { organizar, renombrar, deduplicar, result, isLoading, error, reset } =
    useOrganizador();

  return (
    <div className="space-y-6">
      <PageHeading
        title="Organizador de CFDIs"
        description="Organiza, renombra y deduplica archivos XML de CFDIs."
        action={
          result ? (
            <button
              onClick={reset}
              className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            >
              Nueva operacion
            </button>
          ) : undefined
        }
      />

      <Alert>
        <AlertDescription>
          No requiere e.firma. Las rutas son relativas al servidor Python.
        </AlertDescription>
      </Alert>

      <OrganizadorForm
        onOrganizar={organizar}
        onRenombrar={renombrar}
        onDeduplicar={deduplicar}
        isLoading={isLoading}
      />

      {error && (
        <div className="rounded-md border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive">
          {error}
        </div>
      )}

      <OrganizadorResults result={result} />
    </div>
  );
}

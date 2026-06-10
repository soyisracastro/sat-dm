'use client';

import { PageHeading } from '@/components/layout/page-heading';
import { OrganizadorForm } from '@/components/organizador/organizador-form';
import { OrganizadorResults } from '@/components/organizador/organizador-results';
import { useOrganizador } from '@/hooks/use-organizador';

export default function OrganizadorPage() {
  const { organizar, renombrar, deduplicar, result, isLoading, error, reset } =
    useOrganizador();

  return (
    <div className="space-y-6">
      <PageHeading
        title="Organizador de archivos"
        description="Ordena en carpetas, renombra y quita duplicados de las facturas que descargaste."
        action={
          result ? (
            <button
              onClick={reset}
              className="text-sm text-muted-foreground underline-offset-4 hover:underline"
            >
              Nueva operación
            </button>
          ) : undefined
        }
      />

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

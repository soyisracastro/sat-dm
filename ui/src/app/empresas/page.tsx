'use client';

import { useState } from 'react';
import Link from 'next/link';

import { useEmpresas } from '@/hooks/use-empresas';
import { PageHeading } from '@/components/layout/page-heading';
import { EmpresaAddDialog } from '@/components/empresas/empresa-add-dialog';
import { EmpresaStatusGroup } from '@/components/empresas/empresa-status-group';
import { EmpresaRowExpanded } from '@/components/empresas/empresa-row-expanded';
import {
  ResourceList,
  type ResourceListColumn,
} from '@/components/shared/resource-list';
import { Icon } from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { cn } from '@/lib/utils';
import type { Empresa } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

type Confirmacion = 'archive' | 'unarchive' | 'delete';

export default function EmpresasPage() {
  const {
    empresas,
    loading,
    error,
    refresh,
    addFiel,
    addCiec,
    remove,
    seleccionar,
    archive,
    unarchive,
  } = useEmpresas();
  const [addOpen, setAddOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [accionError, setAccionError] = useState<string | null>(null);

  async function withBusy(rfc: string, fn: () => Promise<void>) {
    setBusy(rfc);
    setAccionError(null);
    try {
      await fn();
    } catch (e) {
      setAccionError(mensajeDeError(e));
    } finally {
      setBusy(null);
    }
  }

  const activas = empresas.filter((e) => !e.archived_at);
  const archivadas = empresas.filter((e) => !!e.archived_at);
  const activeRfc = activas.find((e) => e.default)?.rfc ?? null;

  const columnas: ResourceListColumn<Empresa>[] = [
    {
      key: 'rfc',
      header: 'RFC',
      width: 'w-40',
      render: (e) => (
        <span className="font-mono text-xs font-medium">{e.rfc}</span>
      ),
    },
    {
      key: 'nombre',
      header: 'Nombre',
      hideOnMobile: true,
      render: (e) => (
        <span className="truncate text-sm text-muted-foreground">{e.nombre}</span>
      ),
    },
    {
      key: 'estado',
      header: 'Estado',
      width: 'w-48',
      render: (e) => <EmpresaStatusGroup empresa={e} />,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeading
        title={
          activas.length > 0
            ? `${activas.length} RFC${activas.length === 1 ? '' : 's'} configurados`
            : 'Empresas'
        }
        description="Cada empresa guarda su método de autenticación localmente. La e.firma nunca sale de tu computadora."
        action={
          <Button onClick={() => setAddOpen(true)}>
            <Icon icon="ph:plus-light" className="size-4" /> Agregar empresa
          </Button>
        }
      />

      {(error || accionError) && (
        <Alert variant="destructive">
          <AlertDescription>{accionError || error}</AlertDescription>
        </Alert>
      )}

      {loading && empresas.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" /> Cargando empresas…
        </div>
      ) : empresas.length === 0 ? (
        <EmptyState onAdd={() => setAddOpen(true)} />
      ) : (
        <>
          {activas.length > 0 && (
            <ResourceList
              items={activas}
              getKey={(e) => e.rfc}
              activeId={activeRfc}
              onRowClick={(e) =>
                withBusy(e.rfc, () => seleccionar(e.rfc, e.metodos))
              }
              columns={columnas}
              actionsHeader="Acciones"
              actions={(e) => (
                <EmpresaRowActions
                  empresa={e}
                  archived={false}
                  busy={busy === e.rfc}
                  onArchive={() => withBusy(e.rfc, () => archive(e.rfc))}
                  onDelete={() => withBusy(e.rfc, () => remove(e.rfc))}
                />
              )}
              expandable={{
                render: (e) => (
                  <EmpresaRowExpanded empresa={e} onJobDone={refresh} />
                ),
              }}
            />
          )}

          {archivadas.length > 0 && (
            <details className="group rounded-lg border border-border bg-card">
              <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
                <Icon
                  icon="ph:caret-right-light"
                  className="size-4 transition-transform group-open:rotate-90"
                />
                <span>Empresas archivadas</span>
                <Badge variant="secondary">{archivadas.length}</Badge>
              </summary>
              <div className="border-t border-border p-3">
                <ResourceList
                  items={archivadas}
                  getKey={(e) => e.rfc}
                  columns={columnas}
                  dimmed
                  actionsHeader="Acciones"
                  actions={(e) => (
                    <EmpresaRowActions
                      empresa={e}
                      archived
                      busy={busy === e.rfc}
                      onUnarchive={() => withBusy(e.rfc, () => unarchive(e.rfc))}
                      onDelete={() => withBusy(e.rfc, () => remove(e.rfc))}
                    />
                  )}
                  expandable={{
                    render: (e) => (
                      <EmpresaRowExpanded empresa={e} onJobDone={refresh} />
                    ),
                  }}
                />
              </div>
            </details>
          )}
        </>
      )}

      <div className="flex items-center gap-2 rounded-lg border bg-secondary px-4 py-3 text-xs text-muted-foreground">
        <Icon icon="ph:lock-light" className="size-4 shrink-0" />
        <span>
          Las contraseñas de tu e.firma y CIEC se guardan en el{' '}
          <span className="font-medium text-foreground">keychain del sistema</span>{' '}
          (Keychain en macOS, Credential Manager en Windows), nunca en texto plano.
        </span>
      </div>

      <EmpresaAddDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        addFiel={addFiel}
        addCiec={addCiec}
      />
    </div>
  );
}

function EmptyState({ onAdd }: { onAdd: () => void }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-lg border border-border bg-card p-10 text-center">
      <Icon icon="ph:buildings-light" className="size-8 text-muted-foreground" />
      <div className="space-y-1">
        <p className="font-medium">Aún no tienes empresas</p>
        <p className="text-sm text-muted-foreground">
          Registra tu primera empresa (e.firma o CIEC) para empezar a descargar.
        </p>
      </div>
      <Button onClick={onAdd}>
        <Icon icon="ph:plus-light" className="size-4" /> Agregar empresa
      </Button>
    </div>
  );
}

interface EmpresaRowActionsProps {
  empresa: Empresa;
  archived: boolean;
  busy: boolean;
  onArchive?: () => void;
  onUnarchive?: () => void;
  onDelete: () => void;
}

function EmpresaRowActions({
  empresa,
  archived,
  busy,
  onArchive,
  onUnarchive,
  onDelete,
}: EmpresaRowActionsProps) {
  const [confirm, setConfirm] = useState<Confirmacion | null>(null);

  function ejecutar() {
    if (confirm === 'archive') onArchive?.();
    else if (confirm === 'unarchive') onUnarchive?.();
    else if (confirm === 'delete') onDelete();
    setConfirm(null);
  }

  return (
    <div className="inline-flex items-center gap-1">
      {!archived ? (
        <>
          <Button
            asChild
            variant="ghost"
            size="icon"
            title="Configurar empresa"
          >
            <Link href={`/empresas/detalle?rfc=${encodeURIComponent(empresa.rfc)}`}>
              <Icon icon="ph:gear-light" className="size-4" />
            </Link>
          </Button>
          <Button
            variant="ghost"
            size="icon"
            disabled={busy}
            onClick={() => setConfirm('archive')}
            title="Archivar"
          >
            <Icon icon="ph:archive-light" className="size-4" />
          </Button>
        </>
      ) : (
        <Button
          variant="ghost"
          size="icon"
          disabled={busy}
          onClick={() => setConfirm('unarchive')}
          title="Desarchivar"
        >
          <Icon
            icon="ph:archive-tray-light"
            className={cn('size-4 text-blue-500')}
          />
        </Button>
      )}
      <Button
        variant="ghost"
        size="icon"
        disabled={busy}
        onClick={() => setConfirm('delete')}
        title="Eliminar"
      >
        <Icon icon="ph:trash-light" className="size-4" />
      </Button>

      <Dialog
        open={confirm !== null}
        onOpenChange={(o) => !o && setConfirm(null)}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirm === 'delete'
                ? 'Eliminar empresa'
                : confirm === 'archive'
                  ? 'Archivar empresa'
                  : 'Desarchivar empresa'}
            </DialogTitle>
            <DialogDescription>
              {confirm === 'delete'
                ? `Esto borrará "${empresa.nombre}" del catálogo y sus credenciales del keychain del sistema. Los archivos descargados no se borran.`
                : confirm === 'archive'
                  ? `"${empresa.nombre}" se ocultará de la lista principal. Podrás desarchivarla cuando la necesites.`
                  : `"${empresa.nombre}" volverá a la lista principal.`}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirm(null)}>
              Cancelar
            </Button>
            <Button
              variant={confirm === 'delete' ? 'destructive' : 'default'}
              onClick={ejecutar}
            >
              {confirm === 'delete'
                ? 'Eliminar'
                : confirm === 'archive'
                  ? 'Archivar'
                  : 'Desarchivar'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

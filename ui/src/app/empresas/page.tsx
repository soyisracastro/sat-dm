'use client';

import { useState } from 'react';
import Link from 'next/link';
import { Building2, KeyRound, Loader2, Lock, Pencil, Plus, ShieldCheck, Trash2 } from 'lucide-react';

import { useEmpresas } from '@/hooks/use-empresas';
import { PageHeading } from '@/components/layout/page-heading';
import { EmpresaAddDialog } from '@/components/empresas/empresa-add-dialog';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Card } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import type { Empresa } from '@/lib/types';

const AVATAR_COLORS = ['#0B5FFF', '#059669', '#B45309', '#7C3AED', '#0848CC', '#0E7490'];

function iniciales(nombre: string): string {
  const parts = nombre.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '??';
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

function colorDe(rfc: string): string {
  let h = 0;
  for (const c of rfc) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return AVATAR_COLORS[h % AVATAR_COLORS.length];
}

export default function EmpresasPage() {
  const { empresas, loading, error, addFiel, addCiec, remove, seleccionar } = useEmpresas();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState<string | null>(null); // rfc en proceso

  async function withBusy(rfc: string, fn: () => Promise<void>) {
    setBusy(rfc);
    try {
      await fn();
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeading
        title={
          empresas.length > 0
            ? `${empresas.length} RFC${empresas.length === 1 ? '' : 's'} configurados`
            : 'Empresas'
        }
        description="Cada empresa guarda su método de autenticación localmente. La e.firma nunca sale de tu computadora."
        action={
          <Button onClick={() => setOpen(true)}>
            <Plus className="size-4" /> Agregar empresa
          </Button>
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading && empresas.length === 0 ? (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Cargando empresas…
        </div>
      ) : empresas.length === 0 ? (
        <Card className="flex flex-col items-center gap-3 p-10 text-center">
          <Building2 className="size-8 text-muted-foreground" />
          <div className="space-y-1">
            <p className="font-medium">Aún no tienes empresas</p>
            <p className="text-sm text-muted-foreground">
              Registra tu primera empresa (e.firma o CIEC) para empezar a descargar.
            </p>
          </div>
          <Button onClick={() => setOpen(true)}>
            <Plus className="size-4" /> Agregar empresa
          </Button>
        </Card>
      ) : (
        <Card className="overflow-hidden p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Empresa</TableHead>
                <TableHead>RFC</TableHead>
                <TableHead>Método</TableHead>
                <TableHead className="text-right" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {empresas.map((e) => (
                <EmpresaRow
                  key={e.rfc}
                  empresa={e}
                  busy={busy === e.rfc}
                  onSeleccionar={() => withBusy(e.rfc, () => seleccionar(e.rfc, e.metodos))}
                  onRemove={() => withBusy(e.rfc, () => remove(e.rfc))}
                />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}

      <div className="flex items-center gap-2 rounded-lg border bg-secondary px-4 py-3 text-xs text-muted-foreground">
        <Lock className="size-4 shrink-0" />
        <span>
          Las contraseñas de tu e.firma y CIEC se guardan en el{' '}
          <span className="font-medium text-foreground">keychain del sistema</span>{' '}
          (Keychain en macOS, Credential Manager en Windows), nunca en texto plano.
        </span>
      </div>

      <EmpresaAddDialog open={open} onOpenChange={setOpen} addFiel={addFiel} addCiec={addCiec} />
    </div>
  );
}

function EmpresaRow({
  empresa,
  busy,
  onSeleccionar,
  onRemove,
}: {
  empresa: Empresa;
  busy: boolean;
  onSeleccionar: () => void;
  onRemove: () => void;
}) {
  return (
    <TableRow className={empresa.default ? 'bg-accent/60' : undefined}>
      <TableCell>
        <div className="flex items-center gap-3">
          <div
            className="flex size-8 shrink-0 items-center justify-center rounded-md font-mono text-[10px] font-bold text-white"
            style={{ background: colorDe(empresa.rfc) }}
          >
            {iniciales(empresa.nombre)}
          </div>
          <div>
            <div className="font-medium leading-tight">{empresa.nombre}</div>
            {empresa.default && (
              <div className="flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wide text-primary">
                <span className="size-1.5 rounded-full bg-primary" />
                Activa
              </div>
            )}
          </div>
        </div>
      </TableCell>
      <TableCell className="font-mono text-xs text-muted-foreground">{empresa.rfc}</TableCell>
      <TableCell>
        {/* Una empresa puede tener ambos métodos. */}
        <div className="flex flex-wrap gap-1">
          {empresa.metodos.includes('fiel') && (
            <Badge variant="secondary" className="gap-1">
              <ShieldCheck className="size-3" /> e.firma
            </Badge>
          )}
          {empresa.metodos.includes('ciec') && (
            <Badge variant="secondary" className="gap-1">
              <KeyRound className="size-3" /> CIEC
            </Badge>
          )}
        </div>
      </TableCell>
      <TableCell className="text-right">
        <div className="inline-flex items-center gap-1">
          {!empresa.default && (
            <Button variant="ghost" size="sm" onClick={onSeleccionar} disabled={busy}>
              {busy ? <Loader2 className="size-3 animate-spin" /> : null}
              Usar
            </Button>
          )}
          <Button asChild variant="ghost" size="icon" title="Editar / credenciales">
            <Link href={`/empresas/${encodeURIComponent(empresa.rfc)}`}>
              <Pencil className="size-4" />
            </Link>
          </Button>
          <Button variant="ghost" size="icon" onClick={onRemove} disabled={busy} title="Eliminar">
            <Trash2 className="size-4" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

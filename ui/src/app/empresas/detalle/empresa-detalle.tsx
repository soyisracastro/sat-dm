'use client';

// Componente cliente del detalle de empresa. La ruta es ESTÁTICA
// (`/empresas/detalle`) y el RFC viaja como query param (`?rfc=...`), leído con
// `useSearchParams`. Se evita un segmento dinámico `[rfc]` porque bajo
// `output: 'export'` cualquier valor no pre-generado es 404 (ver ui/CLAUDE.md).
// Debe renderizarse dentro de un <Suspense> (lo hace el page.tsx hermano), que
// es requisito de `useSearchParams` en export estático.

import { useRef, useState } from 'react';
import { useSearchParams } from 'next/navigation';
import Link from 'next/link';

import { useEmpresas } from '@/hooks/use-empresas';
import { PageHeading } from '@/components/layout/page-heading';
import { Icon } from '@/components/ui/icon';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { VencimientoBadge } from '@/components/fiel/vencimiento-badge';
import { ConfiguracionFiscalCard } from '@/components/empresas/configuracion-fiscal-card';
import { semaforoVencimiento } from '@/lib/vencimiento';
import type { Empresa } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

export function EmpresaDetalle() {
  const searchParams = useSearchParams();
  const rfc = searchParams.get('rfc') ?? '';
  const { empresas, loading, addCiec, addFiel, activarSesion, update } = useEmpresas();
  const empresa = empresas.find((e) => e.rfc === rfc);

  const volver = (
    <Link href="/empresas" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <Icon icon="ph:arrow-left-light" className="size-4" /> Empresas
    </Link>
  );

  if (loading && !empresa) {
    return (
      <div className="space-y-4">
        {volver}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" /> Cargando…
        </div>
      </div>
    );
  }

  if (!empresa) {
    return (
      <div className="space-y-4">
        {volver}
        <Alert>
          <AlertDescription>No se encontró la empresa {rfc}.</AlertDescription>
        </Alert>
      </div>
    );
  }

  const tieneCiec = empresa.metodos.includes('ciec');
  const tieneFiel = empresa.metodos.includes('fiel');

  return (
    <div className="max-w-2xl space-y-6">
      {volver}
      <PageHeading title={empresa.nombre} description={`${empresa.rfc}`} />

      <div className="flex flex-wrap items-center gap-2">
        {tieneFiel && (
          <Badge variant="secondary" className="gap-1">
            <Icon icon="ph:shield-check-light" className="size-3" /> e.firma
          </Badge>
        )}
        {tieneCiec && (
          <Badge variant="secondary" className="gap-1">
            <Icon icon="ph:key-light" className="size-3" /> CIEC
          </Badge>
        )}
        {tieneFiel && <VencimientoBadge vencimiento={empresa.vencimiento} />}
      </div>

      <ConfiguracionFiscalCard
        empresa={empresa}
        onGuardar={(patch) => update(empresa.rfc, patch)}
      />

      <CiecSection
        empresa={empresa}
        onGuardar={(ciec) => addCiec(empresa.rfc, empresa.nombre, ciec)}
      />
      <FielSection
        empresa={empresa}
        onGuardar={async (cer, key, password) => {
          await addFiel(cer, key, password, empresa.nombre, empresa.rfc);
          // Cargar la e.firma recién agregada/renovada en la sesión (cabecera/Inicio).
          await activarSesion(empresa.rfc);
        }}
      />
    </div>
  );
}

function Guardado() {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
      <Icon icon="ph:check-circle-light" className="size-3.5" /> Guardado
    </span>
  );
}

function CiecSection({
  empresa,
  onGuardar,
}: {
  empresa: Empresa;
  onGuardar: (ciec: string) => Promise<void>;
}) {
  const tiene = empresa.metodos.includes('ciec');
  const [mostrarForm, setMostrarForm] = useState(!tiene);
  const [ciec, setCiec] = useState('');
  const [saving, setSaving] = useState(false);
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!ciec) return;
    setSaving(true);
    setError(null);
    setOk(false);
    try {
      await onGuardar(ciec);
      setCiec('');
      setOk(true);
      // Si ya tenía CIEC, colapsa el form de vuelta al resumen.
      if (tiene) setMostrarForm(false);
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setSaving(false);
    }
  }

  // Empresa ya tiene CIEC y el form está colapsado → resumen + botón.
  if (tiene && !mostrarForm) {
    return (
      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Icon icon="ph:key-light" className="size-4 text-primary" />
            <span className="text-sm font-medium">CIEC</span>
            {ok && <Guardado />}
          </div>
          <Button variant="outline" size="sm" onClick={() => setMostrarForm(true)}>
            Cambiar contraseña CIEC
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          La contraseña CIEC está guardada en el keychain del sistema.
        </p>
      </Card>
    );
  }

  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon icon="ph:key-light" className="size-4 text-primary" />
          <span className="text-sm font-medium">
            {tiene ? 'Cambiar contraseña CIEC' : 'Agregar CIEC'}
          </span>
        </div>
        {ok && <Guardado />}
      </div>
      <form className="flex gap-2" onSubmit={guardar}>
        <Input
          type="password"
          value={ciec}
          placeholder="Nueva contraseña CIEC"
          onChange={(e) => {
            setCiec(e.target.value);
            setOk(false);
          }}
        />
        <Button type="submit" disabled={!ciec || saving}>
          {saving ? <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" /> : 'Guardar'}
        </Button>
        {tiene && (
          <Button
            type="button"
            variant="ghost"
            onClick={() => {
              setMostrarForm(false);
              setCiec('');
              setError(null);
            }}
          >
            Cancelar
          </Button>
        )}
      </form>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </Card>
  );
}

function FielSection({
  empresa,
  onGuardar,
}: {
  empresa: Empresa;
  onGuardar: (cer: File, key: File, password: string) => Promise<void>;
}) {
  const tiene = empresa.metodos.includes('fiel');
  const sem = tiene ? semaforoVencimiento(empresa.vencimiento) : null;
  const avisaRenovar = sem !== null && sem.estado !== 'verde';
  const [mostrarForm, setMostrarForm] = useState(!tiene);
  const [cer, setCer] = useState<File | null>(null);
  const [key, setKey] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [ok, setOk] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cerRef = useRef<HTMLInputElement>(null);
  const keyRef = useRef<HTMLInputElement>(null);

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    if (!cer || !key || !password) return;
    setSaving(true);
    setError(null);
    setOk(false);
    try {
      await onGuardar(cer, key, password);
      setCer(null);
      setKey(null);
      setPassword('');
      if (cerRef.current) cerRef.current.value = '';
      if (keyRef.current) keyRef.current.value = '';
      setOk(true);
      if (tiene) setMostrarForm(false);
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setSaving(false);
    }
  }

  // Empresa ya tiene FIEL y el form está colapsado → resumen + botón.
  if (tiene && !mostrarForm) {
    return (
      <Card className="space-y-3 p-5">
        <div className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <Icon icon="ph:shield-check-light" className="size-4 text-primary" />
            <span className="text-sm font-medium">e.firma</span>
            {ok && <Guardado />}
          </div>
          <Button variant="outline" size="sm" onClick={() => setMostrarForm(true)}>
            Renovar e.firma
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {sem ? `Vence el ${sem.fecha} · ${sem.label}` : 'Certificado registrado.'}
        </p>
        {avisaRenovar && sem && (
          <Alert
            variant={sem.estado === 'rojo' ? 'destructive' : 'default'}
            className={
              sem.estado === 'amarillo'
                ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300'
                : undefined
            }
          >
            <AlertDescription className="text-xs">
              {sem.vencida
                ? `Esta e.firma venció el ${sem.fecha}. Renuévala subiendo el nuevo .cer y .key.`
                : `Esta e.firma ${sem.label.toLowerCase()} (vence el ${sem.fecha}). Conviene renovarla.`}
            </AlertDescription>
          </Alert>
        )}
      </Card>
    );
  }

  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Icon icon="ph:shield-check-light" className="size-4 text-primary" />
          <span className="text-sm font-medium">
            {tiene ? 'Renovar e.firma' : 'Agregar e.firma'}
          </span>
        </div>
        {ok && <Guardado />}
      </div>
      <p className="text-xs text-muted-foreground">
        Sube el .cer y .key de la e.firma de este RFC ({empresa.rfc}).
      </p>
      {avisaRenovar && sem && (
        <Alert
          variant={sem.estado === 'rojo' ? 'destructive' : 'default'}
          className={
            sem.estado === 'amarillo'
              ? 'border-amber-300 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-300'
              : undefined
          }
        >
          <AlertDescription className="text-xs">
            {sem.vencida
              ? `Esta e.firma venció el ${sem.fecha}. Renuévala subiendo el nuevo .cer y .key.`
              : `Esta e.firma ${sem.label.toLowerCase()} (vence el ${sem.fecha}). Conviene renovarla.`}
          </AlertDescription>
        </Alert>
      )}
      <form className="space-y-3" onSubmit={guardar}>
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <Label htmlFor="cer">Certificado (.cer)</Label>
            <Input ref={cerRef} id="cer" type="file" accept=".cer"
                   onChange={(e) => { setCer(e.target.files?.[0] ?? null); setOk(false); }} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="key">Llave (.key)</Label>
            <Input ref={keyRef} id="key" type="file" accept=".key"
                   onChange={(e) => { setKey(e.target.files?.[0] ?? null); setOk(false); }} />
          </div>
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="pass">Contraseña de la clave privada</Label>
          <Input id="pass" type="password" value={password}
                 onChange={(e) => { setPassword(e.target.value); setOk(false); }} />
        </div>
        <div className="flex gap-2">
          <Button type="submit" disabled={!cer || !key || !password || saving}>
            {saving ? <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" /> : <Icon icon="ph:shield-check-light" className="size-4" />}
            {tiene ? 'Renovar e.firma' : 'Agregar e.firma'}
          </Button>
          {tiene && (
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setMostrarForm(false);
                setCer(null);
                setKey(null);
                setPassword('');
                if (cerRef.current) cerRef.current.value = '';
                if (keyRef.current) keyRef.current.value = '';
                setError(null);
              }}
            >
              Cancelar
            </Button>
          )}
        </div>
      </form>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </Card>
  );
}

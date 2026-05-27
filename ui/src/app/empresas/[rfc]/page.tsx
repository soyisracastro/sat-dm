'use client';

import { useRef, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { ArrowLeft, CheckCircle2, KeyRound, Loader2, ShieldCheck } from 'lucide-react';

import { useEmpresas } from '@/hooks/use-empresas';
import { PageHeading } from '@/components/layout/page-heading';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import type { Empresa } from '@/lib/types';

export default function EmpresaDetallePage() {
  const params = useParams<{ rfc: string }>();
  const rfc = decodeURIComponent(params.rfc);
  const { empresas, loading, addCiec, addFiel } = useEmpresas();
  const empresa = empresas.find((e) => e.rfc === rfc);

  const volver = (
    <Link href="/empresas" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
      <ArrowLeft className="size-4" /> Empresas
    </Link>
  );

  if (loading && !empresa) {
    return (
      <div className="space-y-4">
        {volver}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Cargando…
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
            <ShieldCheck className="size-3" /> e.firma
          </Badge>
        )}
        {tieneCiec && (
          <Badge variant="secondary" className="gap-1">
            <KeyRound className="size-3" /> CIEC
          </Badge>
        )}
        {tieneFiel && empresa.vencimiento && (
          <span className="text-xs text-muted-foreground">
            e.firma vence: {empresa.vencimiento}
          </span>
        )}
      </div>

      <CiecSection
        empresa={empresa}
        onGuardar={(ciec) => addCiec(empresa.rfc, empresa.nombre, ciec)}
      />
      <FielSection
        empresa={empresa}
        onGuardar={(cer, key, password) =>
          addFiel(cer, key, password, empresa.nombre)
        }
      />
    </div>
  );
}

function Guardado() {
  return (
    <span className="inline-flex items-center gap-1 text-xs font-medium text-success">
      <CheckCircle2 className="size-3.5" /> Guardado
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
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <KeyRound className="size-4 text-primary" />
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
          {saving ? <Loader2 className="size-4 animate-spin" /> : 'Guardar'}
        </Button>
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
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card className="space-y-3 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ShieldCheck className="size-4 text-primary" />
          <span className="text-sm font-medium">
            {tiene ? 'Renovar e.firma' : 'Agregar e.firma'}
          </span>
        </div>
        {ok && <Guardado />}
      </div>
      <p className="text-xs text-muted-foreground">
        Sube el .cer y .key de la e.firma de este RFC ({empresa.rfc}).
      </p>
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
        <Button type="submit" disabled={!cer || !key || !password || saving}>
          {saving ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
          {tiene ? 'Renovar e.firma' : 'Agregar e.firma'}
        </Button>
      </form>
      {error && <p className="text-xs text-destructive">{error}</p>}
    </Card>
  );
}

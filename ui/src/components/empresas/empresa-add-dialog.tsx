'use client';

import { useRef, useState } from 'react';

import { cn } from '@/lib/utils';
import { Icon } from '@/components/ui/icon';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { mensajeDeError } from '@/lib/errores';

interface EmpresaAddDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  addFiel: (cer: File, key: File, password: string) => Promise<void>;
  addCiec: (rfc: string, ciec: string) => Promise<void>;
}

/**
 * Modal de alta de empresa, simplificado: solo el acceso (e.firma o CIEC), sin
 * pedir el nombre — se completa solo (razón social del certificado o RFC) en
 * cuanto conectamos con el SAT.
 */
export function EmpresaAddDialog({
  open,
  onOpenChange,
  addFiel,
  addCiec,
}: EmpresaAddDialogProps) {
  // e.firma
  const [cer, setCer] = useState<File | null>(null);
  const [key, setKey] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  // CIEC
  const [rfc, setRfc] = useState('');
  const [ciec, setCiec] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setCer(null);
    setKey(null);
    setPassword('');
    setRfc('');
    setCiec('');
    setError(null);
  }

  function handleOpenChange(next: boolean) {
    if (!next) reset();
    onOpenChange(next);
  }

  async function run(fn: () => Promise<void>) {
    setLoading(true);
    setError(null);
    try {
      await fn();
      handleOpenChange(false);
    } catch (err) {
      setError(mensajeDeError(err));
    } finally {
      setLoading(false);
    }
  }

  const fielOk = !!cer && !!key && password.length > 0;
  const ciecOk = rfc.trim().length >= 12 && ciec.length > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Agregar empresa</DialogTitle>
          <DialogDescription>
            Tus accesos se guardan protegidos y solo en este equipo. Tu e.firma
            nunca sale de tu computadora.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="fiel">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="fiel">
              <Icon icon="ph:shield-check-light" className="size-4" /> e.firma
            </TabsTrigger>
            <TabsTrigger value="ciec">
              <Icon icon="ph:key-light" className="size-4" /> CIEC
            </TabsTrigger>
          </TabsList>

          {/* e.firma */}
          <TabsContent value="fiel" className="mt-4">
            <form
              className="space-y-3.5"
              onSubmit={(e) => {
                e.preventDefault();
                if (fielOk) run(() => addFiel(cer!, key!, password));
              }}
            >
              <FileField
                label="Certificado (.cer)"
                accept=".cer"
                file={cer}
                onPick={setCer}
              />
              <FileField
                label="Llave privada (.key)"
                accept=".key"
                file={key}
                onPick={setKey}
              />
              <Field label="Contraseña de la clave privada" htmlFor="fiel-pass">
                <Input id="fiel-pass" type="password" value={password}
                       placeholder="••••••••"
                       onChange={(e) => setPassword(e.target.value)} />
              </Field>
              <HintNombre />
              <Button type="submit" className="w-full" disabled={!fielOk || loading}>
                {loading ? <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" /> : <Icon icon="ph:shield-check-light" className="size-4" />}
                Registrar con e.firma
              </Button>
            </form>
          </TabsContent>

          {/* CIEC */}
          <TabsContent value="ciec" className="mt-4">
            <form
              className="space-y-3.5"
              onSubmit={(e) => {
                e.preventDefault();
                if (ciecOk) run(() => addCiec(rfc.trim().toUpperCase(), ciec));
              }}
            >
              <Field label="RFC" htmlFor="ciec-rfc">
                <Input id="ciec-rfc" value={rfc} placeholder="XAXX010101000"
                       className="font-mono uppercase"
                       onChange={(e) => setRfc(e.target.value)} />
              </Field>
              <Field label="Contraseña CIEC" htmlFor="ciec-pass">
                <Input id="ciec-pass" type="password" value={ciec}
                       placeholder="••••••••"
                       onChange={(e) => setCiec(e.target.value)} />
              </Field>
              <HintNombre />
              <Button type="submit" className="w-full" disabled={!ciecOk || loading}>
                {loading ? <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" /> : <Icon icon="ph:key-light" className="size-4" />}
                Registrar con CIEC
              </Button>
            </form>
          </TabsContent>
        </Tabs>

        {error && (
          <Alert variant="destructive">
            <AlertTitle>No se pudo registrar</AlertTitle>
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}
      </DialogContent>
    </Dialog>
  );
}

function HintNombre() {
  return (
    <div className="flex items-start gap-2 rounded-lg bg-accent px-3 py-2.5 text-xs leading-relaxed text-accent-foreground">
      <Icon icon="ph:info-light" className="mt-px size-3.75 shrink-0" />
      El nombre de la empresa se completa en cuanto conectamos con el SAT.
    </div>
  );
}

function Field({
  label,
  htmlFor,
  children,
}: {
  label: string;
  htmlFor: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-2">
      <Label htmlFor={htmlFor}>{label}</Label>
      {children}
    </div>
  );
}

/** Selector de archivo estilo prototipo: pill "Seleccionar" + nombre + check. */
function FileField({
  label,
  accept,
  file,
  onPick,
}: {
  label: string;
  accept: string;
  file: File | null;
  onPick: (f: File | null) => void;
}) {
  const ref = useRef<HTMLInputElement>(null);
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <button
        type="button"
        onClick={() => ref.current?.click()}
        className={cn(
          'flex w-full items-center gap-2.5 rounded-lg border bg-card p-1.5 pl-2 text-left transition-colors',
          file ? 'border-success' : 'border-input hover:border-primary',
        )}
      >
        <span className="inline-flex shrink-0 items-center gap-1.5 rounded-md bg-secondary px-2.5 py-1.5 text-xs font-semibold text-secondary-foreground">
          <Icon icon="ph:upload-light" className="size-3.5" />
          Seleccionar
        </span>
        <span
          className={cn(
            'min-w-0 flex-1 truncate text-xs',
            file ? 'font-medium text-foreground' : 'text-muted-foreground',
          )}
        >
          {file ? file.name : 'Ningún archivo seleccionado'}
        </span>
        {file && (
          <Icon
            icon="ph:check-circle-light"
            className="mr-1 size-4 shrink-0 text-success"
          />
        )}
        <input
          ref={ref}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => onPick(e.target.files?.[0] ?? null)}
        />
      </button>
    </div>
  );
}

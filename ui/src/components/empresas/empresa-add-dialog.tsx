'use client';

import { useRef, useState } from 'react';
import { KeyRound, Loader2, ShieldCheck } from 'lucide-react';

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

interface EmpresaAddDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  addFiel: (cer: File, key: File, password: string, nombre: string) => Promise<void>;
  addCiec: (rfc: string, nombre: string, ciec: string) => Promise<void>;
}

/**
 * Modal de alta de empresa con dos métodos (tabs): e.firma (.cer/.key/contraseña) y
 * CIEC (RFC + contraseña). Las credenciales las guarda el agente en el keychain del SO.
 */
export function EmpresaAddDialog({
  open,
  onOpenChange,
  addFiel,
  addCiec,
}: EmpresaAddDialogProps) {
  // e.firma
  const [nombre, setNombre] = useState('');
  const [cer, setCer] = useState<File | null>(null);
  const [key, setKey] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  // CIEC
  const [cnombre, setCnombre] = useState('');
  const [rfc, setRfc] = useState('');
  const [ciec, setCiec] = useState('');

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cerRef = useRef<HTMLInputElement>(null);
  const keyRef = useRef<HTMLInputElement>(null);

  function reset() {
    setNombre('');
    setCer(null);
    setKey(null);
    setPassword('');
    setCnombre('');
    setRfc('');
    setCiec('');
    setError(null);
    if (cerRef.current) cerRef.current.value = '';
    if (keyRef.current) keyRef.current.value = '';
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
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  const fielOk = !!cer && !!key && password.length > 0 && nombre.trim().length > 0;
  const ciecOk =
    rfc.trim().length >= 12 && cnombre.trim().length > 0 && ciec.length > 0;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Agregar empresa</DialogTitle>
          <DialogDescription>
            Las credenciales se guardan localmente en el keychain del sistema. La
            e.firma nunca sale de tu equipo.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="fiel">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="fiel">
              <ShieldCheck className="size-4" /> e.firma
            </TabsTrigger>
            <TabsTrigger value="ciec">
              <KeyRound className="size-4" /> CIEC
            </TabsTrigger>
          </TabsList>

          {/* e.firma */}
          <TabsContent value="fiel" className="mt-4">
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (fielOk) run(() => addFiel(cer!, key!, password, nombre));
              }}
            >
              <Field label="Nombre de la empresa" htmlFor="fiel-nombre">
                <Input id="fiel-nombre" value={nombre} placeholder="Mi Empresa SA de CV"
                       onChange={(e) => setNombre(e.target.value)} />
              </Field>
              <Field label="Certificado (.cer)" htmlFor="fiel-cer">
                <Input ref={cerRef} id="fiel-cer" type="file" accept=".cer"
                       onChange={(e) => setCer(e.target.files?.[0] ?? null)} />
              </Field>
              <Field label="Llave privada (.key)" htmlFor="fiel-key">
                <Input ref={keyRef} id="fiel-key" type="file" accept=".key"
                       onChange={(e) => setKey(e.target.files?.[0] ?? null)} />
              </Field>
              <Field label="Contraseña de la clave privada" htmlFor="fiel-pass">
                <Input id="fiel-pass" type="password" value={password}
                       onChange={(e) => setPassword(e.target.value)} />
              </Field>
              <Button type="submit" className="w-full" disabled={!fielOk || loading}>
                {loading ? <Loader2 className="size-4 animate-spin" /> : <ShieldCheck className="size-4" />}
                Registrar con e.firma
              </Button>
            </form>
          </TabsContent>

          {/* CIEC */}
          <TabsContent value="ciec" className="mt-4">
            <form
              className="space-y-3"
              onSubmit={(e) => {
                e.preventDefault();
                if (ciecOk) run(() => addCiec(rfc.trim().toUpperCase(), cnombre, ciec));
              }}
            >
              <Field label="Nombre de la empresa" htmlFor="ciec-nombre">
                <Input id="ciec-nombre" value={cnombre} placeholder="Mi Empresa SA de CV"
                       onChange={(e) => setCnombre(e.target.value)} />
              </Field>
              <Field label="RFC" htmlFor="ciec-rfc">
                <Input id="ciec-rfc" value={rfc} placeholder="XAXX010101000"
                       className="font-mono uppercase"
                       onChange={(e) => setRfc(e.target.value)} />
              </Field>
              <Field label="Contraseña CIEC" htmlFor="ciec-pass">
                <Input id="ciec-pass" type="password" value={ciec}
                       onChange={(e) => setCiec(e.target.value)} />
              </Field>
              <Button type="submit" className="w-full" disabled={!ciecOk || loading}>
                {loading ? <Loader2 className="size-4 animate-spin" /> : <KeyRound className="size-4" />}
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

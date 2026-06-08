'use client';

import { useRef, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { Icon } from '@/components/ui/icon';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';

interface FielUploadDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function FielUploadDialog({ open, onOpenChange }: FielUploadDialogProps) {
  const { cargarFiel, fielStatus, descargarFiel } = useServer();

  const [cerFile, setCerFile] = useState<File | null>(null);
  const [keyFile, setKeyFile] = useState<File | null>(null);
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successRfc, setSuccessRfc] = useState<string | null>(null);
  const [unloading, setUnloading] = useState(false);

  const cerInputRef = useRef<HTMLInputElement>(null);
  const keyInputRef = useRef<HTMLInputElement>(null);

  const canSubmit = cerFile && keyFile && password.length > 0 && !loading;

  function resetForm() {
    setCerFile(null);
    setKeyFile(null);
    setPassword('');
    setError(null);
    setSuccessRfc(null);
    if (cerInputRef.current) cerInputRef.current.value = '';
    if (keyInputRef.current) keyInputRef.current.value = '';
  }

  function handleOpenChange(nextOpen: boolean) {
    if (!nextOpen) {
      resetForm();
    }
    onOpenChange(nextOpen);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;

    setLoading(true);
    setError(null);
    setSuccessRfc(null);

    try {
      const result = await cargarFiel(cerFile, keyFile, password);
      setSuccessRfc(result.rfc);

      // Auto-close after 1.5s on success
      setTimeout(() => {
        handleOpenChange(false);
      }, 1500);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Error al cargar la e.firma';
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function handleUnload() {
    setUnloading(true);
    try {
      await descargarFiel();
      resetForm();
    } catch (err) {
      const message =
        err instanceof Error ? err.message : 'Error al descargar la e.firma';
      setError(message);
    } finally {
      setUnloading(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Cargar e.firma</DialogTitle>
          <DialogDescription>
            Selecciona los archivos de tu e.firma (FIEL) para autenticarte con
            el SAT.
          </DialogDescription>
        </DialogHeader>

        {/* Show unload option when FIEL is already loaded */}
        {fielStatus.loaded && !successRfc && (
          <Alert>
            <Icon icon="ph:check-circle-light" className="size-4 text-green-600" />
            <AlertTitle>e.firma cargada</AlertTitle>
            <AlertDescription className="flex items-center justify-between">
              <span>RFC: {fielStatus.rfc}</span>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleUnload}
                disabled={unloading}
              >
                {unloading ? (
                  <>
                    <Icon icon="ph:circle-notch-light" className="size-3 animate-spin" />
                    Descargando...
                  </>
                ) : (
                  'Descargar e.firma'
                )}
              </Button>
            </AlertDescription>
          </Alert>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="cer-file">Certificado (.cer)</Label>
            <Input
              ref={cerInputRef}
              id="cer-file"
              type="file"
              accept=".cer"
              onChange={(e) => setCerFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="key-file">Llave privada (.key)</Label>
            <Input
              ref={keyInputRef}
              id="key-file"
              type="file"
              accept=".key"
              onChange={(e) => setKeyFile(e.target.files?.[0] ?? null)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="fiel-password">Contrasena de la llave privada</Label>
            <Input
              id="fiel-password"
              type="password"
              placeholder="Contrasena de la llave privada"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          {error && (
            <Alert variant="destructive">
              <AlertTitle>Error</AlertTitle>
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {successRfc && (
            <Alert className="border-green-200 bg-green-50 text-green-800 dark:border-green-800 dark:bg-green-950/30 dark:text-green-400">
              <Icon icon="ph:check-circle-light" className="size-4 text-green-600" />
              <AlertTitle>e.firma cargada exitosamente</AlertTitle>
              <AlertDescription>RFC: {successRfc}</AlertDescription>
            </Alert>
          )}

          <Button type="submit" className="w-full" disabled={!canSubmit}>
            {loading ? (
              <>
                <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
                Cargando...
              </>
            ) : (
              <>
                <Icon icon="ph:upload-simple-light" className="size-4" />
                Cargar e.firma
              </>
            )}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

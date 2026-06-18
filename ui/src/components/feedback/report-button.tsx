'use client';

import { useState, type CSSProperties } from 'react';
import { toast } from 'sonner';

import { Icon } from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { useAuth } from '@/providers/auth-provider';
import { reportarProblema } from '@/lib/telemetria';

const NO_DRAG: CSSProperties & { WebkitAppRegion?: string } = {
  WebkitAppRegion: 'no-drag',
};

/**
 * Botón "Reportar un problema" para la Titlebar, junto a la campana. Abre un
 * diálogo con una caja de texto; al enviar manda un feedback a Sentry (vía
 * @sentry/electron) vinculado al último error capturado, junto con la info
 * técnica que el SDK adjunta solo (versión, SO, registro). Nunca viaja la
 * e.firma ni datos fiscales. Necesita su propio `no-drag` dentro de la franja
 * arrastrable de la Titlebar.
 */
export function ReportButton() {
  const { license } = useAuth();
  const [open, setOpen] = useState(false);
  const [mensaje, setMensaje] = useState('');
  const [email, setEmail] = useState('');
  const [enviando, setEnviando] = useState(false);

  // Prefill del correo con el de la licencia (si aún no lo tocó el usuario).
  const emailValor = email || license?.email || '';

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (!next) {
      setMensaje('');
      setEmail('');
    }
  }

  function enviar() {
    if (!mensaje.trim()) return;
    setEnviando(true);
    try {
      reportarProblema({ mensaje: mensaje.trim(), email: emailValor || undefined });
      toast.success('Gracias, recibimos tu reporte.', {
        description: 'Lo revisaremos con la información técnica del incidente.',
      });
      handleOpenChange(false);
    } finally {
      setEnviando(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <button
        type="button"
        aria-label="Reportar un problema"
        title="Reportar un problema"
        onClick={() => setOpen(true)}
        className="relative inline-flex size-7 items-center justify-center rounded-md text-foreground transition-colors hover:bg-secondary/60 focus-visible:outline-2 focus-visible:outline-ring"
        style={NO_DRAG}
      >
        <Icon icon="ph:lifebuoy-light" className="size-4" />
      </button>

      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Reportar un problema</DialogTitle>
          <DialogDescription>
            Cuéntanos qué pasó. Adjuntamos automáticamente la información técnica
            del incidente (versión, sistema y registro). Nunca enviamos tu e.firma,
            tus contraseñas ni tus datos fiscales.
          </DialogDescription>
        </DialogHeader>

        <form
          className="space-y-3.5"
          onSubmit={(e) => {
            e.preventDefault();
            enviar();
          }}
        >
          <div className="space-y-2">
            <Label htmlFor="reporte-msg">¿Qué pasó?</Label>
            <textarea
              id="reporte-msg"
              value={mensaje}
              onChange={(e) => setMensaje(e.target.value)}
              rows={4}
              autoFocus
              placeholder="Describe qué intentabas hacer y qué salió mal…"
              className="w-full resize-none rounded-md border border-input bg-transparent px-3 py-2 text-sm shadow-xs outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50 dark:bg-input/30"
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="reporte-email">Tu correo (opcional)</Label>
            <Input
              id="reporte-email"
              type="email"
              value={emailValor}
              placeholder="tucorreo@ejemplo.com"
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <DialogFooter>
            <Button type="submit" disabled={!mensaje.trim() || enviando}>
              {enviando ? (
                <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
              ) : (
                <Icon icon="ph:lifebuoy-light" className="size-4" />
              )}
              Enviar reporte
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}

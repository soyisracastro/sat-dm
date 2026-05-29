'use client';

import { useEffect, useState } from 'react';
import { useTheme } from 'next-themes';

import { Icon } from '@/components/ui/icon';

import { useServer } from '@/providers/server-provider';
import { PageHeading } from '@/components/layout/page-heading';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { getNotifPrefs, setNotifPrefs, type NotifPrefs } from '@/lib/notify/prefs';

const TEMAS = [
  { value: 'light', label: 'Claro', icon: 'ph:sun-light' },
  { value: 'dark', label: 'Oscuro', icon: 'ph:moon-light' },
  { value: 'system', label: 'Sistema', icon: 'ph:desktop-light' },
] as const;

/** Selector de carpeta nativo del SO (solo en Electron); null en navegador. */
function elegirCarpetaNativo(): Promise<string | null> | null {
  if (typeof window === 'undefined') return null;
  const d = (window as unknown as {
    satDesktop?: { elegirCarpeta?: () => Promise<string | null> };
  }).satDesktop;
  return d?.elegirCarpeta ? d.elegirCarpeta() : null;
}

export default function AjustesPage() {
  const { apiClient } = useServer();
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  const [dir, setDir] = useState('');
  const [editable, setEditable] = useState(false);
  const [saving, setSaving] = useState(false);
  const [notifPrefs, setNotifPrefsState] = useState<NotifPrefs>({
    descargas: true,
    efirma: true,
  });

  useEffect(() => {
    setMounted(true);
    setNotifPrefsState(getNotifPrefs());
  }, []);

  function actualizarNotif(patch: Partial<NotifPrefs>) {
    setNotifPrefsState(setNotifPrefs(patch));
  }

  useEffect(() => {
    apiClient
      .getDescargasDir()
      .then((r) => setDir(r.dir))
      .catch(() => {});
  }, [apiClient]);

  async function guardar(nueva: string) {
    setSaving(true);
    try {
      const r = await apiClient.setDescargasDir(nueva);
      setDir(r.dir);
      setEditable(false);
    } finally {
      setSaving(false);
    }
  }

  async function cambiar() {
    const picker = elegirCarpetaNativo();
    if (picker) {
      const elegida = await picker; // diálogo nativo del SO
      if (elegida) await guardar(elegida);
    } else {
      setEditable(true); // navegador (dev): editar la ruta a mano
    }
  }

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeading title="Ajustes" description="Configuración de la aplicación." />

      <Card className="space-y-3 p-5">
        <div className="space-y-1">
          <Label>Apariencia</Label>
          <p className="text-xs text-muted-foreground">
            Elige el tema visual. &quot;Sistema&quot; sigue la preferencia de tu sistema operativo.
          </p>
        </div>

        <div className="flex flex-wrap gap-2">
          {TEMAS.map((t) => {
            const activo = mounted && theme === t.value;
            return (
              <Button
                key={t.value}
                variant={activo ? 'default' : 'outline'}
                onClick={() => setTheme(t.value)}
                aria-pressed={activo}
              >
                <Icon icon={t.icon} className="size-4" />
                {t.label}
              </Button>
            );
          })}
        </div>
      </Card>

      <Card className="space-y-4 p-5">
        <div className="space-y-1">
          <Label>Notificaciones</Label>
          <p className="text-xs text-muted-foreground">
            Si la app está enfocada, el aviso aparece dentro (in-app). Si
            estás en otra ventana, llega al centro de notificaciones del SO.
          </p>
        </div>

        <div className="space-y-3">
          <label className="flex items-start gap-3">
            <Switch
              checked={notifPrefs.descargas}
              onCheckedChange={(v) => actualizarNotif({ descargas: v })}
              className="mt-0.5"
            />
            <span className="space-y-0.5">
              <span className="block text-sm">Avisarme cuando termine una descarga</span>
              <span className="block text-xs text-muted-foreground">
                Aplica a descargas WS (FIEL) y CIEC. También avisa si fallan.
              </span>
            </span>
          </label>

          <label className="flex items-start gap-3">
            <Switch
              checked={notifPrefs.efirma}
              onCheckedChange={(v) => actualizarNotif({ efirma: v })}
              className="mt-0.5"
            />
            <span className="space-y-0.5">
              <span className="block text-sm">
                Recordarme cuando mi e.firma esté por vencer
              </span>
              <span className="block text-xs text-muted-foreground">
                Una vez al día si la e.firma activa vence en 30 días o menos.
              </span>
            </span>
          </label>
        </div>

      </Card>

      <Card className="space-y-3 p-5">
        <div className="space-y-1">
          <Label>Carpeta de descargas</Label>
          <p className="text-xs text-muted-foreground">
            Dónde se guardan los CFDIs y documentos descargados (en subcarpetas por
            tipo y RFC).
          </p>
        </div>

        {editable ? (
          <div className="flex gap-2">
            <Input
              value={dir}
              onChange={(e) => setDir(e.target.value)}
              className="font-mono text-xs"
            />
            <Button onClick={() => guardar(dir)} disabled={saving}>
              {saving ? <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" /> : 'Guardar'}
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <code className="flex-1 truncate rounded-md border bg-secondary px-3 py-2 font-mono text-xs">
              {dir || '—'}
            </code>
            <Button variant="outline" onClick={cambiar} disabled={saving}>
              {saving ? (
                <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
              ) : (
                <Icon icon="ph:folder-light" className="size-4" />
              )}
              Cambiar…
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

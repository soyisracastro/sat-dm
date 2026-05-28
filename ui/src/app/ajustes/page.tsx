'use client';

import { useEffect, useState } from 'react';

import { Icon } from '@/components/ui/icon';

import { useServer } from '@/providers/server-provider';
import { PageHeading } from '@/components/layout/page-heading';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';

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
  const [dir, setDir] = useState('');
  const [editable, setEditable] = useState(false);
  const [saving, setSaving] = useState(false);

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

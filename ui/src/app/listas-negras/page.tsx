'use client';

import { useEffect, useState } from 'react';

import { useServer } from '@/providers/server-provider';
import { PageHeading } from '@/components/layout/page-heading';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Icon } from '@/components/ui/icon';
import Link from 'next/link';
import { MisCfdisTab } from '@/components/listas-negras/mis-cfdis-tab';
import { ValidarRfcsTab } from '@/components/listas-negras/validar-rfcs-tab';
import { MetadataChip } from '@/components/listas-negras/metadata-chip';
import type { ListasNegrasMetadata } from '@/lib/types';
import { mensajeDeError } from '@/lib/errores';

export default function ListasNegrasPage() {
  const { apiClient } = useServer();
  const [metadata, setMetadata] = useState<ListasNegrasMetadata | null>(null);
  const [authError, setAuthError] = useState<string | null>(null);

  // Carga la metadata al montar para mostrarla en el header. Si falla con 401,
  // pinta el alert de "Inicia sesión" y bloquea ambas tabs (las consultas igual
  // fallarían con el mismo 401).
  useEffect(() => {
    let cancelado = false;
    apiClient.listasNegrasMetadata()
      .then((m) => { if (!cancelado) setMetadata(m); })
      .catch((e) => {
        if (cancelado) return;
        const msg = mensajeDeError(e);
        if (/401/.test(msg) || /sesi[óo]n/i.test(msg)) {
          setAuthError(msg);
        }
      });
    return () => { cancelado = true; };
  }, [apiClient]);

  return (
    <div className="space-y-6">
      <PageHeading
        title="Listas negras del SAT"
        description="Validación contra Art. 69 (incumplidos) y Art. 69-B (EFOS) del CFF. Los datos se actualizan mensualmente."
        action={<MetadataChip metadata={metadata} />}
      />

      {authError && (
        <Alert variant="destructive">
          <Icon icon="ph:warning-light" className="size-4" />
          <AlertDescription>
            Necesitas iniciar sesión para consultar las listas negras.{' '}
            <Link href="/login" className="font-medium underline underline-offset-2">
              Iniciar sesión
            </Link>
          </AlertDescription>
        </Alert>
      )}

      {!authError && (
        <Tabs defaultValue="mis-cfdis">
          <TabsList>
            <TabsTrigger value="mis-cfdis">
              <Icon icon="ph:files-light" className="size-4" />
              Mis CFDIs
            </TabsTrigger>
            <TabsTrigger value="validar-rfcs">
              <Icon icon="ph:shield-check-light" className="size-4" />
              Validar RFCs
            </TabsTrigger>
          </TabsList>
          <TabsContent value="mis-cfdis" className="mt-4">
            <MisCfdisTab />
          </TabsContent>
          <TabsContent value="validar-rfcs" className="mt-4">
            <ValidarRfcsTab />
          </TabsContent>
        </Tabs>
      )}
    </div>
  );
}

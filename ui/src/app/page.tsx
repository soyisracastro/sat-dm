'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';

import { useServer } from '@/providers/server-provider';
import { getAgentBaseUrl } from '@/lib/constants';
import { PageHeading } from '@/components/layout/page-heading';
import { FielUploadDialog } from '@/components/fiel/fiel-upload-dialog';
import { VencimientoBadge } from '@/components/fiel/vencimiento-badge';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';

interface FeatureCard {
  href: string;
  title: string;
  description: string;
  icon: string;
  requiresFiel: boolean;
}

// Las 3 herramientas del MVP primero (CIEC, no requieren e.firma), luego el resto.
const FEATURE_CARDS: FeatureCard[] = [
  {
    href: '/empresas',
    title: 'Empresas',
    description: 'Registra y administra tus empresas (e.firma / CIEC).',
    icon: 'ph:buildings-light',
    requiresFiel: false,
  },
  {
    href: '/descarga',
    title: 'Descargar CFDIs',
    description: 'CFDIs del SAT — Web Service si tienes e.firma, portal con CIEC si no.',
    icon: 'ph:download-simple-light',
    requiresFiel: false,
  },
  {
    href: '/comprobantes',
    title: 'Comprobantes',
    description: 'Procesa XMLs descargados: tablas, filtros, validación contra SAT, reportes y exportación.',
    icon: 'ph:files-light',
    requiresFiel: false,
  },
  {
    href: '/organizador',
    title: 'Organizador',
    description: 'Organiza, renombra y deduplica los XML descargados.',
    icon: 'ph:folders-light',
    requiresFiel: false,
  },
];

export default function InicioPage() {
  const { isConnected, fielStatus } = useServer();
  const [fielDialogOpen, setFielDialogOpen] = useState(false);
  const [agentHost, setAgentHost] = useState('');

  // El host real del agente (puerto efímero en Electron); se resuelve en cliente.
  useEffect(() => {
    setAgentHost(getAgentBaseUrl().replace(/^https?:\/\//, ''));
  }, []);

  return (
    <div className="space-y-8">
      <PageHeading title="Inicio" description="Tu central de descargas del SAT." />

      {/* Status cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Icon icon="ph:hard-drives-light" className="size-4" />
              Servidor
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {isConnected ? (
                <>
                  <Icon icon="ph:check-circle-light" className="size-5 text-success" />
                  <span className="text-sm font-medium text-success">Conectado</span>
                  <span className="font-mono text-xs text-muted-foreground">
                    {agentHost}
                  </span>
                </>
              ) : (
                <>
                  <Icon icon="ph:x-circle-light" className="size-5 text-destructive" />
                  <span className="text-sm font-medium text-destructive">
                    Desconectado
                  </span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Icon icon="ph:key-light" className="size-4" />
              e-firma (FIEL)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between gap-2">
              <div className="flex items-center gap-2">
                {fielStatus.loaded ? (
                  <>
                    <Icon icon="ph:check-circle-light" className="size-5 shrink-0 text-success" />
                    <div className="flex flex-col gap-1">
                      <span className="font-mono text-sm font-medium text-success">
                        {fielStatus.rfc}
                      </span>
                      <VencimientoBadge vencimiento={fielStatus.vencimiento} />
                    </div>
                  </>
                ) : (
                  <>
                    <Icon icon="ph:x-circle-light" className="size-5 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      Sin e-firma cargada
                    </span>
                  </>
                )}
              </div>
              <Button variant="outline" size="sm" onClick={() => setFielDialogOpen(true)}>
                {fielStatus.loaded ? 'Cambiar' : 'Cargar'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {FEATURE_CARDS.map((card) => {
          const disabled = card.requiresFiel && !fielStatus.loaded;
          return (
            <Card key={card.href} className={cn('transition-colors', disabled && 'opacity-60')}>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Icon icon={card.icon} className="size-5" />
                  {card.title}
                </CardTitle>
                <CardDescription>{card.description}</CardDescription>
              </CardHeader>
              <CardContent>
                {disabled ? (
                  <Button variant="outline" size="sm" disabled>
                    Requiere e-firma
                  </Button>
                ) : (
                  <Button variant="outline" size="sm" asChild>
                    <Link href={card.href}>Abrir</Link>
                  </Button>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>

      <FielUploadDialog open={fielDialogOpen} onOpenChange={setFielDialogOpen} />
    </div>
  );
}

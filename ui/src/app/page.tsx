'use client';

import { useState } from 'react';
import Link from 'next/link';
import {
  CheckCircle,
  Database,
  Download,
  FolderTree,
  KeyRound,
  Server,
  ShieldCheck,
  XCircle,
} from 'lucide-react';

import { useServer } from '@/providers/server-provider';
import { PageHeading } from '@/components/layout/page-heading';
import { FielUploadDialog } from '@/components/fiel/fiel-upload-dialog';
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { cn } from '@/lib/utils';

// ---------------------------------------------------------------------------
// Feature card definitions
// ---------------------------------------------------------------------------

interface FeatureCard {
  href: string;
  title: string;
  description: string;
  icon: React.ComponentType<{ className?: string }>;
  requiresFiel: boolean;
}

const FEATURE_CARDS: FeatureCard[] = [
  {
    href: '/descarga',
    title: 'Descarga Masiva',
    description:
      'Descarga CFDIs (XMLs) del SAT usando el Web Service oficial con tu e-firma.',
    icon: Download,
    requiresFiel: true,
  },
  {
    href: '/metadata',
    title: 'Metadata',
    description:
      'Consulta resumen (CSV) de tus CFDIs sin descargar los XMLs completos.',
    icon: Database,
    requiresFiel: true,
  },
  {
    href: '/validacion',
    title: 'Validacion CFDI',
    description:
      'Verifica el estatus de CFDIs (Vigente, Cancelado, No Encontrado) en el SAT.',
    icon: ShieldCheck,
    requiresFiel: false,
  },
  {
    href: '/organizador',
    title: 'Organizador',
    description:
      'Organiza, renombra y deduplica archivos XML de CFDIs descargados.',
    icon: FolderTree,
    requiresFiel: false,
  },
];

// ---------------------------------------------------------------------------
// Dashboard page
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { isConnected, fielStatus } = useServer();
  const [fielDialogOpen, setFielDialogOpen] = useState(false);

  return (
    <div className="space-y-8">
      <PageHeading title="Dashboard" />

      {/* Status cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        {/* Server status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="size-4" />
              Servidor
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              {isConnected ? (
                <>
                  <CheckCircle className="size-5 text-green-600" />
                  <span className="text-sm font-medium text-green-700 dark:text-green-400">
                    Conectado
                  </span>
                  <span className="text-xs text-muted-foreground">
                    localhost:8787
                  </span>
                </>
              ) : (
                <>
                  <XCircle className="size-5 text-red-500" />
                  <span className="text-sm font-medium text-red-600 dark:text-red-400">
                    Desconectado
                  </span>
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* FIEL status */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <KeyRound className="size-4" />
              e-firma (FIEL)
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                {fielStatus.loaded ? (
                  <>
                    <CheckCircle className="size-5 text-green-600" />
                    <span className="text-sm font-medium text-green-700 dark:text-green-400">
                      {fielStatus.rfc}
                    </span>
                  </>
                ) : (
                  <>
                    <XCircle className="size-5 text-muted-foreground" />
                    <span className="text-sm text-muted-foreground">
                      Sin e-firma cargada
                    </span>
                  </>
                )}
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setFielDialogOpen(true)}
              >
                {fielStatus.loaded ? 'Cambiar' : 'Cargar'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Feature cards */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {FEATURE_CARDS.map((card) => {
          const Icon = card.icon;
          const disabled = card.requiresFiel && !fielStatus.loaded;

          return (
            <Card
              key={card.href}
              className={cn(
                'transition-colors',
                disabled && 'opacity-50',
              )}
            >
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Icon className="size-5" />
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

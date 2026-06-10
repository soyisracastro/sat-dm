'use client';

import Link from 'next/link';

import { PageHeading } from '@/components/layout/page-heading';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

interface FeatureCard {
  href: string;
  title: string;
  description: string;
  icon: string;
}

// El estado (conexión, e.firma) vive en la barra inferior; el Inicio va
// directo a los accesos.
const FEATURE_CARDS: FeatureCard[] = [
  {
    href: '/empresas',
    title: 'Empresas',
    description: 'Registra y administra tus empresas con e.firma o CIEC.',
    icon: 'ph:buildings-light',
  },
  {
    href: '/descarga',
    title: 'Descargar CFDIs',
    description:
      'Trae tus facturas del SAT: descarga masiva con e.firma o directa del portal con CIEC.',
    icon: 'ph:download-simple-light',
  },
  {
    href: '/comprobantes',
    title: 'Comprobantes',
    description: 'Revisa, valida y exporta las facturas que ya descargaste.',
    icon: 'ph:files-light',
  },
  {
    href: '/organizador',
    title: 'Organizador',
    description:
      'Ordena, renombra y quita duplicados de tus archivos descargados.',
    icon: 'ph:folders-light',
  },
];

export default function InicioPage() {
  return (
    <div className="space-y-8">
      <PageHeading
        title="Inicio"
        description="Tu central para descargar y organizar las facturas del SAT."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {FEATURE_CARDS.map((card) => (
          <Card key={card.href} className="transition-colors">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-base">
                <Icon icon={card.icon} className="size-5" />
                {card.title}
              </CardTitle>
              <CardDescription>{card.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <Button variant="outline" size="sm" asChild>
                <Link href={card.href}>Abrir</Link>
              </Button>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}

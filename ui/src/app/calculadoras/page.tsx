'use client';

import Link from 'next/link';

import { PageHeading } from '@/components/layout/page-heading';
import { Card, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';

interface CalculadoraCard {
  href: string;
  titulo: string;
  descripcion: string;
  icono: string;
}

const CALCULADORAS: CalculadoraCard[] = [
  {
    href: '/calculadoras/aguinaldo',
    titulo: 'Aguinaldo',
    descripcion: 'Aguinaldo proporcional con ISR por Ley o por Reglamento.',
    icono: 'ph:gift-light',
  },
  {
    href: '/calculadoras/sbc',
    titulo: 'Salario Base de Cotización',
    descripcion: 'Factor de integración y SBC diario y mensual para el IMSS.',
    icono: 'ph:heartbeat-light',
  },
  {
    href: '/calculadoras/isr',
    titulo: 'ISR de sueldos',
    descripcion: 'Retención de ISR por período con subsidio para el empleo.',
    icono: 'ph:percent-light',
  },
  {
    href: '/calculadoras/finiquito',
    titulo: 'Finiquito',
    descripcion: 'Partes proporcionales y neto a pagar al terminar la relación laboral.',
    icono: 'ph:handshake-light',
  },
  {
    href: '/calculadoras/liquidacion',
    titulo: 'Liquidación',
    descripcion: 'Finiquito más indemnizaciones según el tipo de terminación.',
    icono: 'ph:scales-light',
  },
  {
    href: '/calculadoras/carga-patronal',
    titulo: 'Carga patronal',
    descripcion: 'Costo real de un empleado: IMSS, Infonavit e impuesto estatal.',
    icono: 'ph:factory-light',
  },
  {
    href: '/calculadoras/ptu',
    titulo: 'PTU',
    descripcion: 'Reparto de utilidades por trabajador con ISR Art. 96 vs Art. 174.',
    icono: 'ph:users-three-light',
  },
];

export default function CalculadorasPage() {
  return (
    <div className="space-y-6">
      <PageHeading
        title="Calculadoras"
        description="Herramientas de nómina y previsión social. Cada cálculo se guarda automáticamente para la empresa activa."
      />

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {CALCULADORAS.map((card) => (
          <Link key={card.href} href={card.href} className="group">
            <Card className="h-full transition-colors group-hover:border-primary/40 group-hover:bg-accent/40">
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Icon icon={card.icono} className="size-5" />
                  {card.titulo}
                </CardTitle>
                <CardDescription>{card.descripcion}</CardDescription>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>
    </div>
  );
}

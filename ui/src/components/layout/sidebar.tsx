'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { cn } from '@/lib/utils';
import { useServer } from '@/providers/server-provider';
import { FielStatus } from '@/components/fiel/fiel-status';
import { Icon } from '@/components/ui/icon';

const NAV_ITEMS = [
  { href: '/', label: 'Inicio', icon: 'ph:squares-four-light' },
  { href: '/empresas', label: 'Empresas', icon: 'ph:buildings-light' },
  { href: '/nueva-descarga', label: 'Nueva descarga', icon: 'ph:download-simple-light' },
  { href: '/documentos', label: 'Documentos', icon: 'ph:file-text-light' },
  { href: '/descarga', label: 'Descarga WS', icon: 'ph:download-simple-light' },
  { href: '/validacion', label: 'Validacion', icon: 'ph:shield-check-light' },
  { href: '/organizador', label: 'Organizador', icon: 'ph:folders-light' },
  { href: '/historial', label: 'Historial', icon: 'ph:clock-counter-clockwise-light' },
  { href: '/ajustes', label: 'Ajustes', icon: 'ph:gear-light' },
] as const;

export function Sidebar() {
  const pathname = usePathname();
  const { isConnected } = useServer();

  return (
    <aside className="hidden w-64 shrink-0 border-r bg-card md:flex md:flex-col">
      {/* La marca vive ahora en el Titlebar (franja superior). */}
      {/* FIEL status */}
      <div className="border-b px-4 py-3">
        <FielStatus />
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-1 px-3 py-4">
        {NAV_ITEMS.map(({ href, label, icon }) => {
          const isActive =
            href === '/' ? pathname === '/' : pathname.startsWith(href);

          return (
            <Link
              key={href}
              href={href}
              className={cn(
                'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                isActive
                  ? 'bg-accent text-accent-foreground'
                  : 'text-muted-foreground hover:bg-accent/50 hover:text-accent-foreground',
              )}
            >
              <Icon icon={icon} className="size-4 shrink-0" />
              {label}
            </Link>
          );
        })}
      </nav>

      {/* Server connection indicator */}
      <div className="border-t px-4 py-3">
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span
            className={cn(
              'size-2 shrink-0 rounded-full',
              isConnected ? 'bg-green-500' : 'bg-red-500',
            )}
          />
          <span>{isConnected ? 'Conectado' : 'Desconectado'}</span>
        </div>
      </div>
    </aside>
  );
}

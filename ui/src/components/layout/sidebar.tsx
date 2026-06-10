'use client';

import { useEffect, useState } from 'react';
import Image from 'next/image';
import Link from 'next/link';
import { usePathname } from 'next/navigation';

import { cn } from '@/lib/utils';
import { AccountMenu } from '@/components/layout/account-menu';
import { EmpresaSwitcher } from '@/components/layout/empresa-switcher';
import { Icon } from '@/components/ui/icon';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// Nav plano (Ajustes vive en el menú de cuenta; Ayuda en el footer).
const NAV_ITEMS = [
  { href: '/', label: 'Inicio', icon: 'ph:squares-four-light' },
  { href: '/empresas', label: 'Empresas', icon: 'ph:buildings-light' },
  { href: '/descarga', label: 'Descargar CFDIs', icon: 'ph:download-simple-light' },
  { href: '/comprobantes', label: 'Comprobantes', icon: 'ph:files-light' },
  { href: '/listas-negras', label: 'Listas negras', icon: 'ph:shield-check-light' },
  { href: '/organizador', label: 'Organizador', icon: 'ph:folders-light' },
  { href: '/historial', label: 'Historial', icon: 'ph:clock-counter-clockwise-light' },
] as const;

const COLLAPSED_KEY = 'tc:sidebar-collapsed';

function NavItem({
  href,
  label,
  icon,
  active,
  collapsed,
}: {
  href: string;
  label: string;
  icon: string;
  active: boolean;
  collapsed: boolean;
}) {
  const link = (
    <Link
      href={href}
      className={cn(
        'relative flex items-center gap-3 rounded-lg text-[13.5px] font-medium transition-colors',
        collapsed ? 'size-11 justify-center' : 'px-3 py-2',
        active
          ? 'bg-accent font-semibold text-primary'
          : 'text-muted-foreground hover:bg-secondary hover:text-foreground',
        // Barra azul del item activo, pegada al borde del sidebar.
        active &&
          'before:absolute before:-left-3 before:top-1/2 before:h-5.5 before:w-1 before:-translate-y-1/2 before:rounded-r before:bg-primary before:content-[""]',
        active && collapsed && 'before:-left-2.5',
      )}
    >
      <Icon
        icon={icon}
        className={cn('size-4.75 shrink-0', active ? 'text-primary' : '')}
      />
      {!collapsed && <span className="truncate">{label}</span>}
    </Link>
  );

  if (!collapsed) return link;
  return (
    <Tooltip>
      <TooltipTrigger asChild>{link}</TooltipTrigger>
      <TooltipContent side="right">{label}</TooltipContent>
    </Tooltip>
  );
}

/**
 * Sidebar v2: marca + selector de empresa + nav plano + footer (Ayuda y
 * cuenta). Colapsable a modo solo-iconos; el estado persiste en localStorage.
 * La conexión y el semáforo de e.firma viven en la barra de estado inferior.
 */
export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  // localStorage solo post-mount (export estático: el primer render del
  // servidor y del cliente deben coincidir).
  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSED_KEY) === '1');
  }, []);

  function toggleCollapsed() {
    setCollapsed((c) => {
      localStorage.setItem(COLLAPSED_KEY, c ? '0' : '1');
      return !c;
    });
  }

  return (
    <aside
      className={cn(
        'hidden shrink-0 border-r bg-sidebar transition-[width] duration-200 md:flex md:flex-col',
        collapsed ? 'w-17' : 'w-62',
      )}
    >
      {/* Marca */}
      <div
        className={cn(
          'flex items-center gap-2.5 pb-3 pt-4',
          collapsed ? 'justify-center px-0' : 'px-3.5',
        )}
      >
        <Image
          src="/todoconta-icon.svg"
          alt="TodoConta"
          width={34}
          height={34}
          className="shrink-0 rounded-lg shadow-sm"
        />
        {!collapsed && (
          <span className="flex-1 truncate text-[17px] font-extrabold tracking-tight text-foreground">
            TodoConta
          </span>
        )}
        {!collapsed && (
          <button
            onClick={toggleCollapsed}
            title="Colapsar menú"
            className="flex size-7.5 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <Icon icon="ph:sidebar-simple-light" className="size-4.5" />
          </button>
        )}
      </div>

      {/* Botón de expandir (solo colapsado, debajo de la marca) */}
      {collapsed && (
        <div className="flex justify-center pb-1">
          <button
            onClick={toggleCollapsed}
            title="Expandir menú"
            className="flex size-7.5 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <Icon icon="ph:sidebar-simple-light" className="size-4.5" />
          </button>
        </div>
      )}

      {/* Selector de empresa */}
      <div className={cn('pb-3', collapsed ? 'flex justify-center px-0' : 'px-3')}>
        <EmpresaSwitcher collapsed={collapsed} />
      </div>

      {/* Navegación */}
      <nav
        className={cn(
          'flex flex-1 flex-col gap-0.5 overflow-y-auto py-1',
          collapsed ? 'items-center px-2.5' : 'px-3',
        )}
      >
        {NAV_ITEMS.map(({ href, label, icon }) => (
          <NavItem
            key={href}
            href={href}
            label={label}
            icon={icon}
            collapsed={collapsed}
            active={href === '/' ? pathname === '/' : pathname.startsWith(href)}
          />
        ))}
      </nav>

      {/* Footer: Ayuda + cuenta */}
      <div
        className={cn(
          'flex flex-col gap-1 border-t py-2.5',
          collapsed ? 'items-center px-2.5' : 'px-3',
        )}
      >
        <NavItem
          href="/ayuda"
          label="Ayuda"
          icon="ph:question-light"
          collapsed={collapsed}
          active={pathname.startsWith('/ayuda')}
        />
        <AccountMenu collapsed={collapsed} />
      </div>
    </aside>
  );
}

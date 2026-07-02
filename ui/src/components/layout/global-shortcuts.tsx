'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useTheme } from 'next-themes';

import { EVENTO_PALETTE_OPEN, EVENTO_SIDEBAR_TOGGLE } from '@/lib/atajos';
import { NAV_ITEMS } from '@/lib/navegacion';
import { useAtajosGlobales, type AtajoGlobal } from '@/hooks/use-atajos-globales';
import {
  CommandPalette,
  type VistaPalette,
} from '@/components/layout/command-palette';

/**
 * Registro central de atajos de teclado (⌘ en mac, Ctrl en win/linux) y dueño
 * del estado del command palette. Se monta UNA sola vez, en la rama
 * autenticada del AppShell (sin atajos en login/splash).
 *
 * Tabla de referencia para el usuario: lib/atajos.ts (ATAJOS) → card en /ayuda.
 */
export function GlobalShortcuts() {
  const router = useRouter();
  const { resolvedTheme, setTheme } = useTheme();

  const [open, setOpen] = useState(false);
  const [vista, setVista] = useState<VistaPalette>('root');

  function abrir(v: VistaPalette) {
    setVista(v);
    setOpen(true);
  }

  // El ítem "Buscar" del sidebar abre el palette por evento window.
  useEffect(() => {
    const onAbrir = () => abrir('root');
    window.addEventListener(EVENTO_PALETTE_OPEN, onAbrir);
    return () => window.removeEventListener(EVENTO_PALETTE_OPEN, onAbrir);
  }, []);

  const atajos: AtajoGlobal[] = [
    // ⌘K: toggle del palette (siempre reabre en la vista principal).
    { tecla: 'k', accion: () => (open ? setOpen(false) : abrir('root')) },
    // ⌘E: directo al cambio de empresa; segundo ⌘E lo cierra.
    {
      tecla: 'e',
      accion: () =>
        open && vista === 'empresas' ? setOpen(false) : abrir('empresas'),
    },
    // ⇧⌘L: alternar tema (pisa "system" a propósito; /ajustes lo restaura).
    {
      tecla: 'l',
      shift: true,
      accion: () => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark'),
    },
    { tecla: ',', accion: () => router.push('/ajustes') },
    { tecla: 'b', accion: () => window.dispatchEvent(new Event(EVENTO_SIDEBAR_TOGGLE)) },
    { tecla: 'd', shift: true, accion: () => router.push('/descarga/rapida') },
    // ⌘N: el query param lo lee /empresas para abrir el alta (y lo limpia).
    { tecla: 'n', accion: () => router.push('/empresas?alta=1') },
    { tecla: 'f1', mod: false, accion: () => router.push('/ayuda') },
    // ⌘1..⌘7 por posición en NAV_ITEMS (ver nota de orden en lib/navegacion.ts).
    ...NAV_ITEMS.flatMap((item, i): AtajoGlobal[] => [
      { tecla: `Digit${i + 1}`, esCode: true, accion: () => router.push(item.href) },
      { tecla: `Numpad${i + 1}`, esCode: true, accion: () => router.push(item.href) },
    ]),
  ];

  useAtajosGlobales(atajos);

  return (
    <CommandPalette
      open={open}
      vista={vista}
      onOpenChange={setOpen}
      onVistaChange={setVista}
    />
  );
}

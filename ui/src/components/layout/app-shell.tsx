'use client';

import type { ReactNode } from 'react';

import { Sidebar } from '@/components/layout/sidebar';
import { Titlebar } from '@/components/layout/titlebar';
import { useEfirmaReminder } from '@/hooks/use-efirma-reminder';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  // Side-effect: dispara la notificación diaria si alguna e.firma del
  // catálogo vence en ≤30 días (dedup global por día en localStorage).
  useEfirmaReminder();

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Titlebar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6 md:p-8">{children}</main>
      </div>
    </div>
  );
}

'use client';

import type { ReactNode } from 'react';

import { FounderBanner } from '@/components/auth/founder-banner';
import { Sidebar } from '@/components/layout/sidebar';
import { StartupSplash } from '@/components/layout/startup-splash';
import { StatusBar } from '@/components/layout/status-bar';
import { Titlebar } from '@/components/layout/titlebar';
import { useEfirmaReminder } from '@/hooks/use-efirma-reminder';
import { useAuth } from '@/providers/auth-provider';
import LoginPage from '@/app/login/page';

interface AppShellProps {
  children: ReactNode;
}

export function AppShell({ children }: AppShellProps) {
  // Side-effect: dispara la notificación diaria si alguna e.firma del
  // catálogo vence en ≤30 días (dedup global por día en localStorage).
  useEfirmaReminder();

  const { license, loading } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen flex-col overflow-hidden">
        <Titlebar />
        <StartupSplash />
      </div>
    );
  }

  if (!license?.authenticated) {
    // Renderea el LoginPage inline (no navegamos). La URL no cambia; al
    // autenticarse, `useAuth()` re-renderea con el shell normal.
    return (
      <div className="flex h-screen flex-col overflow-hidden">
        <Titlebar />
        <div className="flex-1 overflow-y-auto">
          <LoginPage />
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <Titlebar />
      <FounderBanner />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto p-6 md:p-8">{children}</main>
      </div>
      <StatusBar />
    </div>
  );
}

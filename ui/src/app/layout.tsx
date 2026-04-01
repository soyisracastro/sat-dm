import type { Metadata } from 'next';
import './globals.css';
import { ServerProvider } from '@/providers/server-provider';
import { AppShell } from '@/components/layout/app-shell';
import { TooltipProvider } from '@/components/ui/tooltip';

export const metadata: Metadata = {
  title: 'SAT Descarga Masiva',
  description: 'Descarga masiva de CFDIs del SAT',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body>
        <ServerProvider>
          <TooltipProvider>
            <AppShell>{children}</AppShell>
          </TooltipProvider>
        </ServerProvider>
      </body>
    </html>
  );
}

import type { Metadata } from 'next';
import './globals.css';
import { AuthProvider } from '@/providers/auth-provider';
import { ServerProvider } from '@/providers/server-provider';
import { ThemeProvider } from '@/providers/theme-provider';
import { SonnerProvider } from '@/components/providers/sonner-provider';
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
    <html lang="es" suppressHydrationWarning>
      <body>
        <ThemeProvider>
          <ServerProvider>
            <AuthProvider>
              <TooltipProvider>
                <AppShell>{children}</AppShell>
              </TooltipProvider>
            </AuthProvider>
          </ServerProvider>
          <SonnerProvider />
        </ThemeProvider>
      </body>
    </html>
  );
}

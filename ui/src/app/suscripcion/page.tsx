'use client';

import { useState } from 'react';
import { toast } from 'sonner';

import { useAuth } from '@/providers/auth-provider';
import { useServer } from '@/providers/server-provider';
import { mensajeDeError } from '@/lib/errores';
import { diasRestantes, formatDate, formatPesosEnteros } from '@/lib/formatting';
import type { TransferIntentResponse } from '@/lib/api-client';
import { PageHeading } from '@/components/layout/page-heading';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Icon } from '@/components/ui/icon';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';

/**
 * Página interna de suscripción y cuenta (/suscripcion).
 *
 * - Estado del plan actual + cuenta regresiva.
 * - Si no paga (trial/free): plan anual con pago por tarjeta (Stripe) o por
 *   transferencia (datos bancarios + activación manual).
 * - Si es premium: cancelar la suscripción dentro de la app (al fin del periodo).
 * - Si es fundador: estado celebratorio (acceso de por vida).
 *
 * Ruta estática (cumple `output: 'export'`).
 */
export default function SuscripcionPage() {
  const { license, refresh } = useAuth();
  const { apiClient } = useServer();

  const [busyTarjeta, setBusyTarjeta] = useState(false);
  const [busyTransfer, setBusyTransfer] = useState(false);
  const [busyCancel, setBusyCancel] = useState(false);
  const [transfer, setTransfer] = useState<TransferIntentResponse | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);

  if (!license?.authenticated) return null;

  const plan = license.plan ?? 'free';
  const esFundador = plan === 'founder' || license.is_founder === true;
  const esPremium = plan === 'premium';
  const promoActive = license.promo_active === true;
  const precio = promoActive
    ? license.promo_price_mxn ?? 1495
    : license.regular_price_mxn ?? 2990;
  const regular = license.regular_price_mxn ?? 2990;

  async function pagarTarjeta() {
    if (busyTarjeta) return;
    setBusyTarjeta(true);
    try {
      const { url } = await apiClient.authSubscribe();
      window.open(url, '_blank', 'noopener,noreferrer');
      toast.info(
        'Te abrimos el navegador para pagar. Cuando termines, vuelve y toca "Actualizar estado".',
      );
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusyTarjeta(false);
    }
  }

  async function pedirTransferencia() {
    if (busyTransfer) return;
    setBusyTransfer(true);
    try {
      const res = await apiClient.authTransferIntent();
      setTransfer(res);
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusyTransfer(false);
    }
  }

  async function confirmarCancelar() {
    if (busyCancel) return;
    setBusyCancel(true);
    try {
      const res = await apiClient.authCancelSubscription();
      toast.success(
        res.message ??
          'Tu suscripción se cancelará al fin del periodo. Conservas el acceso hasta entonces.',
      );
      setCancelOpen(false);
      await refresh();
    } catch (e) {
      toast.error(mensajeDeError(e));
    } finally {
      setBusyCancel(false);
    }
  }

  async function copiar(texto: string, etiqueta: string) {
    try {
      await navigator.clipboard.writeText(texto);
      toast.success(`${etiqueta} copiada`);
    } catch {
      toast.error('No se pudo copiar');
    }
  }

  // -------- Estado actual --------
  const dias = license.days_remaining ?? null;
  const diasTxt = dias === null ? '' : dias === 1 ? '1 día' : `${dias} días`;
  const cancela = license.subscription_cancel_at_period_end === true;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <PageHeading
        title="Suscripción y cuenta"
        description="Tu plan, pagos y baja. La app sigue funcional siempre; la suscripción apoya el proyecto."
      />

      {/* Estado actual */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Icon
              icon={
                esFundador
                  ? 'ph:crown-simple-fill'
                  : esPremium
                    ? 'ph:crown-simple-fill'
                    : plan === 'trial'
                      ? 'ph:hourglass-medium-light'
                      : 'ph:user-light'
              }
              className={
                esFundador
                  ? 'size-5 text-amber-500'
                  : esPremium
                    ? 'size-5 text-violet-500'
                    : 'size-5 text-muted-foreground'
              }
            />
            {esFundador
              ? 'Miembro Fundador'
              : esPremium
                ? 'Suscripción activa'
                : plan === 'trial'
                  ? 'Periodo de prueba'
                  : 'Plan gratuito'}
          </CardTitle>
          <CardDescription>
            {esFundador
              ? 'Tienes acceso de por vida. Gracias por construir esto desde el inicio.'
              : esPremium
                ? cancela
                  ? `Programada para terminar el ${formatDate(license.expires_at ?? '')}. Conservas el acceso hasta esa fecha.`
                  : `Tu suscripción está vigente${license.expires_at ? `; se renueva el ${formatDate(license.expires_at)}` : ''}.`
                : plan === 'trial'
                  ? `Te ${dias === 1 ? 'queda' : 'quedan'} ${diasTxt} de prueba. Después podrás seguir usando la app.`
                  : 'Estás en el plan gratuito. Suscríbete para apoyar el proyecto.'}
          </CardDescription>
        </CardHeader>
        {license.email && (
          <CardContent className="text-sm text-muted-foreground">
            Cuenta: <span className="text-foreground">{license.email}</span>
          </CardContent>
        )}
      </Card>

      {/* Plan anual (solo si no paga) */}
      {!esFundador && !esPremium && (
        <Card className="border-primary/40">
          <CardHeader>
            <CardTitle className="flex items-center justify-between gap-2">
              <span className="flex items-center gap-2">
                <Icon icon="ph:crown-simple-light" className="size-5 text-primary" />
                Plan anual
              </span>
              {promoActive && (
                <span className="rounded-full bg-primary/10 px-2.5 py-0.5 text-xs font-bold text-primary">
                  50% de por vida
                </span>
              )}
            </CardTitle>
            <CardDescription>
              Acceso completo en la app de escritorio y, de regalo, a las
              herramientas premium en línea.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <div className="flex items-end gap-2">
              <span className="text-3xl font-bold tracking-tight">
                {formatPesosEnteros(precio)}
              </span>
              <span className="pb-1 text-sm text-muted-foreground">/ año</span>
              {promoActive && precio !== regular && (
                <span className="pb-1 text-sm text-muted-foreground line-through">
                  {formatPesosEnteros(regular)}
                </span>
              )}
            </div>

            {promoActive && (
              <Alert>
                <Icon icon="ph:percent-light" className="size-4" />
                <AlertTitle>Precio bloqueado de por vida</AlertTitle>
                <AlertDescription>
                  Conservas {formatPesosEnteros(precio)}/año mientras no canceles.
                  {license.promo_ends_at &&
                    ` Tu oferta termina en ${diasRestantes(license.promo_ends_at) ?? 0} días.`}
                </AlertDescription>
              </Alert>
            )}

            <div className="flex flex-wrap gap-2">
              <Button onClick={pagarTarjeta} disabled={busyTarjeta}>
                <Icon
                  icon={busyTarjeta ? 'ph:circle-notch-light' : 'ph:credit-card-light'}
                  className={busyTarjeta ? 'size-4 animate-spin' : 'size-4'}
                />
                Pagar con tarjeta
              </Button>
              <Button
                variant="outline"
                onClick={pedirTransferencia}
                disabled={busyTransfer}
              >
                <Icon
                  icon={busyTransfer ? 'ph:circle-notch-light' : 'ph:wallet-light'}
                  className={busyTransfer ? 'size-4 animate-spin' : 'size-4'}
                />
                Pagar por transferencia
              </Button>
              <Button variant="ghost" onClick={() => refresh()}>
                <Icon icon="ph:arrows-clockwise-light" className="size-4" />
                Actualizar estado
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Con tarjeta la activación es automática. Por transferencia puede
              tardar unas horas.
            </p>

            {/* Datos bancarios para transferencia */}
            {transfer && (
              <Alert variant="warning">
                <Icon icon="ph:wallet-light" className="size-4" />
                <AlertTitle>
                  Transfiere {formatPesosEnteros(transfer.amount_mxn)} y te activamos
                </AlertTitle>
                <AlertDescription>
                  <div className="mt-1 flex w-full flex-col gap-1.5 text-sm">
                    {transfer.banco.beneficiario && (
                      <DatoBancario
                        etiqueta="Beneficiario"
                        valor={transfer.banco.beneficiario}
                        onCopy={copiar}
                      />
                    )}
                    {transfer.banco.banco && (
                      <DatoBancario etiqueta="Banco" valor={transfer.banco.banco} onCopy={copiar} />
                    )}
                    {transfer.banco.clabe && (
                      <DatoBancario etiqueta="CLABE" valor={transfer.banco.clabe} onCopy={copiar} />
                    )}
                    {transfer.banco.referencia && (
                      <DatoBancario
                        etiqueta="Referencia"
                        valor={transfer.banco.referencia}
                        onCopy={copiar}
                      />
                    )}
                    {!transfer.banco.clabe && (
                      <span className="text-muted-foreground">
                        Los datos bancarios aún no están configurados. Contacta a
                        soporte.
                      </span>
                    )}
                  </div>
                  <p className="mt-2 text-xs">
                    {transfer.message ??
                      'La activación por transferencia puede tardar unas horas.'}{' '}
                    Envíanos tu comprobante para activar tu cuenta.
                  </p>
                </AlertDescription>
              </Alert>
            )}
          </CardContent>
        </Card>
      )}

      {/* Gestión (solo premium) */}
      {esPremium && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Icon icon="ph:gear-light" className="size-5 text-muted-foreground" />
              Gestionar suscripción
            </CardTitle>
            <CardDescription>
              Puedes cancelar cuando quieras. Conservas el acceso hasta el fin del
              periodo ya pagado.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {cancela ? (
              <Alert>
                <Icon icon="ph:info-light" className="size-4" />
                <AlertTitle>Cancelación programada</AlertTitle>
                <AlertDescription>
                  Tu suscripción terminará el {formatDate(license.expires_at ?? '')}{' '}
                  y no se renovará.
                </AlertDescription>
              </Alert>
            ) : (
              <Button variant="outline" onClick={() => setCancelOpen(true)}>
                <Icon icon="ph:x-circle-light" className="size-4" />
                Cancelar suscripción
              </Button>
            )}
          </CardContent>
        </Card>
      )}

      {/* Diálogo de confirmación de cancelación */}
      <Dialog open={cancelOpen} onOpenChange={setCancelOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>¿Cancelar tu suscripción?</DialogTitle>
            <DialogDescription>
              No se renovará al final del periodo. Conservas el acceso hasta
              {license.expires_at ? ` el ${formatDate(license.expires_at)}` : ' el fin del periodo'}.
              Pierdes el precio bloqueado de la promo si vuelves a suscribirte después.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setCancelOpen(false)} disabled={busyCancel}>
              Conservar
            </Button>
            <Button variant="destructive" onClick={confirmarCancelar} disabled={busyCancel}>
              {busyCancel && <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />}
              Sí, cancelar
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function DatoBancario({
  etiqueta,
  valor,
  onCopy,
}: {
  etiqueta: string;
  valor: string;
  onCopy: (texto: string, etiqueta: string) => void;
}) {
  return (
    <div className="flex items-center justify-between gap-2">
      <span className="text-muted-foreground">{etiqueta}</span>
      <span className="flex items-center gap-1.5">
        <span className="font-medium text-foreground">{valor}</span>
        <button
          type="button"
          onClick={() => onCopy(valor, etiqueta)}
          className="text-muted-foreground hover:text-foreground"
          aria-label={`Copiar ${etiqueta}`}
        >
          <Icon icon="ph:copy-light" className="size-4" />
        </button>
      </span>
    </div>
  );
}

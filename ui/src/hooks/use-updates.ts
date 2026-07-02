'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';

import { getUpdatesBridge, type UpdatesState } from '@/lib/updates';

/**
 * Suscribe al estado del auto-updater del main de Electron (vía el bridge del
 * preload `window.satDesktop.updates`): `getState()` en mount + `onChanged()`
 * para cambios incrementales, con cleanup al desmontar. En navegador (dev) el
 * bridge es null y `conUpdater` queda false (los consumidores ocultan su UI).
 *
 * Lo comparten la fila "Versión" de Ajustes y el chip del status bar, para no
 * duplicar la lógica de suscripción.
 */
export function useUpdates() {
  const bridge = useMemo(
    () => (typeof window !== 'undefined' ? getUpdatesBridge() : null),
    [],
  );
  const [updates, setUpdates] = useState<UpdatesState | null>(null);

  useEffect(() => {
    if (!bridge) return;
    let dispose: (() => void) | undefined;
    bridge
      .getState()
      .then((s) => {
        setUpdates(s);
        dispose = bridge.onChanged((nuevo) =>
          setUpdates((prev) => ({ ...prev, ...nuevo })),
        );
      })
      .catch(() => {});
    return () => dispose?.();
  }, [bridge]);

  const conUpdater = !!bridge && updates?.disponible === true;
  const ocupado =
    updates?.estado === 'buscando' || updates?.estado === 'descargando';

  const check = useCallback(
    () => bridge?.check().then(setUpdates).catch(() => {}),
    [bridge],
  );
  const install = useCallback(() => bridge?.install(), [bridge]);

  return { updates, bridge, conUpdater, ocupado, check, install };
}

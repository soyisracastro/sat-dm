'use client';

import { useEffect, useRef } from 'react';

import { detectarPlataforma } from '@/lib/atajos';

/**
 * Un atajo capturable. Por default lleva el modificador de la plataforma
 * (⌘ en mac, Ctrl en win/linux); `mod: false` es para teclas de función
 * (F1) que no producen texto — nunca usar `mod: false` con teclas
 * imprimibles o se dispararían al escribir en un input.
 */
export interface AtajoGlobal {
  /**
   * Con `esCode` false/omitido compara contra `e.key.toLowerCase()` ('k', ',');
   * con `esCode` true compara contra `e.code` ('Digit1') — robusto ante
   * layouts donde Shift/AltGr cambian el símbolo de la tecla física.
   */
  tecla: string;
  esCode?: boolean;
  shift?: boolean;
  mod?: boolean;
  accion: () => void;
}

/**
 * Listener global de keydown para los atajos de la app.
 *
 * DEBE montarse UNA sola vez (solo GlobalShortcuts lo usa); una segunda
 * instancia dispararía las acciones dos veces. Captura en `capture: true`
 * para sobrevivir a `stopPropagation` de componentes internos.
 *
 * Guards (en orden):
 * - `e.isComposing`: no interferir con IME.
 * - `e.repeat`: una acción por pulsación, aunque se mantenga la tecla.
 * - Modificador de la plataforma: ⌘ en mac, Ctrl en win/linux.
 * - `!e.altKey`: en Windows con teclado Latinoamericano, AltGr reporta
 *   `ctrlKey && altKey`; sin este guard, escribir '@' ('€', etc.) en un
 *   input dispararía atajos.
 * - Modificador cruzado (`!ctrlKey` en mac, `!metaKey` en win): no capturar
 *   combos híbridos que no son nuestros.
 */
export function useAtajosGlobales(atajos: AtajoGlobal[]): void {
  // Los handlers viven en un ref actualizado por render: el listener se
  // registra una sola vez y siempre ve las acciones (y closures) vigentes.
  const atajosRef = useRef(atajos);
  atajosRef.current = atajos;

  useEffect(() => {
    const { mac } = detectarPlataforma();

    function onKeyDown(e: KeyboardEvent) {
      if (e.isComposing || e.repeat) return;
      const conMod = mac ? e.metaKey : e.ctrlKey;

      const tecla = e.key.toLowerCase();
      const atajo = atajosRef.current.find((a) => {
        if (!!a.shift !== e.shiftKey) return false;
        if (!(a.esCode ? a.tecla === e.code : a.tecla === tecla)) return false;
        // Sin modificador (F1): ningún modificador presionado.
        if (a.mod === false) return !e.metaKey && !e.ctrlKey && !e.altKey;
        // Con modificador: el de la plataforma, sin Alt (AltGr) ni el cruzado.
        return conMod && !e.altKey && !(mac ? e.ctrlKey : e.metaKey);
      });
      if (!atajo) return;

      e.preventDefault();
      e.stopPropagation();
      atajo.accion();
    }

    window.addEventListener('keydown', onKeyDown, { capture: true });
    return () => window.removeEventListener('keydown', onKeyDown, { capture: true });
  }, []);
}

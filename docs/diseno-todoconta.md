# Alineación de diseño con TodoConta Apps

Este doc documenta dónde estamos parados respecto al sistema de diseño del web
(`todoconta-apps/apps/web`) para que sat-descarga-masiva sienta el mismo ambiente.

## Estado actual

**Ya está alineado** (no requiere trabajo):
- **Colores**: primary `#0B5FFF` (Azul Legal), success, destructive, warning, background,
  card, accent — los mismos tokens que TodoConta, en `ui/src/app/globals.css`.
- **Fuente**: Inter (Google Fonts) cargada en `globals.css`.
- **Dark mode**: tokens `.dark` definidos.
- **shadcn**: estilo `new-york`, alias `@/*` iguales.
- **Iconos**: `@iconify/react` + Phosphor light (`@iconify-icons/ph`), wrapper `Icon`
  en `ui/src/components/ui/icon.tsx` y registro en `ui/src/lib/icons.ts`. Mismos nombres
  Phosphor que el web (download-simple, circle-notch, key, gear, ...). **Lucide eliminado.**

**Convención de iconos** (heredada del web):
- Usar `<Icon icon="ph:<name>-light" className="..." />`. Stroke 1.5px.
- Tamaños: `size-3` / `size-3.5` (en badges), `size-4` (inline), `size-5` (botones medianos),
  `size-6`/`size-8` (cards/hero).
- Spinner: `<Icon icon="ph:circle-notch-light" className="animate-spin" />`.
- Para registrar un icono nuevo: `import x from '@iconify-icons/ph/<name>-light'` y
  `addIcon('ph:<name>-light', x)` en `lib/icons.ts`.
- Cuando `shadcn add <componente>` reintroduzca `lucide-react`, hay que adaptarlo a Icon
  manualmente (`components.json` ya no declara `iconLibrary`).

## Roadmap de componentes a reusar del web

Análisis de qué se puede tomar de `todoconta-apps/apps/web/src/components` y portar acá,
con su veredicto. Esta app **no tiene** Supabase/Zustand/Stripe/auth: hay que quitar esas
deps al portar (cambiar stores/API por props/callbacks).

### Prioridad alta (presentacionales, casi tal cual)

| Origen | Componente | Qué hace | Adaptación |
|---|---|---|---|
| `components/shared/EmptyState.tsx` | `EmptyState` | Estado vacío con icono+título+CTA. | Portar tal cual (depende solo de `Icon` + `Button`). |
| `components/shared/StatusBadge.tsx` | `StatusBadge` | Badge con tonos `success`/`warning`/`error`/`info`/`neutral`/`ai`. | Portar tal cual (depende de `cva` + `Icon`). Unificaría `VencimientoBadge` y otros badges ad-hoc. |
| `components/shared/StatusIndicator.tsx` | `StatusIndicator` | Indicador inline icono+texto para estados. | Portar tal cual. |
| `components/shared/ResourceList.tsx` | `ResourceList` | Lista genérica con columnas, expand y acciones. | Portar tal cual. Reemplazo natural de la tabla del Historial y candidatos en Empresas. |

### Prioridad media (adaptables)

| Origen | Componente | Qué hace | Adaptación |
|---|---|---|---|
| `components/descarga-masiva/solicitud-status-config.ts` | `SOLICITUD_STATUS_CONFIG` | Config pura de estados de solicitud SAT (etiqueta + tono + icono). | Portar tal cual. Útil para Descarga WS / Historial. |
| `components/descarga-masiva/SolicitudRowExpanded.tsx` | `SolicitudRowExpanded` | Detalle expandido de una solicitud (sólo presentacional). | Portar tal cual; reemplaza `PollingDisplay` parcialmente. |
| `components/descarga-masiva/DescargaForm.tsx` | `DescargaForm` | Form de fechas/tipos para solicitar descarga. | Adaptar: quitar `useEmpresaActiva` (Zustand) y recibir la empresa como prop. |
| `components/empresa/EmpresaCombobox.tsx` | `EmpresaCombobox` | Selector de empresa con búsqueda + favoritas. | Adaptar: callbacks (`onSelect`, `onToggleFavorite`) en vez de stores. |
| `components/empresa/EmpresaStatusCells.tsx` | `getFielStatus` | Función pura que clasifica vigencia FIEL en tonos. | Portar la función; nuestro `semaforoVencimiento` ya cumple esa misión — vale unificar. |
| `components/empresa/FielUploadDialog.tsx` | `FielUploadDialog` | Dialog para subir .cer/.key/password. | Adaptar: nuestra versión ya cumple; usar el web como referencia de UX/microcopy. |

### Solo referencia de diseño (no portar)

- `components/layout/Sidebar.tsx`, `Layout.tsx` — específicos de Next.js web (auth, routing, mobile drawer). Nuestra sidebar ya tiene la misma estructura visual.
- `components/auth/*` — Supabase only.
- `components/providers/ThemeProvider.tsx` — `next-themes`. Si quisiéramos toggle de tema, adaptar con un context propio (los tokens `.dark` ya existen).
- `components/cfdis/CfdiDetailDialog.tsx` — útil como referencia para un futuro "Detalle de CFDI" cuando agreguemos esa pantalla; depende de API de Next.js.

## Próximos PRs sugeridos (en orden)

1. **Adoptar `shared/`** (`StatusBadge`, `StatusIndicator`, `EmptyState`, `ResourceList`) → refactor de empty states y badges actuales para unificar el look.
2. **`solicitud-status-config` + `SolicitudRowExpanded`** → mejorar la pantalla Descarga WS y enriquecer el Historial.
3. **`EmpresaCombobox`** → cambiar el selector de empresa activa actual por el combobox con búsqueda + favoritas (gran upgrade UX).
4. **Tema (opcional)** → toggle dark/light si el usuario lo pide; los tokens ya están listos.

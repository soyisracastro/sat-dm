import '@/lib/icons';
import { Icon as IconifyIcon, type IconProps as IconifyIconProps } from '@iconify/react';

export type IconProps = IconifyIconProps;

// Wrapper sobre @iconify/react: importa el registro de iconos (lib/icons) y re-exporta
// el componente. Uso: <Icon icon="ph:check-light" className="size-4" />.
export function Icon(props: IconProps) {
  return <IconifyIcon {...props} />;
}

'use client';

import * as React from 'react';
import Link from 'next/link';
import { Icon } from '@/components/ui/icon';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

type Size = 'sm' | 'default';

export type ResourceAction =
  | {
      icon: string;
      label: string;
      onClick?: (e: React.MouseEvent) => void;
      href?: string;
      destructive?: boolean;
      disabled?: boolean;
      iconOnly?: boolean;
    }
  | {
      render: () => React.ReactNode;
    };

interface ResourceActionsProps {
  actions: ResourceAction[];
  size?: Size;
  className?: string;
  /**
   * When the actions live inside a clickable row, set to true so each button
   * stops click propagation automatically.
   */
  stopPropagation?: boolean;
}

export function ResourceActions({
  actions,
  size = 'sm',
  className,
  stopPropagation = true,
}: ResourceActionsProps) {
  return (
    <div
      className={cn('flex items-center gap-1', className)}
      onClick={stopPropagation ? (e) => e.stopPropagation() : undefined}
    >
      {actions.map((action, idx) =>
        'render' in action ? (
          <React.Fragment key={idx}>{action.render()}</React.Fragment>
        ) : (
          <ActionButton key={idx} action={action} size={size} />
        ),
      )}
    </div>
  );
}

function ActionButton({
  action,
  size,
}: {
  action: Extract<ResourceAction, { icon: string }>;
  size: Size;
}) {
  const { icon, label, onClick, href, destructive, disabled, iconOnly } = action;

  const buttonSize: 'sm' | 'icon' = iconOnly ? 'icon' : size === 'sm' ? 'sm' : 'sm';
  const variant = 'ghost' as const;
  const destructiveClass = destructive
    ? 'text-muted-foreground hover:text-destructive hover:bg-destructive/10'
    : 'text-muted-foreground hover:text-foreground';

  const iconClass = size === 'sm' ? 'size-3.5' : 'size-4';

  if (href) {
    return (
      <Button
        asChild
        variant={variant}
        size={iconOnly ? 'icon' : buttonSize}
        className={destructiveClass}
      >
        <Link href={href} title={label}>
          <Icon icon={icon} className={iconClass} />
          {!iconOnly && <span className={size === 'sm' ? 'ml-1.5' : 'ml-2'}>{label}</span>}
        </Link>
      </Button>
    );
  }

  return (
    <Button
      variant={variant}
      size={iconOnly ? 'icon' : buttonSize}
      onClick={onClick}
      disabled={disabled}
      title={label}
      className={destructiveClass}
    >
      <Icon icon={icon} className={iconClass} />
      {!iconOnly && <span className={size === 'sm' ? 'ml-1.5' : 'ml-2'}>{label}</span>}
    </Button>
  );
}

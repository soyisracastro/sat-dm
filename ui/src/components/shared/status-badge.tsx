'use client';

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';

export type StatusTone = 'success' | 'warning' | 'error' | 'info' | 'neutral' | 'ai';

const statusBadgeVariants = cva(
  'inline-flex items-center gap-1.5 rounded-full border font-medium transition-colors whitespace-nowrap',
  {
    variants: {
      tone: {
        success:
          'bg-success/10 text-success border-success/20 dark:bg-success/15 dark:border-success/30',
        warning:
          'bg-warning/10 text-warning border-warning/20 dark:bg-warning/15 dark:border-warning/30',
        error:
          'bg-destructive/10 text-destructive border-destructive/20 dark:bg-destructive/15 dark:border-destructive/30',
        info: 'bg-primary/10 text-primary border-primary/20 dark:bg-primary/15 dark:border-primary/30',
        neutral: 'bg-muted text-muted-foreground border-border',
        ai: 'bg-accent-ai/10 text-accent-ai border-accent-ai/20 dark:bg-accent-ai/15 dark:border-accent-ai/30',
      },
      size: {
        sm: 'px-2 py-0.5 text-[10px]',
        default: 'px-2.5 py-0.5 text-xs',
      },
    },
    defaultVariants: {
      tone: 'neutral',
      size: 'default',
    },
  },
);

const iconSizeMap = {
  sm: 'size-2.5',
  default: 'size-3',
} as const;

export interface StatusBadgeProps
  extends React.HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof statusBadgeVariants> {
  icon?: string;
  pulse?: boolean;
}

export function StatusBadge({
  className,
  tone,
  size,
  icon,
  pulse = false,
  children,
  ...props
}: StatusBadgeProps) {
  const iconClass = iconSizeMap[size ?? 'default'];

  return (
    <span className={cn(statusBadgeVariants({ tone, size }), className)} {...props}>
      {icon && <Icon icon={icon} className={cn(iconClass, pulse && 'animate-spin')} />}
      {children}
    </span>
  );
}

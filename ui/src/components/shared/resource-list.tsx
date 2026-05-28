'use client';

import * as React from 'react';
import { cn } from '@/lib/utils';
import { Icon } from '@/components/ui/icon';

export interface ResourceListColumn<T> {
  key: string;
  header?: React.ReactNode;
  render: (item: T) => React.ReactNode;
  /** Tailwind width class (e.g. 'w-24', 'w-32'). Omit for flex-1. */
  width?: string;
  /** Hide on small screens (<640px). */
  hideOnMobile?: boolean;
  /** Right-align content. */
  align?: 'left' | 'right' | 'center';
  /** Tailwind className applied to the cell wrapper. */
  className?: string;
}

interface ResourceListProps<T> {
  items: T[];
  columns: ResourceListColumn<T>[];
  getKey: (item: T) => string;
  actions?: (item: T) => React.ReactNode;
  actionsHeader?: React.ReactNode;
  expandable?: {
    render: (item: T) => React.ReactNode;
    /** Return false to hide the chevron for specific items. */
    enabled?: (item: T) => boolean;
  };
  onRowClick?: (item: T) => void;
  activeId?: string | null;
  /** Dim all rows (used for archived lists). */
  dimmed?: boolean;
  className?: string;
}

export function ResourceList<T>({
  items,
  columns,
  getKey,
  actions,
  actionsHeader,
  expandable,
  onRowClick,
  activeId,
  dimmed = false,
  className,
}: ResourceListProps<T>) {
  const [expandedKeys, setExpandedKeys] = React.useState<Set<string>>(new Set());

  const toggleExpanded = (key: string) => {
    setExpandedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };

  const hasHeaders = columns.some((c) => c.header !== undefined) || actionsHeader !== undefined;

  return (
    <div
      className={cn(
        'overflow-hidden rounded-lg border border-border bg-card',
        dimmed && 'opacity-60',
        className,
      )}
    >
      {hasHeaders && (
        <div className="flex items-center border-b border-border bg-muted/30 px-3 py-2 text-xs font-medium text-muted-foreground">
          {expandable && <div className="w-6 shrink-0" />}
          {columns.map((col) => (
            <div
              key={col.key}
              className={cn(
                'px-2',
                col.width ?? 'flex-1 min-w-0',
                col.hideOnMobile && 'hidden sm:block',
                col.align === 'right' && 'text-right',
                col.align === 'center' && 'text-center',
              )}
            >
              {col.header}
            </div>
          ))}
          {actions && <div className="shrink-0 px-2 text-right">{actionsHeader}</div>}
        </div>
      )}

      <ul className="divide-y divide-border">
        {items.map((item) => {
          const key = getKey(item);
          const isExpanded = expandedKeys.has(key);
          const isActive = activeId === key;
          const canExpand = expandable && (expandable.enabled?.(item) ?? true);
          const clickable = Boolean(onRowClick);

          return (
            <li key={key}>
              <div
                className={cn(
                  'flex items-center px-3 py-2.5 transition-colors',
                  clickable && 'cursor-pointer hover:bg-muted/40',
                  isActive && 'bg-primary/5 ring-1 ring-inset ring-primary/40',
                )}
                onClick={clickable ? () => onRowClick!(item) : undefined}
                role={clickable ? 'button' : undefined}
                tabIndex={clickable ? 0 : undefined}
                onKeyDown={
                  clickable
                    ? (e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          onRowClick!(item);
                        }
                      }
                    : undefined
                }
              >
                {expandable && (
                  <button
                    type="button"
                    className={cn(
                      'flex w-6 shrink-0 items-center justify-center rounded text-muted-foreground transition-colors hover:text-foreground',
                      !canExpand && 'invisible',
                    )}
                    onClick={(e) => {
                      e.stopPropagation();
                      if (canExpand) toggleExpanded(key);
                    }}
                    aria-label={isExpanded ? 'Colapsar' : 'Expandir'}
                    aria-expanded={isExpanded}
                  >
                    <Icon
                      icon="ph:caret-down-light"
                      className={cn(
                        'size-4 transition-transform',
                        isExpanded && 'rotate-180',
                      )}
                    />
                  </button>
                )}

                {columns.map((col) => (
                  <div
                    key={col.key}
                    className={cn(
                      'min-w-0 overflow-hidden px-2 text-sm',
                      col.width ?? 'flex-1',
                      col.hideOnMobile && 'hidden sm:block',
                      col.align === 'right' && 'text-right',
                      col.align === 'center' && 'text-center',
                      col.className,
                    )}
                  >
                    {col.render(item)}
                  </div>
                ))}

                {actions && (
                  <div className="shrink-0 px-2" onClick={(e) => e.stopPropagation()}>
                    {actions(item)}
                  </div>
                )}
              </div>

              {expandable && canExpand && isExpanded && (
                <div className="border-t border-border bg-muted/20 px-3 py-3 sm:pl-11">
                  {expandable.render(item)}
                </div>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

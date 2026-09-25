import { X } from "lucide-react";
import type { PropsWithChildren, ReactNode } from "react";

import { Button } from "./Button";

type DrawerProps = PropsWithChildren<{
  open: boolean;
  title: string;
  subtitle?: string;
  onClose: () => void;
  actions?: ReactNode;
}>;

export function Drawer({
  open,
  title,
  subtitle,
  onClose,
  actions,
  children,
}: DrawerProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="drawer-backdrop" role="presentation" onMouseDown={onClose}>
      <aside
        className="drawer"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="drawer__header">
          <div>
            <h2>{title}</h2>
            {subtitle && <p>{subtitle}</p>}
          </div>
          <Button
            type="button"
            variant="ghost"
            className="drawer__close"
            onClick={onClose}
            aria-label="Fechar"
          >
            <X size={18} />
          </Button>
        </header>
        {actions && <div className="drawer__actions">{actions}</div>}
        <div className="drawer__content">{children}</div>
      </aside>
    </div>
  );
}

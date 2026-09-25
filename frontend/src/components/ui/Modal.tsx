import { X } from "lucide-react";
import type { PropsWithChildren, ReactNode } from "react";

import { Button } from "./Button";

type ModalProps = PropsWithChildren<{
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
}>;

export function Modal({
  open,
  title,
  description,
  onClose,
  footer,
  size = "md",
  children,
}: ModalProps) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className={`modal modal--${size}`}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="modal__header">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          <Button
            type="button"
            variant="ghost"
            className="modal__close"
            onClick={onClose}
            aria-label="Fechar"
          >
            <X size={18} />
          </Button>
        </header>
        <div className="modal__content">{children}</div>
        {footer && <footer className="modal__footer">{footer}</footer>}
      </section>
    </div>
  );
}

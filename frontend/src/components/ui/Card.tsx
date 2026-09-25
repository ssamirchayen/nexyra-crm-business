import type { PropsWithChildren, ReactNode } from "react";

type CardProps = PropsWithChildren<{
  title?: string;
  description?: string;
  actions?: ReactNode;
  className?: string;
}>;

export function Card({
  title,
  description,
  actions,
  className = "",
  children,
}: CardProps) {
  return (
    <section className={`card ${className}`.trim()}>
      {(title || description || actions) && (
        <header className="card__header">
          <div>
            {title && <h2 className="card__title">{title}</h2>}
            {description && (
              <p className="card__description">{description}</p>
            )}
          </div>
          {actions && <div className="card__actions">{actions}</div>}
        </header>
      )}
      <div className="card__content">{children}</div>
    </section>
  );
}

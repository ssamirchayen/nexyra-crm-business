import { ChevronRight } from "lucide-react";

import { Card } from "../components/ui/Card";

type PlaceholderPageProps = {
  title: string;
  description: string;
};

export function PlaceholderPage({
  title,
  description,
}: PlaceholderPageProps) {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="page-eyebrow">Nexyra CRM</p>
          <h1>{title}</h1>
          <p>{description}</p>
        </div>
      </header>

      <Card>
        <div className="placeholder-panel">
          <div className="placeholder-panel__icon">
            <ChevronRight size={22} />
          </div>
          <div>
            <strong>Módulo preparado</strong>
            <p>
              A estrutura visual e a rota já existem. A implementação funcional
              entra nas próximas etapas da Sprint 2.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

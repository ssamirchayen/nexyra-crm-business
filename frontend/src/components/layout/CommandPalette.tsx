import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  CircleDollarSign,
  ContactRound,
  Gauge,
  LayoutDashboard,
  Search,
  Settings,
  Sparkles,
  ShieldCheck,
  UsersRound,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

type CommandPaletteProps = {
  open: boolean;
  onClose: () => void;
};

const commands = [
  { label: "Visão geral", description: "Dashboard comercial", to: "/overview", icon: LayoutDashboard },
  { label: "Dashboard operacional", description: "SLA, riscos, WhatsApp e cadências", to: "/operational-dashboard", icon: Gauge },
  { label: "Leads", description: "Cadastro, busca e filtros", to: "/leads", icon: ContactRound },
  { label: "Pipeline", description: "Kanban de oportunidades", to: "/pipeline", icon: BriefcaseBusiness },
  { label: "Oportunidades", description: "Negociações e histórico", to: "/opportunities", icon: CircleDollarSign },
  { label: "Atividades", description: "Tarefas e follow-ups", to: "/activities", icon: Activity },
  { label: "Recomendações", description: "Próximo melhor passo comercial", to: "/recommendations", icon: Sparkles },
  { label: "Equipe", description: "Vendedores e permissões", to: "/team", icon: UsersRound },
  { label: "Relatórios", description: "Analytics e exportações", to: "/reports", icon: BarChart3 },
  { label: "Auditoria", description: "Rastreabilidade do CRM", to: "/audit", icon: ShieldCheck },
  { label: "Configurações", description: "Empresa, pipeline e preferências", to: "/settings", icon: Settings },
];

export function CommandPalette({ open, onClose }: CommandPaletteProps) {
  const [query, setQuery] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (!open) {
      setQuery("");
      return;
    }

    const timer = window.setTimeout(() => inputRef.current?.focus(), 20);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };

    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [onClose, open]);

  const filtered = useMemo(() => {
    const normalized = query.trim().toLocaleLowerCase("pt-BR");
    if (!normalized) return commands;

    return commands.filter((item) =>
      `${item.label} ${item.description}`.toLocaleLowerCase("pt-BR").includes(normalized),
    );
  }, [query]);

  if (!open) return null;

  const openCommand = (to: string) => {
    navigate(to);
    onClose();
  };

  return (
    <div className="command-palette-backdrop" role="presentation" onMouseDown={onClose}>
      <section
        className="command-palette"
        role="dialog"
        aria-modal="true"
        aria-label="Navegação rápida"
        onMouseDown={(event) => event.stopPropagation()}
      >
        <header className="command-palette__search">
          <Search size={18} />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && filtered[0]) {
                openCommand(filtered[0].to);
              }
            }}
            placeholder="Ir para uma área do CRM..."
          />
          <button type="button" className="icon-button icon-button--compact" onClick={onClose} aria-label="Fechar">
            <X size={16} />
          </button>
        </header>

        <div className="command-palette__results">
          {filtered.length ? (
            filtered.map(({ label, description, to, icon: Icon }) => (
              <button key={to} type="button" className="command-item" onClick={() => openCommand(to)}>
                <span className="command-item__icon"><Icon size={18} /></span>
                <span className="command-item__copy">
                  <strong>{label}</strong>
                  <small>{description}</small>
                </span>
                <kbd>Enter</kbd>
              </button>
            ))
          ) : (
            <div className="command-palette__empty">Nenhuma área encontrada.</div>
          )}
        </div>

        <footer className="command-palette__footer">
          <span><kbd>Ctrl</kbd> <kbd>K</kbd> abrir</span>
          <span><kbd>Esc</kbd> fechar</span>
        </footer>
      </section>
    </div>
  );
}

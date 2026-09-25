import {
  Activity,
  ChevronDown,
  LogOut,
  Menu,
  Moon,
  Search,
  ShieldCheck,
  Sun,
} from "lucide-react";
import { useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../../contexts/AuthContext";
import { useTheme } from "../../contexts/ThemeContext";
import { useWorkspace } from "../../contexts/WorkspaceContext";
import type { ApiStatus } from "../../hooks/useApiStatus";

type TopbarProps = {
  apiStatus: ApiStatus;
  onOpenCommands: () => void;
  onOpenMenu: () => void;
};

const pageNames: Record<string, string> = {
  "/overview": "Visão geral",
  "/leads": "Leads",
  "/pipeline": "Pipeline",
  "/opportunities": "Oportunidades",
  "/activities": "Atividades",
  "/team": "Equipe",
  "/reports": "Relatórios",
  "/audit": "Auditoria",
  "/settings": "Configurações",
  "/security": "Segurança",
};

const roleNames: Record<string, string> = {
  admin: "Administrador",
  manager: "Gerente",
  seller: "Vendedor",
  operator: "Operador",
};

function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (!parts.length) {
    return "NX";
  }

  return `${parts[0]?.[0] ?? ""}${parts[1]?.[0] ?? ""}`.toUpperCase();
}

export function Topbar({ apiStatus, onOpenCommands, onOpenMenu }: TopbarProps) {
  const auth = useAuth();
  const { theme, toggleTheme } = useTheme();
  const { workspace } = useWorkspace();
  const location = useLocation();
  const navigate = useNavigate();
  const pageName = pageNames[location.pathname] ?? "Nexyra CRM";
  const currentAccess = auth.workspaces.find(
    (item) => item.public_id === workspace?.public_id,
  );

  return (
    <header className="topbar">
      <div className="topbar__left">
        <button className="icon-button topbar__menu-button" type="button" onClick={onOpenMenu} aria-label="Abrir menu">
          <Menu size={18} />
        </button>
        <div className="topbar__page-title">
          <strong>{pageName}</strong>
          <span>{workspace?.name ?? "Nenhuma empresa selecionada"}</span>
        </div>
        <button className="topbar__search" type="button" onClick={onOpenCommands}>
          <Search size={18} strokeWidth={1.8} />
          <span>Pesquisar ou navegar...</span>
          <kbd>Ctrl K</kbd>
        </button>
      </div>

      <div className="topbar__actions">
        <span className={`api-status api-status--${apiStatus}`}>
          <span className="api-status__dot" />
          {apiStatus === "online" ? "API online" : apiStatus === "checking" ? "Verificando" : "API offline"}
        </span>

        <button className="icon-button" type="button" onClick={toggleTheme} aria-label="Alternar tema">
          {theme === "light" ? <Moon size={18} strokeWidth={1.8} /> : <Sun size={18} strokeWidth={1.8} />}
        </button>

        <button className="icon-button" type="button" aria-label="Abrir atividades" onClick={() => navigate("/activities")}>
          <Activity size={18} strokeWidth={1.8} />
        </button>

        <details className="profile-menu">
          <summary className="profile-button" aria-label="Abrir menu do usuário">
            <span className="avatar">{initials(auth.user?.name ?? "Nexyra")}</span>
            <span className="profile-copy">
              <strong>{auth.user?.name ?? "Usuário"}</strong>
              <small>{roleNames[currentAccess?.role ?? ""] ?? currentAccess?.role ?? "Usuário"}</small>
            </span>
            <ChevronDown size={15} />
          </summary>
          <div className="profile-menu__popover">
            <div className="profile-menu__identity">
              <strong>{auth.user?.name}</strong>
              <span>{auth.user?.email}</span>
            </div>
            <div className="profile-menu__meta">
              <span>{workspace?.name ?? "Sem empresa selecionada"}</span>
              <small>{roleNames[currentAccess?.role ?? ""] ?? currentAccess?.role}</small>
            </div>
            <button type="button" onClick={() => navigate("/security")}>
              <ShieldCheck size={16} />
              Segurança da conta
            </button>
            <button type="button" onClick={() => void auth.logout()}>
              <LogOut size={16} />
              Sair do CRM
            </button>
          </div>
        </details>
      </div>
    </header>
  );
}

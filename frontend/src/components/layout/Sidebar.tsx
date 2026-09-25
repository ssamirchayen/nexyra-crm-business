import {
  Activity,
  BarChart3,
  BriefcaseBusiness,
  Building2,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Clock3,
  ContactRound,
  Gauge,
  LayoutDashboard,
  MessageCircle,
  MessagesSquare,
  Settings,
  Sparkles,
  ShieldCheck,
  UsersRound,
  Workflow,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";

import { useWorkspace } from "../../contexts/WorkspaceContext";

const navigation = [
  { to: "/overview", label: "Visão geral", icon: LayoutDashboard },
  { to: "/operational-dashboard", label: "Dashboard operacional", icon: Gauge },
  { to: "/leads", label: "Leads", icon: ContactRound },
  { to: "/service-queue", label: "Fila inteligente", icon: Clock3 },
  { to: "/cadences", label: "Cadências", icon: Workflow },
  { to: "/communication", label: "Comunicação", icon: MessagesSquare },
  { to: "/pipeline", label: "Pipeline", icon: BriefcaseBusiness },
  { to: "/opportunities", label: "Oportunidades", icon: CircleDollarSign },
  { to: "/activities", label: "Atividades", icon: Activity },
  { to: "/inbox", label: "Caixa de entrada", icon: MessageCircle },
  { to: "/recommendations", label: "Recomendações", icon: Sparkles },
  { to: "/team", label: "Equipe", icon: UsersRound },
  { to: "/reports", label: "Relatórios", icon: BarChart3 },
  { to: "/audit", label: "Auditoria", icon: ShieldCheck },
];

type SidebarProps = {
  collapsed: boolean;
  mobileOpen: boolean;
  onToggle: () => void;
  onCloseMobile: () => void;
};

export function Sidebar({ collapsed, mobileOpen, onToggle, onCloseMobile }: SidebarProps) {
  const { workspaces, workspace, loading, selectWorkspace } = useWorkspace();

  return (
    <>
      {mobileOpen && <button type="button" className="sidebar-backdrop" onClick={onCloseMobile} aria-label="Fechar menu" />}
      <aside className={`sidebar ${collapsed ? "sidebar--collapsed" : ""} ${mobileOpen ? "sidebar--mobile-open" : ""}`}>
        <div className="sidebar__brand">
          <div className="brand-mark">N</div>
          {!collapsed && (
            <div className="brand-copy"><strong>Nexyra</strong><span>CRM</span></div>
          )}
          <button type="button" className="sidebar__mobile-close" onClick={onCloseMobile} aria-label="Fechar menu">
            <X size={18} />
          </button>
        </div>

        <div className="sidebar__workspace">
          <div className="workspace-icon"><Building2 size={18} /></div>
          {!collapsed && (
            <div className="workspace-copy workspace-copy--select">
              <span className="workspace-copy__label">Empresa atual</span>
              {loading ? (
                <strong>Carregando...</strong>
              ) : workspaces.length > 1 ? (
                <select aria-label="Selecionar empresa" value={workspace?.public_id ?? ""} onChange={(event) => selectWorkspace(event.target.value)}>
                  {workspaces.map((item) => <option key={item.public_id} value={item.public_id}>{item.name}</option>)}
                </select>
              ) : (
                <strong>{workspace?.name ?? "Nenhuma empresa"}</strong>
              )}
            </div>
          )}
        </div>

        <nav className="sidebar__nav" aria-label="Navegação principal">
          {navigation.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} onClick={onCloseMobile} className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
              <Icon size={19} strokeWidth={1.8} />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          ))}
        </nav>

        <div className="sidebar__bottom">
          <NavLink to="/security" onClick={onCloseMobile} className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
            <ShieldCheck size={19} strokeWidth={1.8} />
            {!collapsed && <span>Segurança</span>}
          </NavLink>
          <NavLink to="/settings" onClick={onCloseMobile} className={({ isActive }) => `nav-item ${isActive ? "nav-item--active" : ""}`}>
            <Settings size={19} strokeWidth={1.8} />
            {!collapsed && <span>Configurações</span>}
          </NavLink>

          {!collapsed && <span className="sidebar__version">CRM 1.0 · Sessão autenticada</span>}

          <button className="sidebar__collapse" type="button" onClick={onToggle} aria-label={collapsed ? "Expandir menu" : "Recolher menu"}>
            {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            {!collapsed && <span>Recolher menu</span>}
          </button>
        </div>
      </aside>
    </>
  );
}

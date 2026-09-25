import {
  BriefcaseBusiness,
  CircleDollarSign,
  FilterX,
  RefreshCw,
  Search,
  ShieldCheck,
  UserPlus,
  UsersRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { TeamMemberDetailsDrawer } from "../components/team/TeamMemberDetailsDrawer";
import { TeamMemberFormModal } from "../components/team/TeamMemberFormModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type {
  RoleDefinition,
  TeamMember,
  TeamMemberCreatePayload,
  TeamMemberUpdatePayload,
  TeamRole,
  TeamSummary,
} from "../types/team";

const roleLabels: Record<TeamRole, string> = {
  admin: "Administrador",
  manager: "Gestor",
  seller: "Vendedor",
  operator: "Operador",
};

const roleTones: Record<TeamRole, "info" | "success" | "warning" | "neutral"> = {
  admin: "info",
  manager: "success",
  seller: "warning",
  operator: "neutral",
};

function currency(value: string) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

export function TeamPage() {
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const { user, workspaces, refreshSession } = useAuth();
  const access = workspaces.find((item) => item.public_id === workspace?.public_id);
  const isAdmin = access?.role === "admin";
  const canCreate = access?.permissions.includes("members.create") ?? false;
  const canChangeStatus = access?.permissions.includes("members.deactivate") ?? false;
  const allowedRoles: TeamRole[] = isAdmin
    ? ["admin", "manager", "seller", "operator"] : ["seller", "operator"];
  function canEdit(member: TeamMember) {
    return !!access?.permissions.includes("members.update") &&
      (isAdmin || (member.role !== "admin" && member.role !== "manager"));
  }
  const [summary, setSummary] = useState<TeamSummary | null>(null);
  const [roles, setRoles] = useState<RoleDefinition[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [search, setSearch] = useState("");
  const [roleFilter, setRoleFilter] = useState<"all" | TeamRole>("all");
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [selected, setSelected] = useState<TeamMember | null>(null);
  const [editing, setEditing] = useState<TeamMember | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const loadTeam = useCallback(async () => {
    if (!workspace) {
      setSummary(null);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const [teamSummary, roleDefinitions] = await Promise.all([
        api.get<TeamSummary>(`/workspaces/${workspace.public_id}/team/summary`),
        api.get<RoleDefinition[]>("/roles"),
      ]);
      setSummary(teamSummary);
      setRoles(roleDefinitions);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a equipe.",
      );
    } finally {
      setLoading(false);
    }
  }, [workspace]);

  useEffect(() => {
    setSearch("");
    setRoleFilter("all");
    setStatusFilter("all");
    setSelected(null);
    setEditing(null);
    setFormMode(null);
    setFormError(null);
    void loadTeam();
  }, [loadTeam, workspace?.public_id]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  const filteredMembers = useMemo(() => {
    const normalizedSearch = search.trim().toLowerCase();

    return (summary?.members ?? []).filter((member) => {
      const matchesSearch =
        !normalizedSearch ||
        member.name.toLowerCase().includes(normalizedSearch) ||
        member.email.toLowerCase().includes(normalizedSearch) ||
        member.public_id.toLowerCase().includes(normalizedSearch);
      const matchesRole = roleFilter === "all" || member.role === roleFilter;
      const matchesStatus =
        statusFilter === "all" ||
        (statusFilter === "active" && member.membership_active) ||
        (statusFilter === "inactive" && !member.membership_active);

      return matchesSearch && matchesRole && matchesStatus;
    });
  }, [roleFilter, search, statusFilter, summary?.members]);

  function openCreate() {
    if (!canCreate) return;
    setEditing(null);
    setFormError(null);
    setFormMode("create");
  }

  function openEdit(member: TeamMember) {
    if (!canEdit(member)) return;
    setSelected(null);
    setEditing(member);
    setFormError(null);
    setFormMode("edit");
  }

  async function createMember(payload: TeamMemberCreatePayload) {
    if (!workspace || !canCreate) return;
    setSaving(true);
    setFormError(null);
    try {
      await api.post(`/workspaces/${workspace.public_id}/members`, payload);
      setFormMode(null);
      setToast("Membro adicionado à equipe.");
      await loadTeam();
    } catch (requestError) {
      setFormError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível adicionar o membro.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function updateMember(payload: TeamMemberUpdatePayload) {
    if (!workspace || !editing || !canEdit(editing)) return;
    if (editing.public_id === user?.public_id &&
        (payload.active === false || (payload.role && payload.role !== editing.role)) &&
        !window.confirm("Alterar seu próprio acesso? Suas permissões serão atualizadas imediatamente.")) return;
    setSaving(true);
    setFormError(null);
    try {
      await api.patch(
        `/workspaces/${workspace.public_id}/members/${editing.public_id}`,
        payload,
      );
      setFormMode(null);
      setEditing(null);
      setToast("Acesso atualizado com sucesso.");
      if (editing.public_id === user?.public_id) await refreshSession();
      else await loadTeam();
    } catch (requestError) {
      setFormError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível atualizar o acesso.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function toggleActive(member: TeamMember) {
    if (!workspace || !canChangeStatus || !canEdit(member)) return;
    if (!window.confirm(member.membership_active
      ? "Desativar o acesso desta pessoa à empresa?" : "Reativar o acesso desta pessoa à empresa?")) return;
    setSaving(true);
    try {
      await api.patch(
        `/workspaces/${workspace.public_id}/members/${member.public_id}`,
        { active: !member.membership_active },
      );
      setSelected(null);
      setToast(member.membership_active ? "Membro desativado." : "Membro reativado.");
      if (member.public_id === user?.public_id) await refreshSession();
      else await loadTeam();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível alterar o status do membro.",
      );
    } finally {
      setSaving(false);
    }
  }

  function clearFilters() {
    setSearch("");
    setRoleFilter("all");
    setStatusFilter("all");
  }

  if (workspaceLoading) {
    return <div className="page-state">Carregando empresa...</div>;
  }

  if (!workspace) {
    return (
      <div className="page-state page-state--empty">
        <UsersRound size={28} />
        <strong>Nenhuma empresa selecionada</strong>
        <span>Selecione uma empresa para gerenciar a equipe.</span>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Equipe</p>
          <h1>Equipe comercial</h1>
          <p>Gerencie usuários, funções, permissões e desempenho por empresa.</p>
        </div>
        {canCreate && <Button onClick={openCreate} disabled={saving}>
          <UserPlus size={17} />
          Novo membro
        </Button>}
      </header>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <Button variant="secondary" onClick={() => void loadTeam()}>
            <RefreshCw size={15} />
            Tentar novamente
          </Button>
        </div>
      )}

      <section className="team-metrics">
        <article className="team-metric-card">
          <UsersRound size={19} />
          <div>
            <span>Membros ativos</span>
            <strong>{summary?.active_members ?? 0}</strong>
            <small>{summary?.total_members ?? 0} cadastrados</small>
          </div>
        </article>
        <article className="team-metric-card">
          <ShieldCheck size={19} />
          <div>
            <span>Vendedores</span>
            <strong>{summary?.sellers ?? 0}</strong>
            <small>{summary?.managers ?? 0} gestores</small>
          </div>
        </article>
        <article className="team-metric-card">
          <BriefcaseBusiness size={19} />
          <div>
            <span>Oportunidades abertas</span>
            <strong>{summary?.total_open_opportunities ?? 0}</strong>
            <small>{summary?.total_assigned_leads ?? 0} leads atribuídos</small>
          </div>
        </article>
        <article className="team-metric-card">
          <CircleDollarSign size={19} />
          <div>
            <span>Receita ganha</span>
            <strong>{currency(summary?.total_won_value ?? "0")}</strong>
            <small>Histórico da equipe</small>
          </div>
        </article>
      </section>

      <Card className="team-filter-card">
        <div className="team-toolbar">
          <div className="team-search">
            <Search size={17} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Buscar por nome, e-mail ou ID..."
            />
          </div>

          <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value as "all" | TeamRole)}>
            <option value="all">Todas as funções</option>
            <option value="admin">Administrador</option>
            <option value="manager">Gestor</option>
            <option value="seller">Vendedor</option>
            <option value="operator">Operador</option>
          </select>

          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as "all" | "active" | "inactive")}>
            <option value="all">Todos os status</option>
            <option value="active">Ativos</option>
            <option value="inactive">Inativos</option>
          </select>

          {(search || roleFilter !== "all" || statusFilter !== "all") && (
            <Button variant="ghost" onClick={clearFilters}>
              <FilterX size={16} />
              Limpar
            </Button>
          )}
        </div>
      </Card>

      <Card className="team-table-card">
        {loading ? (
          <div className="table-state">Carregando equipe...</div>
        ) : filteredMembers.length === 0 ? (
          <div className="table-state table-state--empty">
            <UsersRound size={26} />
            <strong>{summary?.members.length ? "Nenhum membro encontrado" : "Sua equipe ainda está vazia"}</strong>
            <span>
              {summary?.members.length
                ? "Altere os filtros para visualizar outros usuários."
                : "Adicione o primeiro membro para começar a distribuir leads e atividades."}
            </span>
          </div>
        ) : (
          <div className="table-wrap">
            <table className="data-table team-table">
              <thead>
                <tr>
                  <th>Usuário</th>
                  <th>Função</th>
                  <th>Status</th>
                  <th>Leads</th>
                  <th>Oportunidades</th>
                  <th>Conversão</th>
                  <th>Receita ganha</th>
                  <th>Pendências</th>
                </tr>
              </thead>
              <tbody>
                {filteredMembers.map((member) => (
                  <tr key={member.public_id} onClick={() => setSelected(member)}>
                    <td>
                      <div className="team-user-cell">
                        <span className="team-avatar">
                          {member.name
                            .split(" ")
                            .slice(0, 2)
                            .map((part) => part[0])
                            .join("")
                            .toUpperCase()}
                        </span>
                        <div>
                          <strong>{member.name}</strong>
                          <span>{member.email}</span>
                        </div>
                      </div>
                    </td>
                    <td><Badge tone={roleTones[member.role]}>{roleLabels[member.role]}</Badge></td>
                    <td><Badge tone={member.membership_active ? "success" : "neutral"}>{member.membership_active ? "Ativo" : "Inativo"}</Badge></td>
                    <td>{member.assigned_leads}</td>
                    <td>{member.open_opportunities}</td>
                    <td><strong>{member.conversion_rate.toFixed(1)}%</strong></td>
                    <td><strong>{currency(member.won_value)}</strong></td>
                    <td>
                      <span className={member.overdue_activities > 0 ? "team-pending team-pending--danger" : "team-pending"}>
                        {member.pending_activities}
                        {member.overdue_activities > 0 && ` · ${member.overdue_activities} atrasadas`}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <div className="team-security-note">
        <ShieldCheck size={18} />
        <div>
          <strong>Controle de acesso por workspace</strong>
          <span>
            Administradores gerenciam todos os perfis. Gestores cadastram e editam vendedores e operadores. A empresa deve manter um administrador ativo com senha configurada.
          </span>
        </div>
      </div>

      <TeamMemberDetailsDrawer
        workspaceId={workspace.public_id}
        member={selected}
        canEdit={selected ? canEdit(selected) : false}
        canChangeStatus={canChangeStatus && !!selected && canEdit(selected)}
        saving={saving}
        roles={roles}
        onClose={() => setSelected(null)}
        onEdit={openEdit}
        onToggleActive={(member) => void toggleActive(member)}
      />

      <TeamMemberFormModal
        open={formMode === "create" ? canCreate : formMode === "edit" && !!editing && canEdit(editing)}
        allowedRoles={allowedRoles}
        canChangeStatus={canChangeStatus}
        mode={formMode ?? "create"}
        member={editing}
        saving={saving}
        error={formError}
        onClose={() => {
          setFormMode(null);
          setEditing(null);
          setFormError(null);
        }}
        onCreate={createMember}
        onUpdate={updateMember}
      />

      {toast && <div className="toast toast--success">{toast}</div>}
    </div>
  );
}

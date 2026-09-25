import {
  CalendarClock,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  FilterX,
  Inbox,
  Mail,
  MessageCircle,
  MoreHorizontal,
  Phone,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  StickyNote,
  UsersRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ActivityDetailsDrawer } from "../components/activities/ActivityDetailsDrawer";
import { ActivityFormModal } from "../components/activities/ActivityFormModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type {
  Activity,
  ActivityCard,
  ActivityFilters,
  ActivityMetadata,
  ActivityPage,
  ActivityPayload,
  ActivityUpdatePayload,
} from "../types/activities";
import type { LeadPage, WorkspaceMember } from "../types/leads";
import type { OpportunityPage } from "../types/opportunities";

const PAGE_SIZE = 12;

const initialFilters: ActivityFilters = {
  q: "",
  activity_type: "",
  status: "",
  owner: "",
  overdue: "all",
};

const typeLabels: Record<string, string> = {
  call: "Ligação",
  whatsapp: "WhatsApp",
  email: "E-mail",
  meeting: "Reunião",
  task: "Tarefa",
  follow_up: "Follow-up",
  note: "Nota",
};

function ActivityIcon({ type }: { type: string }) {
  const props = { size: 17, strokeWidth: 1.8 };
  if (type === "call") return <Phone {...props} />;
  if (type === "whatsapp") return <MessageCircle {...props} />;
  if (type === "email") return <Mail {...props} />;
  if (type === "meeting") return <UsersRound {...props} />;
  if (type === "note") return <StickyNote {...props} />;
  return <CalendarClock {...props} />;
}

function formatDateTime(value: string | null) {
  if (!value) return "Sem data";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusTone(activity: ActivityCard) {
  if (activity.status === "completed") return "success" as const;
  if (activity.status === "cancelled") return "neutral" as const;
  if (activity.overdue) return "danger" as const;
  return "warning" as const;
}

function statusLabel(activity: ActivityCard) {
  if (activity.status === "completed") return "Concluída";
  if (activity.status === "cancelled") return "Cancelada";
  if (activity.overdue) return "Atrasada";
  return "Pendente";
}

type Stats = {
  total: number;
  pending: number;
  overdue: number;
  completed: number;
};

export function ActivitiesPage() {
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [filters, setFilters] = useState<ActivityFilters>(initialFilters);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<ActivityPage | null>(null);
  const [queue, setQueue] = useState<ActivityCard[]>([]);
  const [stats, setStats] = useState<Stats>({ total: 0, pending: 0, overdue: 0, completed: 0 });
  const [metadata, setMetadata] = useState<ActivityMetadata>({ leads: [], opportunities: [], members: [] });
  const [loading, setLoading] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [selected, setSelected] = useState<ActivityCard | null>(null);
  const [editing, setEditing] = useState<ActivityCard | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const activeMembers = useMemo(
    () => metadata.members.filter((item) => item.user_active && item.membership_active),
    [metadata.members],
  );

  const hasFilters = useMemo(
    () => Object.values(filters).some((value) => value && value !== "all"),
    [filters],
  );

  const buildParams = useCallback((targetPage: number, pageSize: number) => {
    const params = new URLSearchParams({
      page: String(targetPage),
      page_size: String(pageSize),
    });
    if (filters.q.trim()) params.set("q", filters.q.trim());
    if (filters.activity_type) params.set("activity_type", filters.activity_type);
    if (filters.status) params.set("status", filters.status);
    if (filters.owner === "unassigned") {
      params.set("unassigned", "true");
    } else if (filters.owner) {
      params.set("owner_user_public_id", filters.owner);
    }
    if (filters.overdue !== "all") params.set("overdue", filters.overdue);
    return params;
  }, [filters]);

  const loadActivities = useCallback(async () => {
    if (!workspace) {
      setData(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<ActivityPage>(
        `/workspaces/${workspace.public_id}/activities/search?${buildParams(page, PAGE_SIZE).toString()}`,
      );
      setData(result);
      if (result.total_pages > 0 && page > result.total_pages) {
        setPage(result.total_pages);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as atividades.",
      );
    } finally {
      setLoading(false);
    }
  }, [buildParams, page, workspace]);

  const loadSupportData = useCallback(async () => {
    if (!workspace) return;
    setMetadataLoading(true);
    try {
      const [members, leads, opportunities, total, pending, overdue, completed, queueResult] = await Promise.all([
        api.get<WorkspaceMember[]>(`/workspaces/${workspace.public_id}/members`),
        api.get<LeadPage>(`/workspaces/${workspace.public_id}/leads/search?page=1&page_size=100&active=true`),
        api.get<OpportunityPage>(`/workspaces/${workspace.public_id}/opportunities/search?page=1&page_size=100&status=open`),
        api.get<ActivityPage>(`/workspaces/${workspace.public_id}/activities/search?page=1&page_size=1`),
        api.get<ActivityPage>(`/workspaces/${workspace.public_id}/activities/search?page=1&page_size=1&status=pending`),
        api.get<ActivityPage>(`/workspaces/${workspace.public_id}/activities/search?page=1&page_size=1&overdue=true`),
        api.get<ActivityPage>(`/workspaces/${workspace.public_id}/activities/search?page=1&page_size=1&status=completed`),
        api.get<ActivityPage>(`/workspaces/${workspace.public_id}/activities/search?page=1&page_size=6&status=pending`),
      ]);
      setMetadata({ members, leads: leads.items, opportunities: opportunities.items });
      setStats({ total: total.total, pending: pending.total, overdue: overdue.total, completed: completed.total });
      setQueue(queueResult.items);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar os dados de apoio das atividades.",
      );
    } finally {
      setMetadataLoading(false);
    }
  }, [workspace]);

  useEffect(() => {
    setFilters(initialFilters);
    setPage(1);
    setSelected(null);
    void loadSupportData();
  }, [loadSupportData, workspace?.public_id]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadActivities(), filters.q ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [filters.q, loadActivities]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function updateFilter<K extends keyof ActivityFilters>(key: K, value: ActivityFilters[K]) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function applyQuickFilter(next: Partial<ActivityFilters>) {
    setFilters({ ...initialFilters, ...next });
    setPage(1);
  }

  function openCreate() {
    setEditing(null);
    setFormError(null);
    setFormMode("create");
  }

  function openEdit(activity: ActivityCard) {
    setSelected(null);
    setEditing(activity);
    setFormError(null);
    setFormMode("edit");
  }

  async function refreshAll() {
    await Promise.all([loadActivities(), loadSupportData()]);
  }

  async function handleSubmit(payload: ActivityPayload | ActivityUpdatePayload) {
    if (!workspace || !formMode) return;
    setSaving(true);
    setFormError(null);
    try {
      if (formMode === "edit" && editing) {
        await api.patch<Activity>(
          `/workspaces/${workspace.public_id}/activities/${editing.public_id}`,
          payload,
        );
        setToast("Atividade atualizada com sucesso.");
      } else {
        await api.post<Activity>(
          `/workspaces/${workspace.public_id}/activities`,
          payload,
        );
        setToast("Atividade criada com sucesso.");
      }
      setFormMode(null);
      setEditing(null);
      await refreshAll();
    } catch (requestError) {
      setFormError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível salvar a atividade.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function changeState(activity: ActivityCard, action: "complete" | "cancel") {
    if (!workspace) return;
    setSaving(true);
    try {
      await api.post<Activity>(
        `/workspaces/${workspace.public_id}/activities/${activity.public_id}/${action}`,
      );
      setSelected(null);
      setToast(action === "complete" ? "Atividade concluída." : "Atividade cancelada.");
      await refreshAll();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível atualizar a atividade.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (workspaceLoading) {
    return <div className="page-state">Carregando empresa...</div>;
  }

  if (!workspace) {
    return (
      <Card>
        <div className="empty-state empty-state--large">
          <Inbox size={28} />
          <strong>Nenhuma empresa disponível</strong>
          <span>Crie ou ative um workspace para começar a organizar follow-ups.</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="page-stack">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Rotina comercial</p>
          <h1>Atividades e follow-ups</h1>
          <p>Organize contatos, tarefas, reuniões e próximos passos da equipe.</p>
        </div>
        <Button onClick={openCreate}>
          <Plus size={17} />
          Nova atividade
        </Button>
      </header>

      <section className="activity-metrics">
        <button type="button" className="activity-metric" onClick={() => applyQuickFilter({})}>
          <CalendarClock size={18} />
          <div><span>Total</span><strong>{stats.total}</strong></div>
        </button>
        <button type="button" className="activity-metric" onClick={() => applyQuickFilter({ status: "pending" })}>
          <Clock3 size={18} />
          <div><span>Pendentes</span><strong>{stats.pending}</strong></div>
        </button>
        <button type="button" className="activity-metric activity-metric--danger" onClick={() => applyQuickFilter({ overdue: "true" })}>
          <CircleAlert size={18} />
          <div><span>Atrasadas</span><strong>{stats.overdue}</strong></div>
        </button>
        <button type="button" className="activity-metric activity-metric--success" onClick={() => applyQuickFilter({ status: "completed" })}>
          <CheckCircle2 size={18} />
          <div><span>Concluídas</span><strong>{stats.completed}</strong></div>
        </button>
      </section>

      <Card className="activity-filter-card">
        <div className="lead-toolbar">
          <div className="lead-search">
            <Search size={17} />
            <input
              type="search"
              placeholder="Buscar atividade, lead, oportunidade ou responsável..."
              value={filters.q}
              onChange={(event) => updateFilter("q", event.target.value)}
            />
          </div>
          <div className="lead-toolbar__summary">
            <strong>{data?.total ?? 0}</strong>
            <span>{data?.total === 1 ? "atividade encontrada" : "atividades encontradas"}</span>
          </div>
          <Button variant="ghost" onClick={() => void refreshAll()} disabled={loading || metadataLoading}>
            <RefreshCw size={16} className={loading || metadataLoading ? "spin" : ""} />
          </Button>
        </div>

        <div className="lead-filters activity-filters">
          <div className="lead-filters__label">
            <SlidersHorizontal size={15} />
            Filtros
          </div>
          <select value={filters.activity_type} onChange={(event) => updateFilter("activity_type", event.target.value)}>
            <option value="">Todos os tipos</option>
            {Object.entries(typeLabels).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
          <select value={filters.status} onChange={(event) => updateFilter("status", event.target.value)}>
            <option value="">Todos os status</option>
            <option value="pending">Pendentes</option>
            <option value="completed">Concluídas</option>
            <option value="cancelled">Canceladas</option>
          </select>
          <select value={filters.owner} onChange={(event) => updateFilter("owner", event.target.value)}>
            <option value="">Todos os responsáveis</option>
            <option value="unassigned">Sem responsável</option>
            {activeMembers.map((member) => (
              <option key={member.public_id} value={member.public_id}>{member.name}</option>
            ))}
          </select>
          <select value={filters.overdue} onChange={(event) => updateFilter("overdue", event.target.value as ActivityFilters["overdue"])}>
            <option value="all">Prazo: todos</option>
            <option value="true">Somente atrasadas</option>
            <option value="false">Sem atraso</option>
          </select>
          {hasFilters && (
            <Button variant="ghost" className="lead-clear-filters" onClick={() => {
              setFilters(initialFilters);
              setPage(1);
            }}>
              <FilterX size={15} />
              Limpar
            </Button>
          )}
        </div>
      </Card>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <Button variant="ghost" onClick={() => void refreshAll()}>Tentar novamente</Button>
        </div>
      )}

      <section className="activity-layout">
        <Card className="activity-table-card">
          {loading && !data ? (
            <div className="table-loading"><RefreshCw size={20} className="spin" /><span>Carregando atividades...</span></div>
          ) : data && data.items.length > 0 ? (
            <>
              <div className="table-wrap">
                <table className="data-table activity-table">
                  <thead>
                    <tr>
                      <th>Atividade</th>
                      <th>Relacionamento</th>
                      <th>Responsável</th>
                      <th>Prazo</th>
                      <th>Status</th>
                      <th aria-label="Ações" />
                    </tr>
                  </thead>
                  <tbody>
                    {data.items.map((activity) => (
                      <tr key={activity.public_id} onClick={() => setSelected(activity)}>
                        <td>
                          <div className="activity-primary-cell">
                            <span className="activity-type-icon"><ActivityIcon type={activity.activity_type} /></span>
                            <div>
                              <strong>{activity.title}</strong>
                              <span>{typeLabels[activity.activity_type] ?? activity.activity_type}</span>
                            </div>
                          </div>
                        </td>
                        <td>
                          <div className="stacked-cell">
                            <strong>{activity.lead_name ?? "Atividade interna"}</strong>
                            <span>{activity.opportunity_title ?? "Sem oportunidade"}</span>
                          </div>
                        </td>
                        <td>{activity.owner_name ?? "Sem responsável"}</td>
                        <td className={activity.overdue ? "activity-date--overdue" : ""}>{formatDateTime(activity.due_at)}</td>
                        <td><Badge tone={statusTone(activity)}>{statusLabel(activity)}</Badge></td>
                        <td>
                          <button className="table-action-button" type="button" aria-label={`Abrir ${activity.title}`} onClick={(event) => {
                            event.stopPropagation();
                            setSelected(activity);
                          }}>
                            <MoreHorizontal size={17} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <footer className="table-pagination">
                <span>Página <strong>{data.page}</strong> de <strong>{Math.max(data.total_pages, 1)}</strong></span>
                <div>
                  <Button variant="secondary" disabled={data.page <= 1 || loading} onClick={() => setPage((current) => Math.max(1, current - 1))}>
                    <ChevronLeft size={15} />Anterior
                  </Button>
                  <Button variant="secondary" disabled={data.page >= data.total_pages || loading} onClick={() => setPage((current) => current + 1)}>
                    Próxima<ChevronRight size={15} />
                  </Button>
                </div>
              </footer>
            </>
          ) : (
            <div className="empty-state empty-state--large">
              <Inbox size={28} />
              <strong>Nenhuma atividade encontrada</strong>
              <span>{hasFilters ? "Ajuste os filtros para visualizar outros compromissos." : "Registre o primeiro follow-up ou compromisso comercial."}</span>
              {!hasFilters && <Button onClick={openCreate}>Nova atividade</Button>}
            </div>
          )}
        </Card>

        <Card title="Próximos follow-ups" description="Fila operacional priorizada por prazo" className="activity-queue-card">
          {queue.length > 0 ? (
            <div className="activity-queue">
              {queue.map((activity) => (
                <button key={activity.public_id} type="button" className="activity-queue__item" onClick={() => setSelected(activity)}>
                  <span className="activity-type-icon"><ActivityIcon type={activity.activity_type} /></span>
                  <div>
                    <strong>{activity.title}</strong>
                    <span>{activity.lead_name ?? "Atividade interna"}</span>
                    <small className={activity.overdue ? "activity-date--overdue" : ""}>{formatDateTime(activity.due_at)}</small>
                  </div>
                  {activity.overdue && <CircleAlert size={16} />}
                </button>
              ))}
            </div>
          ) : (
            <div className="activity-queue-empty">
              <CheckCircle2 size={24} />
              <strong>Fila em dia</strong>
              <span>Nenhum compromisso pendente.</span>
            </div>
          )}
        </Card>
      </section>

      <ActivityFormModal
        open={formMode !== null}
        mode={formMode ?? "create"}
        activity={editing}
        metadata={metadata}
        saving={saving}
        error={formError}
        onClose={() => {
          if (!saving) {
            setFormMode(null);
            setEditing(null);
            setFormError(null);
          }
        }}
        onSubmit={handleSubmit}
      />

      <ActivityDetailsDrawer
        activity={selected}
        busy={saving}
        onClose={() => setSelected(null)}
        onEdit={openEdit}
        onComplete={(activity) => void changeState(activity, "complete")}
        onCancel={(activity) => void changeState(activity, "cancel")}
      />

      {toast && <div className="toast toast--success">{toast}</div>}
    </div>
  );
}

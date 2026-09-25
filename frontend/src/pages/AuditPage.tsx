import {
  Bot,
  ChevronLeft,
  ChevronRight,
  FilterX,
  Fingerprint,
  Inbox,
  Network,
  RefreshCw,
  Search,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { AuditDetailsDrawer } from "../components/audit/AuditDetailsDrawer";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useWorkspace } from "../contexts/WorkspaceContext";
import {
  actorLabel,
  actorTone,
  formatAuditDate,
  labelizeAuditAction,
  labelizeEntity,
  roleLabels,
} from "../lib/audit";
import { api } from "../lib/api";
import type { AuditEvent, AuditEventPage } from "../types/audit";

const EMPTY_DATA: AuditEventPage = {
  items: [],
  total: 0,
  page: 1,
  page_size: 25,
  total_pages: 0,
  stats: {
    total_events: 0,
    user_events: 0,
    system_events: 0,
    atlas_events: 0,
    integration_events: 0,
  },
  available_actor_types: [],
  available_entity_types: [],
  available_actions: [],
  available_actors: [],
};

function periodStart(period: string) {
  if (period === "all") return null;

  const now = new Date();
  const days = Number(period);
  now.setDate(now.getDate() - days);
  return now.toISOString();
}

export function AuditPage() {
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [data, setData] = useState<AuditEventPage>(EMPTY_DATA);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<AuditEvent | null>(null);
  const [search, setSearch] = useState("");
  const [actorType, setActorType] = useState("all");
  const [actorUser, setActorUser] = useState("all");
  const [entityType, setEntityType] = useState("all");
  const [action, setAction] = useState("all");
  const [period, setPeriod] = useState("30");
  const [page, setPage] = useState(1);

  const loadAudit = useCallback(async () => {
    if (!workspace) {
      setData(EMPTY_DATA);
      return;
    }

    const params = new URLSearchParams();
    if (search.trim()) params.set("q", search.trim());
    if (actorType !== "all") params.set("actor_type", actorType);
    if (actorUser !== "all") params.set("actor_user_public_id", actorUser);
    if (entityType !== "all") params.set("entity_type", entityType);
    if (action !== "all") params.set("action", action);

    const createdFrom = periodStart(period);
    if (createdFrom) params.set("created_from", createdFrom);
    params.set("page", String(page));
    params.set("page_size", "25");

    setLoading(true);
    setError(null);
    try {
      const response = await api.get<AuditEventPage>(
        `/workspaces/${workspace.public_id}/audit/search?${params.toString()}`,
      );
      setData(response);

      if (response.total_pages > 0 && page > response.total_pages) {
        setPage(response.total_pages);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a auditoria.",
      );
    } finally {
      setLoading(false);
    }
  }, [action, actorType, actorUser, entityType, page, period, search, workspace]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadAudit();
    }, search ? 260 : 0);

    return () => window.clearTimeout(timer);
  }, [loadAudit, search]);

  useEffect(() => {
    setPage(1);
    setSelected(null);
  }, [workspace?.public_id]);

  const hasFilters = useMemo(
    () =>
      Boolean(search.trim()) ||
      actorType !== "all" ||
      actorUser !== "all" ||
      entityType !== "all" ||
      action !== "all" ||
      period !== "30",
    [action, actorType, actorUser, entityType, period, search],
  );

  function resetFilters() {
    setSearch("");
    setActorType("all");
    setActorUser("all");
    setEntityType("all");
    setAction("all");
    setPeriod("30");
    setPage(1);
  }

  function changeFilter(setter: (value: string) => void, value: string) {
    setter(value);
    setPage(1);
  }

  if (workspaceLoading) {
    return <div className="page-state">Carregando empresa...</div>;
  }

  if (!workspace) {
    return (
      <div className="page-state page-state--empty">
        <ShieldCheck size={28} />
        <strong>Nenhuma empresa selecionada</strong>
        <span>Selecione uma empresa para consultar a trilha de auditoria.</span>
      </div>
    );
  }

  return (
    <div className="page-stack">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Governança</p>
          <h1>Auditoria</h1>
          <p>
            Rastreie alterações, responsáveis, integrações e ações executadas no CRM.
          </p>
        </div>
        <Button variant="secondary" onClick={() => void loadAudit()} disabled={loading}>
          <RefreshCw className={loading ? "spin" : ""} size={16} />
          Atualizar
        </Button>
      </header>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <Button variant="secondary" onClick={() => void loadAudit()}>
            Tentar novamente
          </Button>
        </div>
      )}

      <section className="audit-metrics">
        <article className="audit-metric-card">
          <Fingerprint size={19} />
          <div>
            <span>Eventos</span>
            <strong>{data.stats.total_events}</strong>
            <small>no filtro atual</small>
          </div>
        </article>
        <article className="audit-metric-card">
          <UserRound size={19} />
          <div>
            <span>Usuários</span>
            <strong>{data.stats.user_events}</strong>
            <small>ações atribuídas a pessoas</small>
          </div>
        </article>
        <article className="audit-metric-card">
          <Bot size={19} />
          <div>
            <span>Atlas</span>
            <strong>{data.stats.atlas_events}</strong>
            <small>ações do copiloto</small>
          </div>
        </article>
        <article className="audit-metric-card">
          <Network size={19} />
          <div>
            <span>Integrações</span>
            <strong>{data.stats.integration_events}</strong>
            <small>{data.stats.system_events} eventos de sistema</small>
          </div>
        </article>
      </section>

      <Card className="audit-filter-card">
        <div className="audit-toolbar">
          <div className="audit-search">
            <Search size={17} />
            <input
              type="search"
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              placeholder="Buscar evento, ação, entidade, usuário ou ID..."
              aria-label="Buscar na auditoria"
            />
          </div>

          <label>
            <span>Período</span>
            <select value={period} onChange={(event) => changeFilter(setPeriod, event.target.value)}>
              <option value="7">Últimos 7 dias</option>
              <option value="30">Últimos 30 dias</option>
              <option value="90">Últimos 90 dias</option>
              <option value="180">Últimos 180 dias</option>
              <option value="365">Último ano</option>
              <option value="all">Todo o histórico</option>
            </select>
          </label>

          <label>
            <span>Origem</span>
            <select value={actorType} onChange={(event) => changeFilter(setActorType, event.target.value)}>
              <option value="all">Todas</option>
              {data.available_actor_types.map((item) => (
                <option key={item} value={item}>{actorLabel(item)}</option>
              ))}
            </select>
          </label>

          <label>
            <span>Usuário</span>
            <select value={actorUser} onChange={(event) => changeFilter(setActorUser, event.target.value)}>
              <option value="all">Todos</option>
              {data.available_actors.map((item) => (
                <option key={item.public_id} value={item.public_id}>
                  {item.name} · {roleLabels[item.role] ?? item.role}
                </option>
              ))}
            </select>
          </label>

          <label>
            <span>Entidade</span>
            <select value={entityType} onChange={(event) => changeFilter(setEntityType, event.target.value)}>
              <option value="all">Todas</option>
              {data.available_entity_types.map((item) => (
                <option key={item} value={item}>{labelizeEntity(item)}</option>
              ))}
            </select>
          </label>

          <label>
            <span>Ação</span>
            <select value={action} onChange={(event) => changeFilter(setAction, event.target.value)}>
              <option value="all">Todas</option>
              {data.available_actions.map((item) => (
                <option key={item} value={item}>{labelizeAuditAction(item)}</option>
              ))}
            </select>
          </label>

          <Button variant="secondary" onClick={resetFilters} disabled={!hasFilters}>
            <FilterX size={15} />
            Limpar
          </Button>
        </div>
      </Card>

      <Card
        title="Trilha de auditoria"
        description={`${data.total} evento(s) encontrado(s)`}
      >
        {loading && data.items.length === 0 ? (
          <div className="table-loading">
            <RefreshCw className="spin" size={17} />
            Carregando histórico...
          </div>
        ) : data.items.length > 0 ? (
          <>
            <div className="table-wrap">
              <table className="data-table audit-table">
                <thead>
                  <tr>
                    <th>Data</th>
                    <th>Ação</th>
                    <th>Entidade</th>
                    <th>Responsável</th>
                    <th>Origem</th>
                    <th>Evento</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((event) => (
                    <tr key={event.public_id} onClick={() => setSelected(event)}>
                      <td>
                        <div className="stacked-cell audit-date-cell">
                          <strong>{formatAuditDate(event.created_at)}</strong>
                          <span>{event.public_id}</span>
                        </div>
                      </td>
                      <td>
                        <div className="stacked-cell audit-action-cell">
                          <strong>{labelizeAuditAction(event.action)}</strong>
                          <span>{event.action}</span>
                        </div>
                      </td>
                      <td>
                        <div className="stacked-cell">
                          <strong>{labelizeEntity(event.entity_type)}</strong>
                          <span>{event.entity_public_id}</span>
                        </div>
                      </td>
                      <td>
                        <div className="stacked-cell">
                          <strong>{event.actor_user_name ?? actorLabel(event.actor_type)}</strong>
                          <span>
                            {event.actor_role
                              ? roleLabels[event.actor_role] ?? event.actor_role
                              : event.actor_user_public_id ?? "Execução automática"}
                          </span>
                        </div>
                      </td>
                      <td>
                        <Badge tone={actorTone(event.actor_type)}>
                          {actorLabel(event.actor_type)}
                        </Badge>
                      </td>
                      <td>
                        <button
                          className="table-action-button"
                          type="button"
                          aria-label={`Abrir evento ${event.public_id}`}
                          onClick={(clickEvent) => {
                            clickEvent.stopPropagation();
                            setSelected(event);
                          }}
                        >
                          <ChevronRight size={17} />
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <footer className="table-pagination">
              <span>
                Página <strong>{data.page}</strong> de{" "}
                <strong>{Math.max(data.total_pages, 1)}</strong>
              </span>
              <div>
                <Button
                  variant="secondary"
                  disabled={data.page <= 1 || loading}
                  onClick={() => setPage((current) => Math.max(1, current - 1))}
                >
                  <ChevronLeft size={15} />
                  Anterior
                </Button>
                <Button
                  variant="secondary"
                  disabled={data.page >= data.total_pages || loading}
                  onClick={() => setPage((current) => current + 1)}
                >
                  Próxima
                  <ChevronRight size={15} />
                </Button>
              </div>
            </footer>
          </>
        ) : (
          <div className="empty-state empty-state--large">
            <Inbox size={28} />
            <strong>Nenhum evento encontrado</strong>
            <span>
              {hasFilters
                ? "Ajuste os filtros para consultar outra parte do histórico."
                : "Os eventos auditáveis aparecerão aqui conforme o CRM for utilizado."}
            </span>
            {hasFilters && (
              <Button variant="secondary" onClick={resetFilters}>
                Limpar filtros
              </Button>
            )}
          </div>
        )}
      </Card>

      <div className="audit-footnote">
        <ShieldCheck size={14} />
        <span>
          A auditoria preserva o antes/depois e a origem técnica do evento. Identidade humana completa depende da autenticação real do CRM.
        </span>
      </div>

      <AuditDetailsDrawer event={selected} onClose={() => setSelected(null)} />
    </div>
  );
}

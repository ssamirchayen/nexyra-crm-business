import {
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Inbox,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { OpportunityCloseModal } from "../components/opportunities/OpportunityCloseModal";
import { OpportunityDetailsDrawer } from "../components/opportunities/OpportunityDetailsDrawer";
import { OpportunityFormModal } from "../components/opportunities/OpportunityFormModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type {
  Lead,
  WorkspaceMember,
  WorkspaceSegmentConfig,
} from "../types/leads";
import type {
  OpportunityCard,
  OpportunityHistory,
  OpportunityPage,
  OpportunityPayload,
  OpportunityUpdatePayload,
} from "../types/opportunities";

const PAGE_SIZE = 12;

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatCurrency(value: string, currency = "BRL") {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency,
  }).format(Number(value || 0));
}

function formatDate(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(new Date(`${value}T12:00:00`));
}

function statusTone(status: string) {
  if (status === "won") return "success" as const;
  if (status === "lost") return "danger" as const;
  return "info" as const;
}

function statusLabel(status: string) {
  if (status === "won") return "Ganha";
  if (status === "lost") return "Perdida";
  return "Aberta";
}

export function OpportunitiesPage() {
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [data, setData] = useState<OpportunityPage | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [segmentConfig, setSegmentConfig] =
    useState<WorkspaceSegmentConfig | null>(null);

  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("");
  const [stage, setStage] = useState("");
  const [owner, setOwner] = useState("");
  const [page, setPage] = useState(1);

  const [loading, setLoading] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [selected, setSelected] = useState<OpportunityCard | null>(null);
  const [history, setHistory] = useState<OpportunityHistory[]>([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<OpportunityCard | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [closeMode, setCloseMode] = useState<"won" | "lost" | null>(null);
  const [closingOpportunity, setClosingOpportunity] =
    useState<OpportunityCard | null>(null);
  const [closeError, setCloseError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const activeMembers = useMemo(
    () =>
      members.filter(
        (member) => member.membership_active && member.user_active,
      ),
    [members],
  );

  const loadMetadata = useCallback(async () => {
    if (!workspace) return;

    setMetadataLoading(true);
    try {
      const [memberItems, config, leadPage] = await Promise.all([
        api.get<WorkspaceMember[]>(
          `/workspaces/${workspace.public_id}/members`,
        ),
        api.get<WorkspaceSegmentConfig>(
          `/workspaces/${workspace.public_id}/segment-config`,
        ),
        api.get<Lead[]>(
          `/workspaces/${workspace.public_id}/leads`,
        ),
      ]);
      setMembers(memberItems);
      setSegmentConfig(config);
      setLeads(leadPage.filter((lead) => lead.active));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar os dados auxiliares.",
      );
    } finally {
      setMetadataLoading(false);
    }
  }, [workspace]);

  const loadOpportunities = useCallback(async () => {
    if (!workspace) return;

    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });
    if (query.trim()) params.set("q", query.trim());
    if (status) params.set("opportunity_status", status);
    if (stage) params.set("stage", stage);
    if (owner === "unassigned") {
      params.set("unassigned", "true");
    } else if (owner) {
      params.set("owner_user_public_id", owner);
    }

    try {
      const result = await api.get<OpportunityPage>(
        `/workspaces/${workspace.public_id}/opportunities/search?${params.toString()}`,
      );
      setData(result);

    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as oportunidades.",
      );
    } finally {
      setLoading(false);
    }
  }, [owner, page, query, stage, status, workspace]);

  useEffect(() => {
    setData(null);
    setPage(1);
    setQuery("");
    setStatus("");
    setStage("");
    setOwner("");
    setSelected(null);
    if (workspace) void loadMetadata();
  }, [loadMetadata, workspace]);

  useEffect(() => {
    if (!workspace) return;
    const timer = window.setTimeout(() => {
      void loadOpportunities();
    }, 220);
    return () => window.clearTimeout(timer);
  }, [loadOpportunities, workspace]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function openDetails(opportunity: OpportunityCard) {
    if (!workspace) return;
    setSelected(opportunity);
    setHistory([]);
    setHistoryLoading(true);
    try {
      setHistory(
        await api.get<OpportunityHistory[]>(
          `/workspaces/${workspace.public_id}/opportunities/${opportunity.public_id}/history`,
        ),
      );
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  function openCreate() {
    setEditing(null);
    setFormError(null);
    setFormMode("create");
  }

  function openEdit(opportunity: OpportunityCard) {
    setEditing(opportunity);
    setFormError(null);
    setFormMode("edit");
  }

  async function handleFormSubmit(
    payload: OpportunityPayload | OpportunityUpdatePayload,
  ) {
    if (!workspace || !formMode) return;

    setSaving(true);
    setFormError(null);

    try {
      if (formMode === "edit" && editing) {
        await api.patch(
          `/workspaces/${workspace.public_id}/opportunities/${editing.public_id}`,
          payload,
        );
        setToast("Oportunidade atualizada.");
      } else {
        await api.post(
          `/workspaces/${workspace.public_id}/opportunities`,
          payload,
        );
        setToast("Oportunidade criada.");
      }

      setFormMode(null);
      setEditing(null);
      setSelected(null);
      await loadOpportunities();
    } catch (requestError) {
      setFormError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível salvar a oportunidade.",
      );
    } finally {
      setSaving(false);
    }
  }

  function openClose(
    mode: "won" | "lost",
    opportunity: OpportunityCard,
  ) {
    setClosingOpportunity(opportunity);
    setCloseMode(mode);
    setCloseError(null);
  }

  async function handleClose(reason: string | null) {
    if (!workspace || !closeMode || !closingOpportunity) return;

    setSaving(true);
    setCloseError(null);
    try {
      if (closeMode === "won") {
        await api.post(
          `/workspaces/${workspace.public_id}/opportunities/${closingOpportunity.public_id}/won`,
          {},
        );
        setToast("Oportunidade marcada como ganha.");
      } else {
        await api.post(
          `/workspaces/${workspace.public_id}/opportunities/${closingOpportunity.public_id}/lost`,
          { reason },
        );
        setToast("Oportunidade marcada como perdida.");
      }

      setCloseMode(null);
      setClosingOpportunity(null);
      setSelected(null);
      await loadOpportunities();
    } catch (requestError) {
      setCloseError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível encerrar a oportunidade.",
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
          <span>Selecione uma empresa para visualizar oportunidades.</span>
        </div>
      </Card>
    );
  }

  const visibleValue =
    data?.items.reduce(
      (total, item) => total + Number(item.value_amount),
      0,
    ) ?? 0;

  return (
    <div className="page-stack">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Comercial</p>
          <h1>Oportunidades</h1>
          <p>
            Acompanhe negociações abertas, ganhas e perdidas em uma única visão.
          </p>
        </div>
        <div className="page-header__actions">
          <Button
            variant="secondary"
            onClick={() => void loadOpportunities()}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Atualizar
          </Button>
          <Button onClick={openCreate}>
            <Plus size={17} />
            Nova oportunidade
          </Button>
        </div>
      </header>

      <section className="opportunity-list-summary">
        <div>
          <span>Resultados</span>
          <strong>{data?.total ?? 0}</strong>
        </div>
        <div>
          <span>Valor nesta página</span>
          <strong>{formatCurrency(String(visibleValue))}</strong>
        </div>
      </section>

      <Card>
        <div className="opportunity-toolbar">
          <div className="pipeline-search">
            <Search size={17} />
            <input
              type="search"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
              placeholder="Buscar por lead, oportunidade, telefone ou interesse..."
            />
          </div>

          <div className="opportunity-filters">
            <SlidersHorizontal size={15} />
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos os status</option>
              <option value="open">Abertas</option>
              <option value="won">Ganhas</option>
              <option value="lost">Perdidas</option>
            </select>

            <select
              value={stage}
              onChange={(event) => {
                setStage(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todas as etapas</option>
              {segmentConfig?.pipeline.map((item) => (
                <option key={item} value={item}>
                  {labelize(item)}
                </option>
              ))}
            </select>

            <select
              value={owner}
              onChange={(event) => {
                setOwner(event.target.value);
                setPage(1);
              }}
            >
              <option value="">Todos os responsáveis</option>
              <option value="unassigned">Sem responsável</option>
              {activeMembers.map((member) => (
                <option key={member.public_id} value={member.public_id}>
                  {member.name}
                </option>
              ))}
            </select>
          </div>
        </div>
      </Card>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <Button variant="ghost" onClick={() => void loadOpportunities()}>
            Tentar novamente
          </Button>
        </div>
      )}

      <Card className="opportunity-table-card">
        {loading && !data ? (
          <div className="table-loading">
            <RefreshCw size={20} className="spin" />
            <span>Carregando oportunidades...</span>
          </div>
        ) : data && data.items.length > 0 ? (
          <>
            <div className="table-wrap">
              <table className="data-table opportunity-table">
                <thead>
                  <tr>
                    <th>Oportunidade</th>
                    <th>Lead</th>
                    <th>Valor</th>
                    <th>Etapa</th>
                    <th>Responsável</th>
                    <th>Previsão</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((opportunity) => (
                    <tr
                      key={opportunity.public_id}
                      onClick={() => void openDetails(opportunity)}
                    >
                      <td>
                        <div className="opportunity-title-cell">
                          <span className="opportunity-money-icon">
                            <CircleDollarSign size={15} />
                          </span>
                          <div>
                            <strong>{opportunity.title}</strong>
                            <span>{opportunity.public_id}</span>
                          </div>
                        </div>
                      </td>
                      <td>
                        <div className="stacked-cell">
                          <strong>{opportunity.lead_name}</strong>
                          <span>{opportunity.lead_interest ?? "—"}</span>
                        </div>
                      </td>
                      <td>
                        <strong>
                          {formatCurrency(
                            opportunity.value_amount,
                            opportunity.currency,
                          )}
                        </strong>
                      </td>
                      <td>{labelize(opportunity.stage)}</td>
                      <td>{opportunity.owner_name ?? "Sem responsável"}</td>
                      <td>{formatDate(opportunity.expected_close_date)}</td>
                      <td>
                        <Badge tone={statusTone(opportunity.status)}>
                          {statusLabel(opportunity.status)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <footer className="lead-pagination">
              <div>
                Página <strong>{data.page}</strong> de{" "}
                <strong>{Math.max(data.total_pages, 1)}</strong>
              </div>
              <div className="lead-pagination__buttons">
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
                  disabled={
                    data.total_pages === 0 ||
                    data.page >= data.total_pages ||
                    loading
                  }
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
            <CircleDollarSign size={28} />
            <strong>Nenhuma oportunidade encontrada</strong>
            <span>
              Crie uma oportunidade a partir de um lead para iniciar o pipeline.
            </span>
            <Button onClick={openCreate}>
              <Plus size={16} />
              Nova oportunidade
            </Button>
          </div>
        )}
      </Card>

      <OpportunityFormModal
        open={formMode !== null}
        mode={formMode ?? "create"}
        opportunity={editing}
        leads={leads}
        members={activeMembers}
        segmentConfig={segmentConfig}
        saving={saving}
        error={formError}
        onClose={() => {
          setFormMode(null);
          setEditing(null);
          setFormError(null);
        }}
        onSubmit={handleFormSubmit}
      />

      <OpportunityDetailsDrawer
        opportunity={selected}
        history={history}
        historyLoading={historyLoading}
        onClose={() => {
          setSelected(null);
          setHistory([]);
        }}
        onEdit={openEdit}
        onWon={(opportunity) => openClose("won", opportunity)}
        onLost={(opportunity) => openClose("lost", opportunity)}
      />

      <OpportunityCloseModal
        open={closeMode !== null}
        mode={closeMode ?? "won"}
        opportunity={closingOpportunity}
        saving={saving}
        error={closeError}
        onClose={() => {
          setCloseMode(null);
          setClosingOpportunity(null);
          setCloseError(null);
        }}
        onConfirm={handleClose}
      />

      {metadataLoading && (
        <div className="metadata-indicator">Atualizando dados auxiliares...</div>
      )}
      {toast && <div className="toast toast--success">{toast}</div>}
    </div>
  );
}

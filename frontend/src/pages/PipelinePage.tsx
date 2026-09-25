import {
  CircleDollarSign,
  GripVertical,
  Inbox,
  Plus,
  RefreshCw,
  Search,
  SlidersHorizontal,
  UserRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { OpportunityCloseModal } from "../components/opportunities/OpportunityCloseModal";
import { OpportunityDetailsDrawer } from "../components/opportunities/OpportunityDetailsDrawer";
import { OpportunityFormModal } from "../components/opportunities/OpportunityFormModal";
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
  OpportunityPayload,
  OpportunityUpdatePayload,
  PipelineBoard,
} from "../types/opportunities";

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatCurrency(value: string, currency = "BRL") {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(value || 0));
}

function formatDate(value: string | null) {
  if (!value) return null;
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
  }).format(new Date(`${value}T12:00:00`));
}

export function PipelinePage() {
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [board, setBoard] = useState<PipelineBoard | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [segmentConfig, setSegmentConfig] =
    useState<WorkspaceSegmentConfig | null>(null);

  const [query, setQuery] = useState("");
  const [owner, setOwner] = useState("");
  const [loading, setLoading] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [movingId, setMovingId] = useState<string | null>(null);

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
          : "Não foi possível carregar os dados do pipeline.",
      );
    } finally {
      setMetadataLoading(false);
    }
  }, [workspace]);

  const loadBoard = useCallback(async () => {
    if (!workspace) return;

    setLoading(true);
    setError(null);

    const params = new URLSearchParams();
    if (query.trim()) params.set("q", query.trim());
    if (owner === "unassigned") {
      params.set("unassigned", "true");
    } else if (owner) {
      params.set("owner_user_public_id", owner);
    }

    try {
      const suffix = params.toString() ? `?${params.toString()}` : "";
      const result = await api.get<PipelineBoard>(
        `/workspaces/${workspace.public_id}/pipeline/board${suffix}`,
      );
      setBoard(result);

    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar o pipeline.",
      );
    } finally {
      setLoading(false);
    }
  }, [owner, query, workspace]);

  useEffect(() => {
    setBoard(null);
    setSelected(null);
    setHistory([]);
    setQuery("");
    setOwner("");
    if (workspace) {
      void loadMetadata();
    }
  }, [loadMetadata, workspace]);

  useEffect(() => {
    if (!workspace) return;
    const timer = window.setTimeout(() => {
      void loadBoard();
    }, 220);
    return () => window.clearTimeout(timer);
  }, [loadBoard, workspace]);

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
      const items = await api.get<OpportunityHistory[]>(
        `/workspaces/${workspace.public_id}/opportunities/${opportunity.public_id}/history`,
      );
      setHistory(items);
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoading(false);
    }
  }

  async function handleMove(opportunityId: string, toStage: string) {
    if (!workspace) return;

    const current = board?.stages
      .flatMap((stage) => stage.opportunities)
      .find((item) => item.public_id === opportunityId);

    if (!current || current.stage === toStage || current.status !== "open") {
      setDraggingId(null);
      return;
    }

    setMovingId(opportunityId);
    setError(null);

    try {
      await api.post(
        `/workspaces/${workspace.public_id}/opportunities/${opportunityId}/move`,
        { to_stage: toStage },
      );
      setToast(
        `${current.lead_name} movido para ${labelize(toStage)}.`,
      );
      await loadBoard();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível mover a oportunidade.",
      );
    } finally {
      setMovingId(null);
      setDraggingId(null);
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
        setToast("Oportunidade criada e adicionada ao pipeline.");
      }

      setFormMode(null);
      setEditing(null);
      setSelected(null);
      await loadBoard();
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
      await loadBoard();
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
          <span>Selecione ou crie um workspace para usar o pipeline.</span>
        </div>
      </Card>
    );
  }

  const averageTicket =
    board && board.open_opportunities > 0
      ? Number(board.total_pipeline_value) / board.open_opportunities
      : 0;

  return (
    <div className="page-stack pipeline-page">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Comercial</p>
          <h1>Pipeline</h1>
          <p>
            Visualize e mova negociações entre as etapas do funil comercial.
          </p>
        </div>
        <div className="page-header__actions">
          <Button
            variant="secondary"
            onClick={() => void loadBoard()}
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

      <section className="pipeline-summary">
        <div className="pipeline-summary__item">
          <span>Pipeline aberto</span>
          <strong>
            {formatCurrency(board?.total_pipeline_value ?? "0.00")}
          </strong>
        </div>
        <div className="pipeline-summary__item">
          <span>Oportunidades abertas</span>
          <strong>{board?.open_opportunities ?? 0}</strong>
        </div>
        <div className="pipeline-summary__item">
          <span>Ticket médio aberto</span>
          <strong>{formatCurrency(String(averageTicket))}</strong>
        </div>
        <div className="pipeline-summary__item">
          <span>Etapas configuradas</span>
          <strong>{board?.pipeline.length ?? segmentConfig?.pipeline.length ?? 0}</strong>
        </div>
      </section>

      <Card className="pipeline-toolbar-card">
        <div className="pipeline-toolbar">
          <div className="pipeline-search">
            <Search size={17} />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Buscar oportunidade, lead, telefone ou interesse..."
            />
          </div>
          <div className="pipeline-owner-filter">
            <SlidersHorizontal size={15} />
            <select
              value={owner}
              onChange={(event) => setOwner(event.target.value)}
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
          <Button variant="ghost" onClick={() => void loadBoard()}>
            Tentar novamente
          </Button>
        </div>
      )}

      {loading && !board ? (
        <Card>
          <div className="table-loading">
            <RefreshCw size={20} className="spin" />
            <span>Carregando pipeline...</span>
          </div>
        </Card>
      ) : board ? (
        <div className="pipeline-board-wrap">
          <div
            className="pipeline-board"
            style={{
              gridTemplateColumns: `repeat(${Math.max(board.stages.length, 1)}, minmax(292px, 1fr))`,
            }}
          >
            {board.stages.map((stage) => (
              <section
                className={`pipeline-column ${
                  draggingId ? "pipeline-column--drop-ready" : ""
                }`}
                key={stage.code}
                onDragOver={(event) => event.preventDefault()}
                onDrop={(event) => {
                  event.preventDefault();
                  const id =
                    event.dataTransfer.getData("text/opportunity-id") ||
                    draggingId;
                  if (id) {
                    void handleMove(id, stage.code);
                  }
                }}
              >
                <header className="pipeline-column__header">
                  <div>
                    <span className="pipeline-column__title">
                      {labelize(stage.code)}
                    </span>
                    <span className="pipeline-column__count">
                      {stage.total_count}
                    </span>
                  </div>
                  <strong>{formatCurrency(stage.total_value)}</strong>
                </header>

                <div className="pipeline-column__body">
                  {stage.opportunities.length > 0 ? (
                    stage.opportunities.map((opportunity) => (
                      <article
                        key={opportunity.public_id}
                        className={`pipeline-card ${
                          movingId === opportunity.public_id
                            ? "pipeline-card--moving"
                            : ""
                        }`}
                        draggable={movingId !== opportunity.public_id}
                        onDragStart={(event) => {
                          setDraggingId(opportunity.public_id);
                          event.dataTransfer.effectAllowed = "move";
                          event.dataTransfer.setData(
                            "text/opportunity-id",
                            opportunity.public_id,
                          );
                        }}
                        onDragEnd={() => setDraggingId(null)}
                        onClick={() => void openDetails(opportunity)}
                      >
                        <div className="pipeline-card__top">
                          <span className="pipeline-card__drag">
                            <GripVertical size={15} />
                          </span>
                          <span className="pipeline-card__id">
                            {opportunity.public_id}
                          </span>
                        </div>

                        <div className="pipeline-card__main">
                          <strong>{opportunity.title}</strong>
                          <span>{opportunity.lead_name}</span>
                          {opportunity.lead_interest && (
                            <small>{opportunity.lead_interest}</small>
                          )}
                        </div>

                        <div className="pipeline-card__value">
                          <CircleDollarSign size={15} />
                          <strong>
                            {formatCurrency(
                              opportunity.value_amount,
                              opportunity.currency,
                            )}
                          </strong>
                        </div>

                        <div className="pipeline-card__footer">
                          <span>
                            <UserRound size={13} />
                            {opportunity.owner_name ?? "Sem responsável"}
                          </span>
                          {opportunity.expected_close_date && (
                            <time>
                              {formatDate(opportunity.expected_close_date)}
                            </time>
                          )}
                        </div>
                      </article>
                    ))
                  ) : (
                    <div className="pipeline-column__empty">
                      <span>Solte uma oportunidade aqui</span>
                    </div>
                  )}
                </div>
              </section>
            ))}
          </div>
        </div>
      ) : null}

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

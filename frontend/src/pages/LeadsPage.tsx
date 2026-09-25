import {
  ChevronLeft,
  ChevronRight,
  FileSpreadsheet,
  FilterX,
  Inbox,
  ListChecks,
  MoreHorizontal,
  RefreshCw,
  Search,
  Send,
  SlidersHorizontal,
  Upload,
  UserPlus,
  Waypoints,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";

import { CsvImportModal } from "../components/leads/CsvImportModal";
import { LeadBatchMessageModal } from "../components/leads/LeadBatchMessageModal";
import { LeadBatchTriageModal } from "../components/leads/LeadBatchTriageModal";
import { LeadConsentModal } from "../components/leads/LeadConsentModal";
import { LeadDistributionModal } from "../components/leads/LeadDistributionModal";
import { LeadDetailsDrawer } from "../components/leads/LeadDetailsDrawer";
import { LeadFormModal } from "../components/leads/LeadFormModal";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { Modal } from "../components/ui/Modal";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type {
  Lead,
  LeadFilters,
  LeadIntakeResult,
  LeadPage,
  LeadPayload,
  WorkspaceMember,
  WorkspaceSegmentConfig,
} from "../types/leads";

const PAGE_SIZE = 12;

const initialFilters: LeadFilters = {
  q: "",
  status: "",
  priority: "",
  source: "",
  channel: "",
  campaign: "",
  owner: "",
  active: "true",
};

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\w/g, (letter) => letter.toUpperCase());
}

function priorityTone(priority: string) {
  if (priority === "urgente") return "danger" as const;
  if (priority === "alta") return "warning" as const;
  if (priority === "baixa") return "neutral" as const;
  return "info" as const;
}

function initials(name: string) {
  return name
    .split(" ")
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

export function LeadsPage() {
  const [searchParams] = useSearchParams();
  const searchQuery = searchParams.get("q")?.trim() ?? "";
  const auth = useAuth();
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [filters, setFilters] = useState<LeadFilters>(initialFilters);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<LeadPage | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [segmentConfig, setSegmentConfig] =
    useState<WorkspaceSegmentConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [metadataLoading, setMetadataLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [editingLead, setEditingLead] = useState<Lead | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | "intake" | null>(
    null,
  );
  const [deactivateLead, setDeactivateLead] = useState<Lead | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [csvImportOpen, setCsvImportOpen] = useState(false);
  const [distributionOpen, setDistributionOpen] = useState(false);
  const [consentLead, setConsentLead] = useState<Lead | null>(null);
  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  const [batchOpen, setBatchOpen] = useState(false);
  const [batchMessageOpen, setBatchMessageOpen] = useState(false);


  useEffect(() => {
    if (!searchQuery) return;
    setFilters((current) =>
      current.q === searchQuery ? current : { ...current, q: searchQuery },
    );
    setPage(1);
  }, [searchQuery]);

  const activeMembers = useMemo(
    () =>
      members.filter((member) => member.membership_active && member.user_active),
    [members],
  );

  const canAssignLeads = useMemo(() => {
    if (!workspace) return false;
    return Boolean(
      auth.workspaces
        .find((item) => item.public_id === workspace.public_id)
        ?.permissions.includes("leads.assign"),
    );
  }, [auth.workspaces, workspace]);

  const canSendWhatsApp = useMemo(() => {
    if (!workspace) return false;
    return Boolean(
      auth.workspaces
        .find((item) => item.public_id === workspace.public_id)
        ?.permissions.includes("activities.create"),
    );
  }, [auth.workspaces, workspace]);

  const pageLeadIds = useMemo(
    () => data?.items.map((lead) => lead.public_id) ?? [],
    [data],
  );

  const allPageSelected = useMemo(
    () =>
      pageLeadIds.length > 0 &&
      pageLeadIds.every((publicId) => selectedLeadIds.includes(publicId)),
    [pageLeadIds, selectedLeadIds],
  );

  const memberById = useMemo(
    () => new Map(activeMembers.map((member) => [member.public_id, member])),
    [activeMembers],
  );

  const hasFilters = useMemo(
    () =>
      Object.entries(filters).some(([key, value]) => {
        if (key === "active") {
          return value !== "true";
        }
        return Boolean(value);
      }),
    [filters],
  );

  const loadMetadata = useCallback(async () => {
    if (!workspace) {
      setMembers([]);
      setSegmentConfig(null);
      return;
    }

    setMetadataLoading(true);
    try {
      const [memberItems, config] = await Promise.all([
        api.get<WorkspaceMember[]>(
          `/workspaces/${workspace.public_id}/members`,
        ),
        api.get<WorkspaceSegmentConfig>(
          `/workspaces/${workspace.public_id}/segment-config`,
        ),
      ]);
      setMembers(memberItems);
      setSegmentConfig(config);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar os metadados dos leads.",
      );
    } finally {
      setMetadataLoading(false);
    }
  }, [workspace]);

  const loadLeads = useCallback(async () => {
    if (!workspace) {
      setData(null);
      return;
    }

    setLoading(true);
    setError(null);

    const params = new URLSearchParams({
      page: String(page),
      page_size: String(PAGE_SIZE),
    });

    if (filters.q.trim()) params.set("q", filters.q.trim());
    if (filters.status) params.set("lead_status", filters.status);
    if (filters.priority) params.set("priority", filters.priority);
    if (filters.source.trim()) params.set("source", filters.source.trim());
    if (filters.channel.trim()) params.set("channel", filters.channel.trim());
    if (filters.campaign.trim()) params.set("campaign", filters.campaign.trim());

    if (filters.owner === "unassigned") {
      params.set("unassigned", "true");
    } else if (filters.owner) {
      params.set("owner_user_public_id", filters.owner);
    }

    if (filters.active !== "all") {
      params.set("active", filters.active);
    }

    try {
      const result = await api.get<LeadPage>(
        `/workspaces/${workspace.public_id}/leads/search?${params.toString()}`,
      );
      setData(result);

      if (result.total_pages > 0 && page > result.total_pages) {
        setPage(result.total_pages);
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar os leads.",
      );
    } finally {
      setLoading(false);
    }
  }, [filters, page, workspace]);

  useEffect(() => {
    setFilters(initialFilters);
    setPage(1);
    setSelectedLead(null);
    void loadMetadata();
  }, [loadMetadata, workspace?.public_id]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadLeads();
    }, filters.q ? 250 : 0);

    return () => window.clearTimeout(timer);
  }, [filters.q, loadLeads]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function updateFilter<K extends keyof LeadFilters>(
    key: K,
    value: LeadFilters[K],
  ) {
    setFilters((current) => ({ ...current, [key]: value }));
    setPage(1);
  }

  function toggleLeadSelection(publicId: string) {
    setSelectedLeadIds((current) =>
      current.includes(publicId)
        ? current.filter((item) => item !== publicId)
        : current.length >= 100
          ? current
          : [...current, publicId],
    );
  }

  function toggleCurrentPageSelection() {
    setSelectedLeadIds((current) => {
      if (allPageSelected) {
        return current.filter((item) => !pageLeadIds.includes(item));
      }
      const next = [...current];
      for (const publicId of pageLeadIds) {
        if (!next.includes(publicId) && next.length < 100) {
          next.push(publicId);
        }
      }
      return next;
    });
  }

  function openCreate(mode: "create" | "intake") {
    setEditingLead(null);
    setFormError(null);
    setFormMode(mode);
  }

  function openEdit(lead: Lead) {
    setSelectedLead(null);
    setEditingLead(lead);
    setFormError(null);
    setFormMode("edit");
  }

  async function handleSubmit(payload: LeadPayload) {
    if (!workspace || !formMode) return;

    setSaving(true);
    setFormError(null);

    try {
      if (formMode === "edit" && editingLead) {
        const updated = await api.patch<Lead>(
          `/workspaces/${workspace.public_id}/leads/${editingLead.public_id}`,
          payload,
        );
        setToast("Lead atualizado com sucesso.");
        setSelectedLead(updated);
      } else if (formMode === "intake") {
        const result = await api.post<LeadIntakeResult>(
          `/workspaces/${workspace.public_id}/leads/intake`,
          payload,
        );
        setToast(
          result.action === "duplicate_updated"
            ? "Lead existente identificado e atualizado pelo intake."
            : "Entrada registrada e novo lead criado.",
        );
      } else {
        await api.post<Lead>(
          `/workspaces/${workspace.public_id}/leads`,
          payload,
        );
        setToast("Lead criado com sucesso.");
      }

      setFormMode(null);
      setEditingLead(null);
      await loadLeads();
    } catch (requestError) {
      setFormError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível salvar o lead.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function confirmDeactivate() {
    if (!workspace || !deactivateLead) return;

    setSaving(true);
    try {
      await api.post<Lead>(
        `/workspaces/${workspace.public_id}/leads/${deactivateLead.public_id}/deactivate`,
      );
      setToast("Lead desativado.");
      setDeactivateLead(null);
      setSelectedLead(null);
      await loadLeads();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível desativar o lead.",
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
          <span>Crie ou ative um workspace para começar a gerenciar leads.</span>
        </div>
      </Card>
    );
  }

  return (
    <div className="page-stack">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Comercial</p>
          <h1>Leads</h1>
          <p>
            Gerencie contatos, responsáveis, origens e avanço no pipeline.
          </p>
        </div>
        <div className="page-header__actions">
          {selectedLeadIds.length > 0 && (
            <Button variant="secondary" onClick={() => setBatchOpen(true)}>
              <ListChecks size={17} />
              Triagem ({selectedLeadIds.length})
            </Button>
          )}
          {selectedLeadIds.length > 0 && canSendWhatsApp && (
            <Button variant="secondary" onClick={() => setBatchMessageOpen(true)}>
              <Send size={17} />
              Mensagem ({selectedLeadIds.length})
            </Button>
          )}
          {canAssignLeads && (
            <Button variant="secondary" onClick={() => setDistributionOpen(true)}>
              <Waypoints size={17} />
              Distribuição
            </Button>
          )}
          <Button variant="secondary" onClick={() => setCsvImportOpen(true)}>
            <FileSpreadsheet size={17} />
            Importar CSV
          </Button>
          <Button variant="secondary" onClick={() => openCreate("intake")}>
            <Upload size={17} />
            Registrar entrada
          </Button>
          <Button onClick={() => openCreate("create")}>
            <UserPlus size={17} />
            Novo lead
          </Button>
        </div>
      </header>

      <Card className="lead-filter-card">
        <div className="lead-toolbar">
          <div className="lead-search">
            <Search size={17} />
            <input
              type="search"
              placeholder="Buscar por nome, telefone, e-mail, interesse ou campanha..."
              value={filters.q}
              onChange={(event) => updateFilter("q", event.target.value)}
            />
          </div>
          <div className="lead-toolbar__summary">
            <strong>{data?.total ?? 0}</strong>
            <span>{data?.total === 1 ? "lead encontrado" : "leads encontrados"}</span>
          </div>
          <Button
            variant="ghost"
            className="lead-refresh-button"
            onClick={() => void loadLeads()}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
          </Button>
        </div>

        <div className="lead-filters">
          <div className="lead-filters__label">
            <SlidersHorizontal size={15} />
            Filtros
          </div>
          <select
            value={filters.status}
            onChange={(event) => updateFilter("status", event.target.value)}
          >
            <option value="">Todos os status</option>
            {segmentConfig?.pipeline.map((stage) => (
              <option key={stage} value={stage}>
                {labelize(stage)}
              </option>
            ))}
          </select>
          <select
            value={filters.priority}
            onChange={(event) => updateFilter("priority", event.target.value)}
          >
            <option value="">Todas as prioridades</option>
            <option value="baixa">Baixa</option>
            <option value="media">Média</option>
            <option value="alta">Alta</option>
            <option value="urgente">Urgente</option>
          </select>
          <input
            placeholder="Origem"
            value={filters.source}
            onChange={(event) => updateFilter("source", event.target.value)}
          />
          <input
            placeholder="Canal"
            value={filters.channel}
            onChange={(event) => updateFilter("channel", event.target.value)}
          />
          <input
            placeholder="Campanha"
            value={filters.campaign}
            onChange={(event) => updateFilter("campaign", event.target.value)}
          />
          <select
            value={filters.owner}
            onChange={(event) => updateFilter("owner", event.target.value)}
          >
            <option value="">Todos os responsáveis</option>
            <option value="unassigned">Sem responsável</option>
            {activeMembers.map((member) => (
              <option key={member.public_id} value={member.public_id}>
                {member.name}
              </option>
            ))}
          </select>
          <select
            value={filters.active}
            onChange={(event) =>
              updateFilter("active", event.target.value as LeadFilters["active"])
            }
          >
            <option value="true">Ativos</option>
            <option value="false">Inativos</option>
            <option value="all">Todos</option>
          </select>
          {hasFilters && (
            <Button
              variant="ghost"
              className="lead-clear-filters"
              onClick={() => {
                setFilters(initialFilters);
                setPage(1);
              }}
            >
              <FilterX size={15} />
              Limpar
            </Button>
          )}
        </div>
      </Card>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <Button variant="ghost" onClick={() => void loadLeads()}>
            Tentar novamente
          </Button>
        </div>
      )}

      {selectedLeadIds.length > 0 && (
        <div className="batch-selection-bar">
          <span>
            <strong>{selectedLeadIds.length}</strong> lead(s) selecionado(s)
          </span>
          <div>
            <Button variant="ghost" onClick={() => setSelectedLeadIds([])}>
              Limpar seleção
            </Button>
            {canSendWhatsApp && (
              <Button variant="secondary" onClick={() => setBatchMessageOpen(true)}>
                <Send size={16} />
                Enviar mensagem
              </Button>
            )}
            <Button onClick={() => setBatchOpen(true)}>
              <ListChecks size={16} />
              Triar em lote
            </Button>
          </div>
        </div>
      )}

      <Card className="lead-table-card">
        {(loading || metadataLoading) && !data ? (
          <div className="table-loading">
            <RefreshCw size={20} className="spin" />
            <span>Carregando leads...</span>
          </div>
        ) : data && data.items.length > 0 ? (
          <>
            <div className="table-wrap">
              <table className="data-table lead-table">
                <thead>
                  <tr>
                    <th className="lead-select-cell">
                      <input
                        type="checkbox"
                        aria-label="Selecionar leads desta página"
                        checked={allPageSelected}
                        onChange={toggleCurrentPageSelection}
                      />
                    </th>
                    <th>Lead</th>
                    <th>Interesse</th>
                    <th>Origem / canal</th>
                    <th>Campanha</th>
                    <th>Responsável</th>
                    <th>Status</th>
                    <th>Prioridade</th>
                    <th aria-label="Ações" />
                  </tr>
                </thead>
                <tbody>
                  {data.items.map((lead) => {
                    const owner = lead.owner_user_public_id
                      ? memberById.get(lead.owner_user_public_id)
                      : null;

                    return (
                      <tr
                        key={lead.public_id}
                        className={`lead-table__row ${
                          selectedLeadIds.includes(lead.public_id)
                            ? "lead-table__row--selected"
                            : ""
                        }`}
                        onClick={() => setSelectedLead(lead)}
                      >
                        <td
                          className="lead-select-cell"
                          onClick={(event) => event.stopPropagation()}
                        >
                          <input
                            type="checkbox"
                            aria-label={`Selecionar ${lead.name}`}
                            checked={selectedLeadIds.includes(lead.public_id)}
                            onChange={() => toggleLeadSelection(lead.public_id)}
                          />
                        </td>
                        <td>
                          <div className="lead-primary-cell">
                            <span className="lead-avatar lead-avatar--table">
                              {initials(lead.name)}
                            </span>
                            <div>
                              <strong>{lead.name}</strong>
                              <span>{lead.phone ?? lead.email ?? "Sem contato"}</span>
                            </div>
                          </div>
                        </td>
                        <td>{lead.interest ?? "—"}</td>
                        <td>
                          <div className="stacked-cell">
                            <strong>{labelize(lead.source)}</strong>
                            <span>{labelize(lead.channel)}</span>
                          </div>
                        </td>
                        <td>{lead.campaign ?? "—"}</td>
                        <td>
                          <div className="owner-cell">
                            <span className="owner-dot" />
                            {owner?.name ?? "Sem responsável"}
                          </div>
                        </td>
                        <td>
                          <Badge tone="info">{labelize(lead.status)}</Badge>
                        </td>
                        <td>
                          <Badge tone={priorityTone(lead.priority)}>
                            {labelize(lead.priority)}
                          </Badge>
                        </td>
                        <td>
                          <button
                            className="table-action-button"
                            type="button"
                            aria-label={`Abrir ${lead.name}`}
                            onClick={(event) => {
                              event.stopPropagation();
                              setSelectedLead(lead);
                            }}
                          >
                            <MoreHorizontal size={17} />
                          </button>
                        </td>
                      </tr>
                    );
                  })}
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
            <strong>Nenhum lead encontrado</strong>
            <span>
              {hasFilters
                ? "Ajuste os filtros ou limpe a busca para ver outros registros."
                : "Cadastre o primeiro lead ou registre uma entrada externa."}
            </span>
            {!hasFilters && (
              <Button onClick={() => openCreate("create")}>Novo lead</Button>
            )}
          </div>
        )}
      </Card>

      <LeadBatchMessageModal
        open={batchMessageOpen}
        workspacePublicId={workspace.public_id}
        leadPublicIds={selectedLeadIds}
        onClose={() => setBatchMessageOpen(false)}
        onSent={() => {
          setToast("Envio em lote concluído.");
          setSelectedLeadIds([]);
        }}
      />

      <LeadBatchTriageModal
        open={batchOpen}
        workspacePublicId={workspace.public_id}
        leadPublicIds={selectedLeadIds}
        members={activeMembers}
        segmentConfig={segmentConfig}
        canAssign={canAssignLeads}
        onClose={() => setBatchOpen(false)}
        onApplied={() => {
          setToast("Triagem em lote aplicada com sucesso.");
          setBatchOpen(false);
          setSelectedLeadIds([]);
          void loadLeads();
        }}
      />

      <LeadDistributionModal
        open={distributionOpen}
        workspacePublicId={workspace.public_id}
        onClose={() => setDistributionOpen(false)}
        onChanged={() => {
          void loadLeads();
          void loadMetadata();
        }}
      />

      <CsvImportModal
        open={csvImportOpen}
        workspacePublicId={workspace.public_id}
        segmentConfig={segmentConfig}
        onClose={() => setCsvImportOpen(false)}
        onImported={(result) => {
          setToast(
            `Importação concluída: ${result.created} criado(s), ${result.duplicate_updated} atualizado(s).`,
          );
          void loadLeads();
        }}
      />

      <LeadFormModal
        open={formMode !== null}
        mode={formMode ?? "create"}
        lead={editingLead}
        members={activeMembers}
        segmentConfig={segmentConfig}
        saving={saving}
        error={formError}
        onClose={() => {
          if (!saving) {
            setFormMode(null);
            setEditingLead(null);
            setFormError(null);
          }
        }}
        onSubmit={handleSubmit}
      />

      <LeadDetailsDrawer
        lead={selectedLead}
        members={activeMembers}
        onClose={() => setSelectedLead(null)}
        onEdit={openEdit}
        onDeactivate={(lead) => setDeactivateLead(lead)}
        onManageConsent={(lead) => setConsentLead(lead)}
      />

      <LeadConsentModal
        open={consentLead !== null}
        workspacePublicId={workspace.public_id}
        lead={consentLead}
        onClose={() => setConsentLead(null)}
        onChanged={() => {
          void loadLeads();
        }}
      />

      <Modal
        open={deactivateLead !== null}
        title="Desativar lead"
        description="O registro continuará disponível na auditoria e poderá ser consultado usando o filtro de inativos."
        onClose={() => !saving && setDeactivateLead(null)}
        size="sm"
        footer={
          <>
            <Button
              variant="secondary"
              disabled={saving}
              onClick={() => setDeactivateLead(null)}
            >
              Cancelar
            </Button>
            <Button
              variant="danger"
              disabled={saving}
              onClick={() => void confirmDeactivate()}
            >
              {saving ? "Desativando..." : "Confirmar desativação"}
            </Button>
          </>
        }
      >
        <div className="confirmation-copy">
          <strong>{deactivateLead?.name}</strong>
          <p>Esse lead deixará de aparecer na visualização padrão de ativos.</p>
        </div>
      </Modal>

      {toast && <div className="toast toast--success">{toast}</div>}
    </div>
  );
}

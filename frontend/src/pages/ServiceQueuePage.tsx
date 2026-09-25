import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  RefreshCw,
  Save,
  TimerReset,
  UserRoundX,
  UsersRound,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type { WorkspaceMember } from "../types/leads";
import type {
  LeadSlaConfig,
  LeadSlaQueue,
  LeadSlaQueueItem,
  LeadSlaState,
} from "../types/leadSla";

const defaultConfig: LeadSlaConfig = {
  enabled: true,
  first_response_minutes: 15,
  warning_before_minutes: 5,
  follow_up_due_hours: 24,
  stale_lead_hours: 24,
};

function formatDateTime(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatMinutes(minutes: number) {
  if (minutes < 60) return `${minutes} min`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest ? `${hours}h ${rest}min` : `${hours}h`;
}

function slaTone(state: LeadSlaState) {
  if (state === "breached") return "danger" as const;
  if (state === "warning") return "warning" as const;
  if (state === "contacted") return "success" as const;
  return "info" as const;
}

function slaLabel(state: LeadSlaState) {
  if (state === "breached") return "SLA estourado";
  if (state === "warning") return "SLA em alerta";
  if (state === "contacted") return "Contatado";
  return "Aguardando contato";
}

const reasonLabels: Record<string, string> = {
  first_response_breached: "Primeiro contato atrasado",
  first_response_warning: "SLA perto do limite",
  awaiting_first_contact: "Sem primeiro contato",
  overdue_followup: "Retorno vencido",
  followup_due_soon: "Retorno próximo",
  stale_lead: "Lead sem contato recente",
  unassigned: "Sem responsável",
};

export function ServiceQueuePage() {
  const auth = useAuth();
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [queue, setQueue] = useState<LeadSlaQueue | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [ownerFilter, setOwnerFilter] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [config, setConfig] = useState<LeadSlaConfig>(defaultConfig);

  const currentWorkspaceAccess = useMemo(
    () => auth.workspaces.find((item) => item.public_id === workspace?.public_id),
    [auth.workspaces, workspace?.public_id],
  );
  const canConfigure = Boolean(
    currentWorkspaceAccess?.permissions.includes("settings.update"),
  );

  const activeMembers = useMemo(
    () => members.filter((item) => item.user_active && item.membership_active),
    [members],
  );

  const load = useCallback(async () => {
    if (!workspace) {
      setQueue(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "150" });
      if (ownerFilter === "unassigned") {
        params.set("unassigned", "true");
      } else if (ownerFilter) {
        params.set("owner_user_public_id", ownerFilter);
      }
      const [result, memberItems] = await Promise.all([
        api.get<LeadSlaQueue>(
          `/workspaces/${workspace.public_id}/lead-sla/queue?${params.toString()}`,
        ),
        api.get<WorkspaceMember[]>(`/workspaces/${workspace.public_id}/members`),
      ]);
      setQueue(result);
      setConfig(result.config);
      setMembers(memberItems);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a fila inteligente.",
      );
    } finally {
      setLoading(false);
    }
  }, [ownerFilter, workspace]);

  useEffect(() => {
    setOwnerFilter("");
  }, [workspace?.public_id]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function saveConfig() {
    if (!workspace || !canConfigure) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.put<LeadSlaConfig>(
        `/workspaces/${workspace.public_id}/lead-sla/config`,
        config,
      );
      setConfig(saved);
      setToast("Configuração de SLA atualizada.");
      await load();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível salvar a configuração.",
      );
    } finally {
      setSaving(false);
    }
  }

  function updateNumber(key: keyof LeadSlaConfig, raw: string) {
    const value = Math.max(0, Number(raw) || 0);
    setConfig((current) => ({ ...current, [key]: value }));
  }

  const metrics = queue?.metrics;

  return (
    <div className="page-stack sla-page">
      <div className="page-heading-row">
        <div>
          <span className="eyebrow">Sprint 5 · Operação comercial</span>
          <h1>Fila inteligente de atendimento</h1>
          <p>
            Prioriza primeiro contato, retornos vencidos e leads sem interação recente.
          </p>
        </div>
        <Button variant="secondary" onClick={() => void load()} disabled={loading || workspaceLoading}>
          <RefreshCw size={17} className={loading ? "spin" : ""} />
          Atualizar fila
        </Button>
      </div>

      {error && <div className="page-alert page-alert--danger">{error}</div>}
      {toast && <div className="page-alert page-alert--success">{toast}</div>}

      <div className="sla-metrics-grid">
        <Metric label="Na fila" value={metrics?.total_attention ?? 0} icon={<UsersRound size={18} />} />
        <Metric label="SLA estourado" value={metrics?.sla_breached ?? 0} icon={<AlertTriangle size={18} />} tone="danger" />
        <Metric label="Retornos vencidos" value={metrics?.overdue_followups ?? 0} icon={<TimerReset size={18} />} tone="warning" />
        <Metric label="Sem responsável" value={metrics?.unassigned ?? 0} icon={<UserRoundX size={18} />} />
      </div>

      <Card
        title="Fila do dia"
        description="Itens com maior urgência aparecem primeiro. A pontuação combina SLA, retorno, inatividade e prioridade do lead."
        actions={
          <select
            className="sla-owner-filter"
            aria-label="Filtrar responsável"
            value={ownerFilter}
            onChange={(event) => setOwnerFilter(event.target.value)}
          >
            <option value="">Toda a equipe</option>
            {auth.user && <option value={auth.user.public_id}>Minha fila</option>}
            <option value="unassigned">Sem responsável</option>
            {activeMembers
              .filter((member) => member.public_id !== auth.user?.public_id)
              .map((member) => (
                <option key={member.public_id} value={member.public_id}>
                  {member.name}
                </option>
              ))}
          </select>
        }
      >
        {!queue?.config.enabled ? (
          <div className="sla-empty">
            <CheckCircle2 size={24} />
            <div><strong>Fila de SLA desativada</strong><p>Ative a configuração abaixo para gerar prioridades operacionais.</p></div>
          </div>
        ) : loading && !queue ? (
          <div className="sla-empty"><Clock3 size={24} /><p>Calculando prioridades...</p></div>
        ) : queue?.items.length ? (
          <div className="sla-queue-list">
            {queue.items.map((item) => <QueueRow key={item.lead_public_id} item={item} />)}
          </div>
        ) : (
          <div className="sla-empty">
            <CheckCircle2 size={24} />
            <div><strong>Nenhuma pendência crítica</strong><p>A fila não encontrou leads que precisem de atenção agora.</p></div>
          </div>
        )}
      </Card>

      <Card
        title="Política de SLA"
        description={canConfigure ? "Defina os limites usados pela fila inteligente." : "Somente administradores podem alterar estes limites."}
      >
        <div className="sla-config-grid">
          <label className="form-field sla-toggle-field">
            <span>Fila inteligente</span>
            <input
              type="checkbox"
              checked={config.enabled}
              disabled={!canConfigure}
              onChange={(event) => setConfig((current) => ({ ...current, enabled: event.target.checked }))}
            />
          </label>
          <label className="form-field">
            <span>Primeiro contato (min)</span>
            <input type="number" min={1} max={1440} value={config.first_response_minutes} disabled={!canConfigure} onChange={(event) => updateNumber("first_response_minutes", event.target.value)} />
          </label>
          <label className="form-field">
            <span>Alerta antes do limite (min)</span>
            <input type="number" min={0} max={1439} value={config.warning_before_minutes} disabled={!canConfigure} onChange={(event) => updateNumber("warning_before_minutes", event.target.value)} />
          </label>
          <label className="form-field">
            <span>Mostrar retorno nas próximas (h)</span>
            <input type="number" min={1} max={168} value={config.follow_up_due_hours} disabled={!canConfigure} onChange={(event) => updateNumber("follow_up_due_hours", event.target.value)} />
          </label>
          <label className="form-field">
            <span>Lead sem contato após (h)</span>
            <input type="number" min={1} max={720} value={config.stale_lead_hours} disabled={!canConfigure} onChange={(event) => updateNumber("stale_lead_hours", event.target.value)} />
          </label>
        </div>
        {canConfigure && (
          <div className="sla-config-actions">
            <Button onClick={() => void saveConfig()} disabled={saving}>
              <Save size={17} />
              {saving ? "Salvando..." : "Salvar política"}
            </Button>
          </div>
        )}
      </Card>
    </div>
  );
}

function Metric({ label, value, icon, tone = "neutral" }: { label: string; value: number; icon: ReactNode; tone?: "neutral" | "warning" | "danger" }) {
  return (
    <div className={`sla-metric sla-metric--${tone}`}>
      <div className="sla-metric__icon">{icon}</div>
      <div><span>{label}</span><strong>{value}</strong></div>
    </div>
  );
}

function QueueRow({ item }: { item: LeadSlaQueueItem }) {
  return (
    <article className="sla-queue-row">
      <div className="sla-queue-row__main">
        <div className="sla-queue-row__title">
          <strong>{item.lead_name}</strong>
          <Badge tone={slaTone(item.sla_state)}>{slaLabel(item.sla_state)}</Badge>
          <Badge tone={item.priority === "urgente" ? "danger" : item.priority === "alta" ? "warning" : "neutral"}>{item.priority}</Badge>
        </div>
        <div className="sla-queue-row__meta">
          <span>{item.owner_name ?? "Sem responsável"}</span>
          <span>{item.interest ?? "Sem interesse informado"}</span>
          <span>{item.source}</span>
        </div>
        <div className="sla-reasons">
          {item.reasons.map((reason) => <span key={reason}>{reasonLabels[reason] ?? reason}</span>)}
        </div>
      </div>
      <div className="sla-queue-row__timing">
        <div><span>Prazo SLA</span><strong>{formatDateTime(item.sla_due_at)}</strong></div>
        <div><span>Idade</span><strong>{formatMinutes(item.age_minutes)}</strong></div>
        <div><span>Próximo retorno</span><strong>{formatDateTime(item.next_followup_due_at)}</strong></div>
        <div className="sla-score"><span>Prioridade</span><strong>{item.score}</strong></div>
      </div>
    </article>
  );
}

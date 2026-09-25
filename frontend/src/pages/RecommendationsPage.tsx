import {
  AlertTriangle,
  ArrowRight,
  BrainCircuit,
  Clock3,
  MessageCircleReply,
  RefreshCw,
  Sparkles,
  UserRoundX,
} from "lucide-react";
import { type ReactNode, useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type { WorkspaceMember } from "../types/leads";
import type {
  LeadRecommendationBoard,
  LeadRecommendationItem,
  RecommendationAction,
  RecommendationUrgency,
} from "../types/leadRecommendations";

const actionOptions: Array<{ value: RecommendationAction | ""; label: string }> = [
  { value: "", label: "Todas as ações" },
  { value: "assign_owner", label: "Atribuir responsável" },
  { value: "reply_whatsapp", label: "Responder WhatsApp" },
  { value: "first_contact", label: "Primeiro contato" },
  { value: "follow_up", label: "Retorno vencido" },
  { value: "recover_opportunity", label: "Recuperar negociação" },
  { value: "reengage", label: "Reengajar" },
  { value: "enroll_cadence", label: "Incluir em cadência" },
  { value: "advance_opportunity", label: "Avançar negociação" },
  { value: "review_lead", label: "Revisar próximo passo" },
];

const urgencyLabels: Record<RecommendationUrgency, string> = {
  critical: "Crítica",
  high: "Alta",
  medium: "Média",
  low: "Baixa",
};

function urgencyTone(urgency: RecommendationUrgency) {
  if (urgency === "critical") return "danger" as const;
  if (urgency === "high") return "warning" as const;
  if (urgency === "medium") return "info" as const;
  return "neutral" as const;
}

function channelLabel(channel: LeadRecommendationItem["suggested_channel"]) {
  if (channel === "whatsapp") return "WhatsApp";
  if (channel === "phone") return "Ligação";
  if (channel === "email") return "E-mail";
  return "Manual";
}

function formatDateTime(value: string | null) {
  if (!value) return "—";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

export function RecommendationsPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [board, setBoard] = useState<LeadRecommendationBoard | null>(null);
  const [members, setMembers] = useState<WorkspaceMember[]>([]);
  const [owner, setOwner] = useState("");
  const [urgency, setUrgency] = useState<RecommendationUrgency | "">("");
  const [action, setAction] = useState<RecommendationAction | "">("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeMembers = useMemo(
    () => members.filter((item) => item.user_active && item.membership_active),
    [members],
  );

  const load = useCallback(async () => {
    if (!workspace) {
      setBoard(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "150" });
      if (owner) params.set("owner_user_public_id", owner);
      if (urgency) params.set("urgency", urgency);
      if (action) params.set("action", action);
      const [result, memberItems] = await Promise.all([
        api.get<LeadRecommendationBoard>(
          `/workspaces/${workspace.public_id}/lead-recommendations?${params.toString()}`,
        ),
        api.get<WorkspaceMember[]>(`/workspaces/${workspace.public_id}/members`),
      ]);
      setBoard(result);
      setMembers(memberItems);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as recomendações comerciais.",
      );
    } finally {
      setLoading(false);
    }
  }, [action, owner, urgency, workspace]);

  useEffect(() => {
    setOwner("");
    setUrgency("");
    setAction("");
  }, [workspace?.public_id]);

  useEffect(() => {
    void load();
  }, [load]);

  const metrics = board?.metrics;

  return (
    <div className="page-stack recommendations-page">
      <div className="page-heading-row">
        <div>
          <span className="eyebrow">Sprint 5 · Inteligência operacional</span>
          <h1>Recomendações comerciais</h1>
          <p>
            Prioriza o próximo melhor passo com regras transparentes de SLA, resposta,
            cadência e oportunidade.
          </p>
        </div>
        <Button variant="secondary" onClick={() => void load()} disabled={loading || workspaceLoading}>
          <RefreshCw size={17} className={loading ? "spin" : ""} />
          Atualizar recomendações
        </Button>
      </div>

      {error && <div className="page-alert page-alert--danger">{error}</div>}

      <div className="recommendations-metrics-grid">
        <Metric label="Recomendações" value={metrics?.total_leads ?? 0} icon={<BrainCircuit size={18} />} />
        <Metric label="Críticas" value={metrics?.critical ?? 0} icon={<AlertTriangle size={18} />} tone="danger" />
        <Metric label="Aguardando resposta" value={metrics?.awaiting_reply ?? 0} icon={<MessageCircleReply size={18} />} tone="warning" />
        <Metric label="Sem responsável" value={metrics?.unassigned ?? 0} icon={<UserRoundX size={18} />} />
        <Metric label="Negociações em risco" value={metrics?.opportunities_at_risk ?? 0} icon={<Clock3 size={18} />} tone="warning" />
      </div>

      <Card
        title="Próximo melhor passo"
        description="A ordenação combina prioridade do lead e sinais operacionais. Nenhuma recomendação é executada automaticamente."
        actions={
          <div className="recommendations-filters">
            <select aria-label="Filtrar responsável" value={owner} onChange={(event) => setOwner(event.target.value)}>
              <option value="">Toda a equipe</option>
              {auth.user && <option value={auth.user.public_id}>Minhas recomendações</option>}
              {activeMembers
                .filter((item) => item.public_id !== auth.user?.public_id)
                .map((item) => (
                  <option key={item.public_id} value={item.public_id}>{item.name}</option>
                ))}
            </select>
            <select
              aria-label="Filtrar urgência"
              value={urgency}
              onChange={(event) => setUrgency(event.target.value as RecommendationUrgency | "")}
            >
              <option value="">Todas as urgências</option>
              <option value="critical">Crítica</option>
              <option value="high">Alta</option>
              <option value="medium">Média</option>
              <option value="low">Baixa</option>
            </select>
            <select
              aria-label="Filtrar ação"
              value={action}
              onChange={(event) => setAction(event.target.value as RecommendationAction | "")}
            >
              {actionOptions.map((item) => <option key={item.value || "all"} value={item.value}>{item.label}</option>)}
            </select>
          </div>
        }
      >
        {loading && !board ? (
          <div className="recommendations-empty"><Sparkles size={24} /><p>Analisando carteira...</p></div>
        ) : board?.items.length ? (
          <div className="recommendations-list">
            {board.items.map((item) => (
              <RecommendationRow
                key={item.lead_public_id}
                item={item}
                onOpenLead={() => navigate(`/leads?q=${encodeURIComponent(item.lead_name)}`)}
              />
            ))}
          </div>
        ) : (
          <div className="recommendations-empty">
            <Sparkles size={24} />
            <div>
              <strong>Nenhuma recomendação para os filtros atuais</strong>
              <p>Altere os filtros ou atualize a carteira.</p>
            </div>
          </div>
        )}
      </Card>

      <Card title="Como o motor decide" description="O ranking é determinístico e auditável; não usa uma IA externa para decidir sozinho.">
        <div className="recommendations-explain-grid">
          <div><strong>1. Urgência operacional</strong><span>Resposta aguardando, SLA e retornos vencidos recebem mais peso.</span></div>
          <div><strong>2. Contexto comercial</strong><span>Prioridade do lead, responsável, cadência e oportunidade aberta entram no score.</span></div>
          <div><strong>3. Canal permitido</strong><span>WhatsApp, ligação ou e-mail são sugeridos respeitando consentimento e opt-out.</span></div>
          <div><strong>4. Melhor janela</strong><span>Quando há histórico suficiente, o CRM calcula a janela com mais contatos concluídos.</span></div>
        </div>
      </Card>
    </div>
  );
}

function Metric({ label, value, icon, tone = "neutral" }: { label: string; value: number; icon: ReactNode; tone?: "neutral" | "warning" | "danger" }) {
  return (
    <div className={`recommendations-metric recommendations-metric--${tone}`}>
      <div className="recommendations-metric__icon">{icon}</div>
      <div><span>{label}</span><strong>{value}</strong></div>
    </div>
  );
}

function RecommendationRow({ item, onOpenLead }: { item: LeadRecommendationItem; onOpenLead: () => void }) {
  return (
    <article className="recommendation-row">
      <div className="recommendation-row__main">
        <div className="recommendation-row__title">
          <strong>{item.lead_name}</strong>
          <Badge tone={urgencyTone(item.urgency)}>{urgencyLabels[item.urgency]}</Badge>
          <Badge tone="neutral">Score {item.score}</Badge>
        </div>
        <div className="recommendation-row__action">
          <Sparkles size={16} />
          <strong>{item.action_title}</strong>
          <span>via {channelLabel(item.suggested_channel)}</span>
          {item.suggested_contact_window && <span>· janela {item.suggested_contact_window}</span>}
        </div>
        <div className="recommendation-row__meta">
          <span>{item.owner_name ?? "Sem responsável"}</span>
          <span>{item.interest ?? "Sem interesse informado"}</span>
          <span>{item.source}</span>
          {item.open_opportunity_stage && <span>Oportunidade: {item.open_opportunity_stage}</span>}
        </div>
        <div className="recommendation-row__reasons">
          {item.reasons.map((reason) => <span key={reason}>{reason}</span>)}
        </div>
      </div>
      <div className="recommendation-row__aside">
        <div><span>Último contato</span><strong>{formatDateTime(item.last_contact_at)}</strong></div>
        <div><span>Último WhatsApp</span><strong>{formatDateTime(item.last_whatsapp_at)}</strong></div>
        <Button variant="secondary" onClick={onOpenLead}>
          Abrir lead <ArrowRight size={16} />
        </Button>
      </div>
    </article>
  );
}

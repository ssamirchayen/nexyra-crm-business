import {
  CalendarClock,
  CheckCircle2,
  CirclePause,
  Play,
  Plus,
  RefreshCw,
  Workflow,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useAuth } from "../contexts/AuthContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type { LeadPage } from "../types/leads";
import type {
  LeadCadence,
  LeadCadenceEnrollment,
  LeadCadenceProcessResult,
  LeadCadenceStep,
} from "../types/leadCadences";

const actionLabels: Record<string, string> = {
  call: "Ligação",
  whatsapp: "WhatsApp",
  email: "E-mail",
  follow_up: "Follow-up",
  task: "Tarefa",
};

function formatWhen(value: string | null | undefined) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  try {
    return new Intl.DateTimeFormat("pt-BR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch {
    return "—";
  }
}

function delayLabel(minutes: number) {
  if (minutes === 0) return "imediato";
  if (minutes < 60) return `${minutes} min`;
  if (minutes % 1440 === 0) return `${minutes / 1440} dia(s)`;
  if (minutes % 60 === 0) return `${minutes / 60}h`;
  return `${minutes} min`;
}

type DraftStep = Omit<LeadCadenceStep, "position">;

const newStep = (): DraftStep => ({
  delay_minutes: 0,
  action_type: "follow_up",
  title: "Novo follow-up",
  message_template: null,
});

export function CadencesPage() {
  const auth = useAuth();
  const { workspace } = useWorkspace();
  const [cadences, setCadences] = useState<LeadCadence[]>([]);
  const [enrollments, setEnrollments] = useState<LeadCadenceEnrollment[]>([]);
  const [leads, setLeads] = useState<LeadPage["items"]>([]);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [steps, setSteps] = useState<DraftStep[]>([newStep()]);
  const [selectedCadence, setSelectedCadence] = useState("");
  const [selectedLead, setSelectedLead] = useState("");

  const currentWorkspaceAccess = useMemo(
    () => auth.workspaces.find((item) => item.public_id === workspace?.public_id),
    [auth.workspaces, workspace?.public_id],
  );
  const canConfigure = Boolean(
    currentWorkspaceAccess?.permissions?.includes("settings.update"),
  );

  const load = useCallback(async () => {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const [cadenceItems, enrollmentItems, leadPage] = await Promise.all([
        api.get<LeadCadence[]>(`/workspaces/${workspace.public_id}/lead-cadences`),
        api.get<LeadCadenceEnrollment[]>(
          `/workspaces/${workspace.public_id}/lead-cadence-enrollments`,
        ),
        api.get<LeadPage>(`/workspaces/${workspace.public_id}/leads?page=1&page_size=100&active=true`),
      ]);
      const safeCadences = Array.isArray(cadenceItems)
        ? cadenceItems.map((item) => ({
            ...item,
            steps: Array.isArray(item.steps) ? item.steps : [],
            active_enrollments: Number(item.active_enrollments) || 0,
          }))
        : [];
      const safeEnrollments = Array.isArray(enrollmentItems) ? enrollmentItems : [];
      const safeLeads = Array.isArray(leadPage?.items) ? leadPage.items : [];

      setCadences(safeCadences);
      setEnrollments(safeEnrollments);
      setLeads(safeLeads);
      if (!selectedCadence && safeCadences.length) {
        setSelectedCadence(safeCadences.find((item) => item.active)?.public_id ?? "");
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as cadências.",
      );
    } finally {
      setLoading(false);
    }
  }, [selectedCadence, workspace]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  function updateStep(index: number, patch: Partial<DraftStep>) {
    setSteps((current) =>
      current.map((item, position) =>
        position === index ? { ...item, ...patch } : item,
      ),
    );
  }

  async function createCadence() {
    if (!workspace || !name.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await api.post(`/workspaces/${workspace.public_id}/lead-cadences`, {
        name: name.trim(),
        description: description.trim() || null,
        active: true,
        stop_on_reply: true,
        steps,
      });
      setName("");
      setDescription("");
      setSteps([newStep()]);
      setShowCreate(false);
      setToast("Cadência criada.");
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao criar cadência.");
    } finally {
      setSaving(false);
    }
  }

  async function enrollLead() {
    if (!workspace || !selectedCadence || !selectedLead) return;
    setSaving(true);
    setError(null);
    try {
      await api.post(`/workspaces/${workspace.public_id}/lead-cadence-enrollments`, {
        lead_public_id: selectedLead,
        cadence_public_id: selectedCadence,
      });
      setSelectedLead("");
      setToast("Lead incluído na cadência.");
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao incluir lead.");
    } finally {
      setSaving(false);
    }
  }

  async function processDue() {
    if (!workspace) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.post<LeadCadenceProcessResult>(
        `/workspaces/${workspace.public_id}/lead-cadences/process-due`,
      );
      setToast(
        `${result.activities_created} atividade(s) criada(s); ${result.completed} cadência(s) concluída(s).`,
      );
      await load();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Falha ao processar pendências.");
    } finally {
      setSaving(false);
    }
  }

  async function cancelEnrollment(publicId: string) {
    if (!workspace) return;
    await api.post(
      `/workspaces/${workspace.public_id}/lead-cadence-enrollments/${publicId}/cancel`,
    );
    setToast("Cadência do lead cancelada.");
    await load();
  }

  const activeEnrollments = enrollments.filter((item) => item.status === "active");

  return (
    <div className="page-stack cadence-page">
      <div className="page-heading-row">
        <div>
          <span className="eyebrow">Sprint 5 · Automação comercial</span>
          <h1>Cadências e follow-ups</h1>
          <p>Organize sequências automáticas de atividades para nenhum lead ficar sem próximo passo.</p>
        </div>
        <div className="page-actions">
          <Button variant="secondary" onClick={() => void load()} disabled={loading}>
            <RefreshCw size={16} /> Atualizar
          </Button>
          {canConfigure && (
            <Button onClick={() => setShowCreate((value) => !value)}>
              {showCreate ? <X size={16} /> : <Plus size={16} />}
              {showCreate ? "Fechar" : "Nova cadência"}
            </Button>
          )}
        </div>
      </div>

      {error && <div className="form-alert form-alert--error">{error}</div>}
      {toast && <div className="form-alert form-alert--success">{toast}</div>}

      <div className="metric-grid metric-grid--compact">
        <Card><div className="metric-inline"><Workflow size={18} /><div><span>Cadências</span><strong>{cadences.length}</strong></div></div></Card>
        <Card><div className="metric-inline"><Play size={18} /><div><span>Leads ativos</span><strong>{activeEnrollments.length}</strong></div></div></Card>
        <Card><div className="metric-inline"><CheckCircle2 size={18} /><div><span>Concluídas</span><strong>{enrollments.filter((item) => item.status === "completed").length}</strong></div></div></Card>
      </div>

      {showCreate && canConfigure && (
        <Card>
          <div className="section-heading"><div><h2>Nova cadência</h2><p>O atraso de cada etapa começa a contar depois da etapa anterior.</p></div></div>
          <div className="form-grid form-grid--two">
            <label><span>Nome</span><input value={name} onChange={(event) => setName(event.target.value)} placeholder="Ex.: Lead novo · 3 dias" /></label>
            <label><span>Descrição</span><input value={description} onChange={(event) => setDescription(event.target.value)} placeholder="Objetivo da sequência" /></label>
          </div>
          <div className="cadence-builder">
            {steps.map((step, index) => (
              <div className="cadence-step-editor" key={`${index}-${step.action_type}`}>
                <span className="cadence-step-index">{index + 1}</span>
                <label><span>Aguardar (min)</span><input type="number" min="0" value={step.delay_minutes} onChange={(event) => updateStep(index, { delay_minutes: Math.max(0, Number(event.target.value) || 0) })} /></label>
                <label><span>Ação</span><select value={step.action_type} onChange={(event) => updateStep(index, { action_type: event.target.value as DraftStep["action_type"] })}><option value="follow_up">Follow-up</option><option value="whatsapp">WhatsApp</option><option value="call">Ligação</option><option value="email">E-mail</option><option value="task">Tarefa</option></select></label>
                <label className="cadence-step-title"><span>Título</span><input value={step.title} onChange={(event) => updateStep(index, { title: event.target.value })} /></label>
                <Button variant="ghost" onClick={() => setSteps((current) => current.filter((_, position) => position !== index))} disabled={steps.length === 1}><X size={15} /></Button>
              </div>
            ))}
          </div>
          <div className="page-actions">
            <Button variant="secondary" onClick={() => setSteps((current) => [...current, newStep()])}><Plus size={16} /> Adicionar etapa</Button>
            <Button onClick={() => void createCadence()} disabled={saving || !name.trim()}>Salvar cadência</Button>
          </div>
        </Card>
      )}

      <div className="content-grid content-grid--two">
        <Card>
          <div className="section-heading"><div><h2>Cadências disponíveis</h2><p>Sequências prontas para uso.</p></div></div>
          <div className="cadence-list">
            {cadences.map((cadence) => (
              <div className="cadence-card" key={cadence.public_id}>
                <div className="cadence-card__header"><div><strong>{cadence.name}</strong><span>{cadence.description ?? "Sem descrição"}</span></div><Badge tone={cadence.active ? "success" : "neutral"}>{cadence.active ? "Ativa" : "Inativa"}</Badge></div>
                <div className="cadence-timeline">
                  {(cadence.steps ?? []).map((step) => <span key={step.position}><b>{step.position}</b>{actionLabels[step.action_type] ?? step.action_type} · {delayLabel(Number(step.delay_minutes) || 0)}</span>)}
                </div>
                <small>{cadence.active_enrollments} lead(s) ativo(s) · pausa automática em resposta: {cadence.stop_on_reply ? "sim" : "não"}</small>
              </div>
            ))}
            {!cadences.length && <div className="empty-state">Nenhuma cadência criada ainda.</div>}
          </div>
        </Card>

        <Card>
          <div className="section-heading"><div><h2>Incluir lead</h2><p>Escolha o lead e a sequência.</p></div></div>
          <div className="form-stack">
            <label><span>Lead</span><select value={selectedLead} onChange={(event) => setSelectedLead(event.target.value)}><option value="">Selecione</option>{leads.map((lead) => <option key={lead.public_id} value={lead.public_id}>{lead.name} · {lead.interest ?? "Sem interesse"}</option>)}</select></label>
            <label><span>Cadência</span><select value={selectedCadence} onChange={(event) => setSelectedCadence(event.target.value)}><option value="">Selecione</option>{cadences.filter((item) => item.active).map((cadence) => <option key={cadence.public_id} value={cadence.public_id}>{cadence.name}</option>)}</select></label>
            <Button onClick={() => void enrollLead()} disabled={saving || !selectedLead || !selectedCadence}><Play size={16} /> Iniciar cadência</Button>
          </div>
          <div className="cadence-process-box">
            <CalendarClock size={20} />
            <div><strong>Processar etapas vencidas</strong><span>Cria as atividades que já chegaram ao horário programado.</span></div>
            <Button variant="secondary" onClick={() => void processDue()} disabled={saving}>Executar agora</Button>
          </div>
        </Card>
      </div>

      <Card>
        <div className="section-heading"><div><h2>Leads em cadência</h2><p>Acompanhe o próximo passo e o progresso de cada lead.</p></div></div>
        <div className="table-wrap"><table className="data-table"><thead><tr><th>Lead</th><th>Cadência</th><th>Progresso</th><th>Próxima execução</th><th>Status</th><th /></tr></thead><tbody>{enrollments.map((item) => <tr key={item.public_id}><td><strong>{item.lead_name}</strong><span>{item.lead_public_id}</span></td><td>{item.cadence_name}</td><td>{Math.min(item.current_step, item.total_steps)}/{item.total_steps}</td><td>{formatWhen(item.next_run_at)}</td><td><Badge tone={item.status === "active" ? "info" : item.status === "completed" ? "success" : "neutral"}>{item.status === "active" ? "Ativa" : item.status === "completed" ? "Concluída" : "Cancelada"}</Badge></td><td>{item.status === "active" && <Button variant="ghost" onClick={() => void cancelEnrollment(item.public_id)}><CirclePause size={15} /> Pausar</Button>}</td></tr>)}</tbody></table></div>
      </Card>
    </div>
  );
}

import { Loader2, Save, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type { CommunicationPolicy } from "../types/communication";

const defaultPolicy: CommunicationPolicy = {
  enforce_whatsapp_opt_in: true,
  enforce_email_opt_in: true,
  enforce_sms_opt_in: true,
  enforce_phone_opt_in: false,
  allow_legacy_lead_consent: true,
  stop_cadence_on_block: true,
  updated_at: null,
};

const channelOptions: Array<{
  key: keyof Pick<
    CommunicationPolicy,
    | "enforce_whatsapp_opt_in"
    | "enforce_email_opt_in"
    | "enforce_sms_opt_in"
    | "enforce_phone_opt_in"
  >;
  title: string;
  description: string;
}> = [
  {
    key: "enforce_whatsapp_opt_in",
    title: "WhatsApp",
    description: "Bloqueia novas mensagens quando não houver autorização válida.",
  },
  {
    key: "enforce_email_opt_in",
    title: "E-mail",
    description: "Exige autorização antes de ações comerciais por e-mail.",
  },
  {
    key: "enforce_sms_opt_in",
    title: "SMS",
    description: "Mantém o canal preparado para automações futuras com opt-in.",
  },
  {
    key: "enforce_phone_opt_in",
    title: "Ligação",
    description: "Quando ativo, chamadas em cadências também exigem autorização.",
  },
];

export function CommunicationPage() {
  const { workspace } = useWorkspace();
  const [policy, setPolicy] = useState<CommunicationPolicy>(defaultPolicy);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!workspace) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<CommunicationPolicy>(
        `/workspaces/${workspace.public_id}/communication-policy`,
      );
      setPolicy(result);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a política de comunicação.",
      );
    } finally {
      setLoading(false);
    }
  }, [workspace]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function savePolicy() {
    if (!workspace) return;
    setSaving(true);
    setError(null);
    try {
      const result = await api.put<CommunicationPolicy>(
        `/workspaces/${workspace.public_id}/communication-policy`,
        {
          enforce_whatsapp_opt_in: policy.enforce_whatsapp_opt_in,
          enforce_email_opt_in: policy.enforce_email_opt_in,
          enforce_sms_opt_in: policy.enforce_sms_opt_in,
          enforce_phone_opt_in: policy.enforce_phone_opt_in,
          allow_legacy_lead_consent: policy.allow_legacy_lead_consent,
          stop_cadence_on_block: policy.stop_cadence_on_block,
        },
      );
      setPolicy(result);
      setToast("Política de comunicação atualizada.");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível salvar a política.",
      );
    } finally {
      setSaving(false);
    }
  }

  if (!workspace) {
    return <div className="empty-state">Selecione uma empresa.</div>;
  }

  return (
    <div className="page-stack communication-page">
      <header className="page-header">
        <div>
          <span className="eyebrow">Sprint 5 · Etapa 4</span>
          <h1>Políticas de comunicação</h1>
          <p>
            Controle opt-in, opt-out e as regras que protegem WhatsApp, e-mail,
            SMS e cadências comerciais.
          </p>
        </div>
        <Button onClick={() => void savePolicy()} disabled={saving || loading}>
          {saving ? <Loader2 size={16} className="spin" /> : <Save size={16} />}
          Salvar política
        </Button>
      </header>

      {error && <div className="page-alert page-alert--error">{error}</div>}

      <Card
        title="Canais protegidos"
        description="Quando um canal exige opt-in, o Nexyra verifica a autorização antes de permitir uma nova comunicação."
      >
        {loading ? (
          <div className="table-loading">
            <Loader2 size={18} className="spin" />
            <span>Carregando política...</span>
          </div>
        ) : (
          <div className="communication-policy-grid">
            {channelOptions.map((item) => (
              <label className="communication-policy-card" key={item.key}>
                <span>
                  <strong>{item.title}</strong>
                  <small>{item.description}</small>
                </span>
                <input
                  type="checkbox"
                  checked={Boolean(policy[item.key])}
                  onChange={(event) =>
                    setPolicy((current) => ({
                      ...current,
                      [item.key]: event.target.checked,
                    }))
                  }
                />
              </label>
            ))}
          </div>
        )}
      </Card>

      <Card
        title="Compatibilidade e cadências"
        description="Regras para a transição dos leads antigos e para automações comerciais."
      >
        <div className="communication-rule-list">
          <label>
            <input
              type="checkbox"
              checked={policy.allow_legacy_lead_consent}
              onChange={(event) =>
                setPolicy((current) => ({
                  ...current,
                  allow_legacy_lead_consent: event.target.checked,
                }))
              }
            />
            <span>
              <strong>Aceitar o consentimento legado dos leads existentes</strong>
              <small>
                Mantém compatibilidade com o campo de consentimento já usado no CRM.
                Um opt-out explícito sempre tem prioridade sobre esse legado.
              </small>
            </span>
          </label>
          <label>
            <input
              type="checkbox"
              checked={policy.stop_cadence_on_block}
              onChange={(event) =>
                setPolicy((current) => ({
                  ...current,
                  stop_cadence_on_block: event.target.checked,
                }))
              }
            />
            <span>
              <strong>Interromper cadência quando um canal estiver bloqueado</strong>
              <small>
                Evita que uma sequência continue tentando contato depois de um opt-out.
              </small>
            </span>
          </label>
        </div>
      </Card>

      <div className="communication-info-panel">
        <ShieldCheck size={20} />
        <div>
          <strong>Opt-out explícito vence qualquer autorização anterior.</strong>
          <span>
            O bloqueio é aplicado no backend, inclusive em previews e envios do
            WhatsApp, não apenas na interface.
          </span>
        </div>
      </div>

      {toast && <div className="toast toast--success">{toast}</div>}
    </div>
  );
}

import { Ban, Loader2, RotateCcw, Save, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type {
  ConsentStatus,
  LawfulBasis,
  LeadCommunicationSummary,
  LeadConsentPayload,
} from "../../types/communication";
import type { Lead } from "../../types/leads";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

const channelLabels = {
  whatsapp: "WhatsApp",
  email: "E-mail",
  sms: "SMS",
  phone: "Ligação",
} as const;

const basisLabels: Record<LawfulBasis, string> = {
  consent: "Consentimento",
  contract: "Contrato",
  legitimate_interest: "Legítimo interesse",
  customer_request: "Solicitação do cliente",
  other: "Outro",
};

const statusLabels: Record<ConsentStatus, string> = {
  granted: "Autorizado",
  denied: "Negado",
  revoked: "Opt-out",
  unknown: "Não registrado",
};

type Draft = {
  status: ConsentStatus;
  lawful_basis: LawfulBasis | "";
  source: string;
  evidence: string;
  note: string;
};

type Props = {
  open: boolean;
  workspacePublicId: string;
  lead: Lead | null;
  onClose: () => void;
  onChanged: () => void;
};

export function LeadConsentModal({
  open,
  workspacePublicId,
  lead,
  onClose,
  onChanged,
}: Props) {
  const [summary, setSummary] = useState<LeadCommunicationSummary | null>(null);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [loading, setLoading] = useState(false);
  const [savingChannel, setSavingChannel] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const endpoint = useMemo(() => {
    if (!lead) return null;
    return `/workspaces/${workspacePublicId}/leads/${lead.public_id}`;
  }, [lead, workspacePublicId]);

  const hydrate = useCallback((result: LeadCommunicationSummary) => {
    setSummary(result);
    setDrafts(
      Object.fromEntries(
        result.items.map((item) => [
          item.channel,
          {
            status: item.status,
            lawful_basis: item.lawful_basis ?? "",
            source: item.source ?? "manual",
            evidence: item.evidence ?? "",
            note: item.note ?? "",
          } satisfies Draft,
        ]),
      ),
    );
  }, []);

  const load = useCallback(async () => {
    if (!open || !endpoint) return;
    setLoading(true);
    setError(null);
    try {
      const result = await api.get<LeadCommunicationSummary>(
        `${endpoint}/communication-consents`,
      );
      hydrate(result);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar os consentimentos.",
      );
    } finally {
      setLoading(false);
    }
  }, [endpoint, hydrate, open]);

  useEffect(() => {
    void load();
  }, [load]);

  function updateDraft(channel: string, patch: Partial<Draft>) {
    setDrafts((current) => ({
      ...current,
      [channel]: { ...current[channel], ...patch },
    }));
  }

  async function saveChannel(channel: string) {
    if (!endpoint) return;
    const draft = drafts[channel];
    if (!draft) return;
    setSavingChannel(channel);
    setError(null);
    try {
      const payload: LeadConsentPayload = {
        channel: channel as LeadConsentPayload["channel"],
        status: draft.status,
        lawful_basis: draft.lawful_basis || null,
        source: draft.source || "manual",
        evidence: draft.evidence || null,
        note: draft.note || null,
      };
      const result = await api.put<LeadCommunicationSummary>(
        `${endpoint}/communication-consents`,
        payload,
      );
      hydrate(result);
      onChanged();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível salvar o consentimento.",
      );
    } finally {
      setSavingChannel(null);
    }
  }

  async function setGlobalOptOut(enabled: boolean) {
    if (!endpoint) return;
    setSavingChannel("all");
    setError(null);
    try {
      const result = enabled
        ? await api.post<LeadCommunicationSummary>(
            `${endpoint}/communication-opt-out`,
            {
              channel: "all",
              source: "manual",
              reason: "Opt-out global registrado no Nexyra CRM.",
            },
          )
        : await api.put<LeadCommunicationSummary>(
            `${endpoint}/communication-consents`,
            {
              channel: "all",
              status: "unknown",
              source: "manual",
              note: "Bloqueio global removido manualmente.",
            },
          );
      hydrate(result);
      onChanged();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível atualizar o opt-out global.",
      );
    } finally {
      setSavingChannel(null);
    }
  }

  return (
    <Modal
      open={open}
      title={`Consentimentos · ${lead?.name ?? "Lead"}`}
      description="Autorizações por canal, opt-out e base de registro."
      onClose={onClose}
      size="lg"
    >
      {loading ? (
        <div className="table-loading">
          <Loader2 size={18} className="spin" />
          <span>Carregando consentimentos...</span>
        </div>
      ) : summary ? (
        <div className="consent-modal-stack">
          <div
            className={`consent-global ${summary.global_opt_out ? "consent-global--blocked" : ""}`}
          >
            <div>
              {summary.global_opt_out ? <Ban size={19} /> : <ShieldCheck size={19} />}
              <span>
                <strong>
                  {summary.global_opt_out
                    ? "Opt-out global ativo"
                    : "Sem bloqueio global"}
                </strong>
                <small>
                  {summary.global_opt_out
                    ? "Nenhum canal comercial pode ignorar este bloqueio."
                    : summary.legacy_consent
                      ? "O lead ainda possui consentimento legado válido como fallback."
                      : "As permissões são avaliadas individualmente por canal."}
                </small>
              </span>
            </div>
            <Button
              variant={summary.global_opt_out ? "secondary" : "danger"}
              disabled={savingChannel !== null}
              onClick={() => void setGlobalOptOut(!summary.global_opt_out)}
            >
              {savingChannel === "all" ? (
                <Loader2 size={15} className="spin" />
              ) : summary.global_opt_out ? (
                <RotateCcw size={15} />
              ) : (
                <Ban size={15} />
              )}
              {summary.global_opt_out ? "Remover bloqueio" : "Opt-out global"}
            </Button>
          </div>

          <div className="consent-channel-grid">
            {summary.items.map((item) => {
              const draft = drafts[item.channel];
              if (!draft) return null;
              return (
                <section className="consent-channel-card" key={item.channel}>
                  <header>
                    <div>
                      <strong>{channelLabels[item.channel]}</strong>
                      <small>{item.effective_reason}</small>
                    </div>
                    <Badge tone={item.allowed ? "success" : "danger"}>
                      {item.allowed ? "Permitido" : "Bloqueado"}
                    </Badge>
                  </header>

                  <label className="field">
                    <span>Status explícito</span>
                    <select
                      value={draft.status}
                      onChange={(event) =>
                        updateDraft(item.channel, {
                          status: event.target.value as ConsentStatus,
                        })
                      }
                    >
                      {Object.entries(statusLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="field">
                    <span>Base / motivo</span>
                    <select
                      value={draft.lawful_basis}
                      onChange={(event) =>
                        updateDraft(item.channel, {
                          lawful_basis: event.target.value as LawfulBasis | "",
                        })
                      }
                    >
                      <option value="">Não informada</option>
                      {Object.entries(basisLabels).map(([value, label]) => (
                        <option key={value} value={value}>
                          {label}
                        </option>
                      ))}
                    </select>
                  </label>

                  <label className="field">
                    <span>Origem do registro</span>
                    <input
                      value={draft.source}
                      maxLength={80}
                      onChange={(event) =>
                        updateDraft(item.channel, { source: event.target.value })
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Evidência / referência</span>
                    <input
                      value={draft.evidence}
                      maxLength={2000}
                      placeholder="Ex.: formulário, atendimento, protocolo..."
                      onChange={(event) =>
                        updateDraft(item.channel, { evidence: event.target.value })
                      }
                    />
                  </label>

                  <label className="field">
                    <span>Observação</span>
                    <textarea
                      value={draft.note}
                      maxLength={1000}
                      rows={2}
                      onChange={(event) =>
                        updateDraft(item.channel, { note: event.target.value })
                      }
                    />
                  </label>

                  <Button
                    variant="secondary"
                    disabled={savingChannel !== null}
                    onClick={() => void saveChannel(item.channel)}
                  >
                    {savingChannel === item.channel ? (
                      <Loader2 size={15} className="spin" />
                    ) : (
                      <Save size={15} />
                    )}
                    Salvar canal
                  </Button>
                </section>
              );
            })}
          </div>
        </div>
      ) : null}

      {error && <div className="page-alert page-alert--error">{error}</div>}
    </Modal>
  );
}

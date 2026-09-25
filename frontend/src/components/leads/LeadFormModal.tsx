import { useEffect, useMemo, useState } from "react";

import type {
  Lead,
  LeadPayload,
  WorkspaceMember,
  WorkspaceSegmentConfig,
} from "../../types/leads";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

const sourceOptions = [
  "manual",
  "instagram",
  "facebook",
  "google_ads",
  "site",
  "whatsapp",
  "indicacao",
  "marketplace",
];

const channelOptions = [
  "crm",
  "lead_ads",
  "direct",
  "web",
  "whatsapp",
  "formulario",
  "api",
  "importacao",
];

type FormState = {
  name: string;
  phone: string;
  email: string;
  external_id: string;
  interest: string;
  source: string;
  channel: string;
  campaign: string;
  message: string;
  status: string;
  priority: string;
  owner_user_public_id: string;
  consent: boolean;
  custom_fields: Record<string, string>;
};

type LeadFormModalProps = {
  open: boolean;
  mode: "create" | "edit" | "intake";
  lead: Lead | null;
  members: WorkspaceMember[];
  segmentConfig: WorkspaceSegmentConfig | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: LeadPayload) => Promise<void>;
};

function emptyState(
  mode: LeadFormModalProps["mode"],
  segmentConfig: WorkspaceSegmentConfig | null,
): FormState {
  return {
    name: "",
    phone: "",
    email: "",
    external_id: "",
    interest: "",
    source: mode === "intake" ? "instagram" : "manual",
    channel: mode === "intake" ? "lead_ads" : "crm",
    campaign: "",
    message: "",
    status: segmentConfig?.pipeline[0] ?? "novo",
    priority: "media",
    owner_user_public_id: "",
    consent: true,
    custom_fields: Object.fromEntries(
      (segmentConfig?.custom_fields ?? []).map((field) => [field, ""]),
    ),
  };
}

function fromLead(
  lead: Lead,
  segmentConfig: WorkspaceSegmentConfig | null,
): FormState {
  return {
    name: lead.name,
    phone: lead.phone ?? "",
    email: lead.email ?? "",
    external_id: lead.external_id ?? "",
    interest: lead.interest ?? "",
    source: lead.source,
    channel: lead.channel,
    campaign: lead.campaign ?? "",
    message: lead.message ?? "",
    status: lead.status,
    priority: lead.priority,
    owner_user_public_id: lead.owner_user_public_id ?? "",
    consent: lead.consent,
    custom_fields: Object.fromEntries(
      (segmentConfig?.custom_fields ?? []).map((field) => [
        field,
        String(lead.custom_fields[field] ?? ""),
      ]),
    ),
  };
}

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\w/g, (letter) => letter.toUpperCase());
}

export function LeadFormModal({
  open,
  mode,
  lead,
  members,
  segmentConfig,
  saving,
  error,
  onClose,
  onSubmit,
}: LeadFormModalProps) {
  const initial = useMemo(
    () =>
      mode === "edit" && lead
        ? fromLead(lead, segmentConfig)
        : emptyState(mode, segmentConfig),
    [lead, mode, segmentConfig],
  );
  const [form, setForm] = useState<FormState>(initial);

  useEffect(() => {
    if (open) {
      setForm(initial);
    }
  }, [initial, open]);

  const title =
    mode === "edit"
      ? "Editar lead"
      : mode === "intake"
        ? "Registrar entrada de lead"
        : "Novo lead";

  const description =
    mode === "intake"
      ? "Use o intake para registrar origens externas e atualizar duplicados automaticamente."
      : mode === "edit"
        ? "Atualize os dados comerciais e o responsável pelo lead."
        : "Cadastre um novo lead diretamente no CRM.";

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const customFields = Object.fromEntries(
      Object.entries(form.custom_fields).filter(([, value]) => value !== ""),
    );

    await onSubmit({
      name: form.name.trim(),
      phone: form.phone.trim() || null,
      email: form.email.trim() || null,
      external_id: form.external_id.trim() || null,
      interest: form.interest.trim() || null,
      source: form.source.trim(),
      channel: form.channel.trim(),
      campaign: form.campaign.trim() || null,
      message: form.message.trim() || null,
      status: form.status || null,
      priority: form.priority,
      custom_fields: customFields,
      owner_user_public_id: form.owner_user_public_id || null,
      consent: form.consent,
    });
  }

  return (
    <Modal
      open={open}
      title={title}
      description={description}
      onClose={onClose}
      size="lg"
    >
      <form className="lead-form" onSubmit={handleSubmit}>
        {error && <div className="form-alert form-alert--error">{error}</div>}

        <div className="form-section">
          <div className="form-section__heading">
            <strong>Dados principais</strong>
            <span>Identificação e contato do lead</span>
          </div>
          <div className="form-grid form-grid--2">
            <label className="field field--full">
              <span>Nome *</span>
              <input
                required
                minLength={2}
                value={form.name}
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="Nome do lead"
              />
            </label>
            <label className="field">
              <span>Telefone</span>
              <input
                value={form.phone}
                onChange={(event) =>
                  setForm((current) => ({ ...current, phone: event.target.value }))
                }
                placeholder="(92) 99999-9999"
              />
            </label>
            <label className="field">
              <span>E-mail</span>
              <input
                type="email"
                value={form.email}
                onChange={(event) =>
                  setForm((current) => ({ ...current, email: event.target.value }))
                }
                placeholder="cliente@empresa.com"
              />
            </label>
            <label className="field">
              <span>{segmentConfig?.interest_label ?? "Interesse"}</span>
              <input
                value={form.interest}
                onChange={(event) =>
                  setForm((current) => ({ ...current, interest: event.target.value }))
                }
                placeholder="Produto, curso ou serviço"
              />
            </label>
            <label className="field">
              <span>Identificador externo</span>
              <input
                value={form.external_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    external_id: event.target.value,
                  }))
                }
                placeholder="ID da Meta, formulário ou sistema externo"
              />
            </label>
          </div>
        </div>

        <div className="form-section">
          <div className="form-section__heading">
            <strong>Origem comercial</strong>
            <span>Rastreie canal, campanha e fonte de aquisição</span>
          </div>
          <div className="form-grid form-grid--3">
            <label className="field">
              <span>Origem *</span>
              <input
                required
                list="lead-source-options"
                value={form.source}
                onChange={(event) =>
                  setForm((current) => ({ ...current, source: event.target.value }))
                }
              />
              <datalist id="lead-source-options">
                {sourceOptions.map((source) => (
                  <option key={source} value={source} />
                ))}
              </datalist>
            </label>
            <label className="field">
              <span>Canal *</span>
              <input
                required
                list="lead-channel-options"
                value={form.channel}
                onChange={(event) =>
                  setForm((current) => ({ ...current, channel: event.target.value }))
                }
              />
              <datalist id="lead-channel-options">
                {channelOptions.map((channel) => (
                  <option key={channel} value={channel} />
                ))}
              </datalist>
            </label>
            <label className="field">
              <span>Campanha</span>
              <input
                value={form.campaign}
                onChange={(event) =>
                  setForm((current) => ({ ...current, campaign: event.target.value }))
                }
                placeholder="Campanha de aquisição"
              />
            </label>
          </div>
        </div>

        <div className="form-section">
          <div className="form-section__heading">
            <strong>Gestão do lead</strong>
            <span>Pipeline, prioridade e responsável</span>
          </div>
          <div className="form-grid form-grid--3">
            <label className="field">
              <span>Status</span>
              <select
                value={form.status}
                onChange={(event) =>
                  setForm((current) => ({ ...current, status: event.target.value }))
                }
              >
                {(segmentConfig?.pipeline ?? ["novo"]).map((stage) => (
                  <option key={stage} value={stage}>
                    {labelize(stage)}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span>Prioridade</span>
              <select
                value={form.priority}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    priority: event.target.value,
                  }))
                }
              >
                <option value="baixa">Baixa</option>
                <option value="media">Média</option>
                <option value="alta">Alta</option>
                <option value="urgente">Urgente</option>
              </select>
            </label>
            <label className="field">
              <span>Responsável</span>
              <select
                value={form.owner_user_public_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    owner_user_public_id: event.target.value,
                  }))
                }
              >
                <option value="">Sem responsável</option>
                {members.map((member) => (
                  <option key={member.public_id} value={member.public_id}>
                    {member.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
        </div>

        {(segmentConfig?.custom_fields.length ?? 0) > 0 && (
          <div className="form-section">
            <div className="form-section__heading">
              <strong>Campos do segmento</strong>
              <span>Campos configurados para esta empresa</span>
            </div>
            <div className="form-grid form-grid--2">
              {segmentConfig?.custom_fields.map((field) => (
                <label className="field" key={field}>
                  <span>{labelize(field)}</span>
                  <input
                    value={form.custom_fields[field] ?? ""}
                    onChange={(event) =>
                      setForm((current) => ({
                        ...current,
                        custom_fields: {
                          ...current.custom_fields,
                          [field]: event.target.value,
                        },
                      }))
                    }
                  />
                </label>
              ))}
            </div>
          </div>
        )}

        <div className="form-section">
          <div className="form-grid">
            <label className="field">
              <span>Observação / mensagem</span>
              <textarea
                rows={4}
                value={form.message}
                onChange={(event) =>
                  setForm((current) => ({ ...current, message: event.target.value }))
                }
                placeholder="Contexto recebido do lead ou observação comercial"
              />
            </label>
            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={form.consent}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    consent: event.target.checked,
                  }))
                }
              />
              <span>
                <strong>Consentimento registrado</strong>
                <small>Indica que o contato pode ser tratado conforme a política da empresa.</small>
              </span>
            </label>
          </div>
        </div>

        <div className="lead-form__actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving || !form.name.trim()}>
            {saving
              ? "Salvando..."
              : mode === "edit"
                ? "Salvar alterações"
                : mode === "intake"
                  ? "Registrar entrada"
                  : "Criar lead"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

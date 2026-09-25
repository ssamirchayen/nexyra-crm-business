import { useEffect, useMemo, useState } from "react";

import type {
  ActivityCard,
  ActivityMetadata,
  ActivityPayload,
  ActivityType,
  ActivityUpdatePayload,
} from "../../types/activities";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

const activityTypes: Array<{ value: ActivityType; label: string }> = [
  { value: "call", label: "Ligação" },
  { value: "whatsapp", label: "WhatsApp" },
  { value: "email", label: "E-mail" },
  { value: "meeting", label: "Reunião" },
  { value: "task", label: "Tarefa" },
  { value: "follow_up", label: "Follow-up" },
  { value: "note", label: "Nota" },
];

type FormState = {
  activity_type: ActivityType;
  title: string;
  description: string;
  lead_public_id: string;
  opportunity_public_id: string;
  owner_user_public_id: string;
  due_at: string;
};

type Props = {
  open: boolean;
  mode: "create" | "edit";
  activity: ActivityCard | null;
  metadata: ActivityMetadata;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (payload: ActivityPayload | ActivityUpdatePayload) => Promise<void>;
};

function toLocalInput(value: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

function initialState(mode: Props["mode"], activity: ActivityCard | null): FormState {
  if (mode === "edit" && activity) {
    return {
      activity_type: activity.activity_type,
      title: activity.title,
      description: activity.description ?? "",
      lead_public_id: activity.lead_public_id ?? "",
      opportunity_public_id: activity.opportunity_public_id ?? "",
      owner_user_public_id: activity.owner_user_public_id ?? "",
      due_at: toLocalInput(activity.due_at),
    };
  }

  return {
    activity_type: "follow_up",
    title: "",
    description: "",
    lead_public_id: "",
    opportunity_public_id: "",
    owner_user_public_id: "",
    due_at: "",
  };
}

export function ActivityFormModal({
  open,
  mode,
  activity,
  metadata,
  saving,
  error,
  onClose,
  onSubmit,
}: Props) {
  const initial = useMemo(() => initialState(mode, activity), [activity, mode]);
  const [form, setForm] = useState<FormState>(initial);

  useEffect(() => {
    if (open) setForm(initial);
  }, [initial, open]);

  const activeMembers = useMemo(
    () => metadata.members.filter((item) => item.user_active && item.membership_active),
    [metadata.members],
  );

  const filteredOpportunities = useMemo(() => {
    if (!form.lead_public_id) return metadata.opportunities;
    return metadata.opportunities.filter(
      (item) => item.lead_public_id === form.lead_public_id,
    );
  }, [form.lead_public_id, metadata.opportunities]);

  function setField<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const dueAt = form.due_at ? new Date(form.due_at).toISOString() : null;

    if (mode === "edit") {
      await onSubmit({
        activity_type: form.activity_type,
        title: form.title.trim(),
        description: form.description.trim() || null,
        owner_user_public_id: form.owner_user_public_id || null,
        due_at: dueAt,
      });
      return;
    }

    await onSubmit({
      activity_type: form.activity_type,
      title: form.title.trim(),
      description: form.description.trim() || null,
      lead_public_id: form.lead_public_id || null,
      opportunity_public_id: form.opportunity_public_id || null,
      owner_user_public_id: form.owner_user_public_id || null,
      due_at: dueAt,
    });
  }

  return (
    <Modal
      open={open}
      title={mode === "edit" ? "Editar atividade" : "Nova atividade"}
      description={
        mode === "edit"
          ? "Atualize o compromisso comercial enquanto ele estiver pendente."
          : "Registre um contato, tarefa, reunião ou follow-up."
      }
      onClose={onClose}
      size="lg"
    >
      <form className="lead-form" onSubmit={handleSubmit}>
        {error && <div className="form-alert form-alert--error">{error}</div>}

        <div className="form-section">
          <div className="form-section__heading">
            <strong>Atividade</strong>
            <span>Defina o tipo, assunto e instruções para o responsável.</span>
          </div>
          <div className="form-grid form-grid--2">
            <label className="field">
              <span>Tipo *</span>
              <select
                required
                value={form.activity_type}
                onChange={(event) =>
                  setField("activity_type", event.target.value as ActivityType)
                }
              >
                {activityTypes.map((item) => (
                  <option key={item.value} value={item.value}>
                    {item.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Data e hora</span>
              <input
                type="datetime-local"
                value={form.due_at}
                onChange={(event) => setField("due_at", event.target.value)}
              />
            </label>

            <label className="field field--full">
              <span>Título *</span>
              <input
                required
                minLength={2}
                maxLength={200}
                value={form.title}
                onChange={(event) => setField("title", event.target.value)}
                placeholder="Ex.: Retornar proposta de matrícula"
              />
            </label>

            <label className="field field--full">
              <span>Descrição</span>
              <textarea
                rows={4}
                value={form.description}
                onChange={(event) => setField("description", event.target.value)}
                placeholder="Inclua observações ou informações importantes para o atendimento."
              />
            </label>
          </div>
        </div>

        <div className="form-section">
          <div className="form-section__heading">
            <strong>Relacionamento e responsável</strong>
            <span>Vincule a atividade ao contexto comercial correto.</span>
          </div>
          <div className="form-grid form-grid--3">
            <label className="field">
              <span>Lead</span>
              <select
                disabled={mode === "edit"}
                value={form.lead_public_id}
                onChange={(event) => {
                  setField("lead_public_id", event.target.value);
                  setField("opportunity_public_id", "");
                }}
              >
                <option value="">Atividade interna</option>
                {metadata.leads.map((lead) => (
                  <option key={lead.public_id} value={lead.public_id}>
                    {lead.name}{lead.interest ? ` — ${lead.interest}` : ""}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Oportunidade</span>
              <select
                disabled={mode === "edit"}
                value={form.opportunity_public_id}
                onChange={(event) => {
                  const opportunity = metadata.opportunities.find(
                    (item) => item.public_id === event.target.value,
                  );
                  setForm((current) => ({
                    ...current,
                    opportunity_public_id: event.target.value,
                    lead_public_id:
                      opportunity?.lead_public_id ?? current.lead_public_id,
                  }));
                }}
              >
                <option value="">Sem oportunidade</option>
                {filteredOpportunities.map((item) => (
                  <option key={item.public_id} value={item.public_id}>
                    {item.title} — {item.lead_name}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Responsável</span>
              <select
                value={form.owner_user_public_id}
                onChange={(event) =>
                  setField("owner_user_public_id", event.target.value)
                }
              >
                <option value="">Sem responsável</option>
                {activeMembers.map((member) => (
                  <option key={member.public_id} value={member.public_id}>
                    {member.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          {mode === "edit" && (
            <p className="form-helper">
              O vínculo com lead e oportunidade não muda após a criação, preservando o histórico comercial.
            </p>
          )}
        </div>

        <div className="lead-form__actions">
          <Button type="button" variant="secondary" disabled={saving} onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving || !form.title.trim()}>
            {saving ? "Salvando..." : mode === "edit" ? "Salvar alterações" : "Criar atividade"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

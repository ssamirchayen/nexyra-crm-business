import { useEffect, useMemo, useState } from "react";

import type { Lead, WorkspaceMember, WorkspaceSegmentConfig } from "../../types/leads";
import type {
  OpportunityCard,
  OpportunityPayload,
  OpportunityUpdatePayload,
} from "../../types/opportunities";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

type OpportunityFormModalProps = {
  open: boolean;
  mode: "create" | "edit";
  opportunity: OpportunityCard | null;
  leads: Lead[];
  members: WorkspaceMember[];
  segmentConfig: WorkspaceSegmentConfig | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onSubmit: (
    payload: OpportunityPayload | OpportunityUpdatePayload,
  ) => Promise<void>;
};

type FormState = {
  lead_public_id: string;
  title: string;
  value_amount: string;
  currency: string;
  stage: string;
  owner_user_public_id: string;
  expected_close_date: string;
};

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function initialState(
  mode: OpportunityFormModalProps["mode"],
  opportunity: OpportunityCard | null,
  segmentConfig: WorkspaceSegmentConfig | null,
): FormState {
  if (mode === "edit" && opportunity) {
    return {
      lead_public_id: opportunity.lead_public_id,
      title: opportunity.title,
      value_amount: opportunity.value_amount,
      currency: opportunity.currency,
      stage: opportunity.stage,
      owner_user_public_id: opportunity.owner_user_public_id ?? "",
      expected_close_date: opportunity.expected_close_date ?? "",
    };
  }

  return {
    lead_public_id: "",
    title: "",
    value_amount: "0.00",
    currency: "BRL",
    stage: segmentConfig?.pipeline[0] ?? "novo",
    owner_user_public_id: "",
    expected_close_date: "",
  };
}

export function OpportunityFormModal({
  open,
  mode,
  opportunity,
  leads,
  members,
  segmentConfig,
  saving,
  error,
  onClose,
  onSubmit,
}: OpportunityFormModalProps) {
  const initial = useMemo(
    () => initialState(mode, opportunity, segmentConfig),
    [mode, opportunity, segmentConfig],
  );
  const [form, setForm] = useState<FormState>(initial);

  useEffect(() => {
    if (open) {
      setForm(initial);
    }
  }, [initial, open]);

  const selectedLead = leads.find(
    (lead) => lead.public_id === form.lead_public_id,
  );

  useEffect(() => {
    if (
      mode === "create" &&
      selectedLead &&
      !form.owner_user_public_id &&
      selectedLead.owner_user_public_id
    ) {
      setForm((current) => ({
        ...current,
        owner_user_public_id: selectedLead.owner_user_public_id ?? "",
      }));
    }
  }, [form.owner_user_public_id, mode, selectedLead]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (mode === "edit") {
      await onSubmit({
        title: form.title.trim() || null,
        value_amount: form.value_amount || "0.00",
        currency: form.currency,
        owner_user_public_id: form.owner_user_public_id || null,
        expected_close_date: form.expected_close_date || null,
      });
      return;
    }

    await onSubmit({
      lead_public_id: form.lead_public_id,
      title: form.title.trim() || null,
      value_amount: form.value_amount || "0.00",
      currency: form.currency,
      stage: form.stage || null,
      owner_user_public_id: form.owner_user_public_id || null,
      expected_close_date: form.expected_close_date || null,
    });
  }

  return (
    <Modal
      open={open}
      title={mode === "edit" ? "Editar oportunidade" : "Nova oportunidade"}
      description={
        mode === "edit"
          ? "Atualize os dados comerciais da negociação."
          : "Converta um lead em negociação e posicione-o no pipeline."
      }
      onClose={onClose}
      size="lg"
    >
      <form className="lead-form" onSubmit={handleSubmit}>
        {error && <div className="form-alert form-alert--error">{error}</div>}

        <div className="form-section">
          <div className="form-section__heading">
            <strong>Negociação</strong>
            <span>Lead, título e valor estimado</span>
          </div>
          <div className="form-grid form-grid--2">
            <label className="field field--full">
              <span>Lead *</span>
              <select
                required
                disabled={mode === "edit"}
                value={form.lead_public_id}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    lead_public_id: event.target.value,
                  }))
                }
              >
                <option value="">Selecione um lead</option>
                {mode === "edit" && opportunity && !selectedLead && (
                  <option value={opportunity.lead_public_id}>
                    {opportunity.lead_name}
                  </option>
                )}
                {leads.map((lead) => (
                  <option key={lead.public_id} value={lead.public_id}>
                    {lead.name}
                    {lead.interest ? ` — ${lead.interest}` : ""}
                  </option>
                ))}
              </select>
            </label>

            <label className="field field--full">
              <span>Título</span>
              <input
                value={form.title}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    title: event.target.value,
                  }))
                }
                placeholder={
                  selectedLead?.interest ??
                  "Ex.: Matrícula Radiologia / Proposta comercial"
                }
              />
            </label>

            <label className="field">
              <span>Valor</span>
              <input
                type="number"
                min="0"
                step="0.01"
                value={form.value_amount}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    value_amount: event.target.value,
                  }))
                }
              />
            </label>

            <label className="field">
              <span>Moeda</span>
              <select
                value={form.currency}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    currency: event.target.value,
                  }))
                }
              >
                <option value="BRL">BRL — Real</option>
                <option value="USD">USD — Dólar</option>
                <option value="EUR">EUR — Euro</option>
              </select>
            </label>
          </div>
        </div>

        <div className="form-section">
          <div className="form-section__heading">
            <strong>Pipeline</strong>
            <span>Responsável, etapa e previsão de fechamento</span>
          </div>
          <div className="form-grid form-grid--3">
            {mode === "create" && (
              <label className="field">
                <span>Etapa inicial</span>
                <select
                  value={form.stage}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      stage: event.target.value,
                    }))
                  }
                >
                  {(segmentConfig?.pipeline ?? ["novo"]).map((stage) => (
                    <option key={stage} value={stage}>
                      {labelize(stage)}
                    </option>
                  ))}
                </select>
              </label>
            )}

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

            <label className="field">
              <span>Previsão de fechamento</span>
              <input
                type="date"
                value={form.expected_close_date}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    expected_close_date: event.target.value,
                  }))
                }
              />
            </label>
          </div>
        </div>

        {selectedLead && (
          <div className="opportunity-lead-preview">
            <div>
              <span>Lead selecionado</span>
              <strong>{selectedLead.name}</strong>
            </div>
            <div>
              <span>Interesse</span>
              <strong>{selectedLead.interest ?? "Não informado"}</strong>
            </div>
            <div>
              <span>Origem</span>
              <strong>{labelize(selectedLead.source)}</strong>
            </div>
          </div>
        )}

        <div className="lead-form__actions">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving}>
            {saving
              ? "Salvando..."
              : mode === "edit"
                ? "Salvar alterações"
                : "Criar oportunidade"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

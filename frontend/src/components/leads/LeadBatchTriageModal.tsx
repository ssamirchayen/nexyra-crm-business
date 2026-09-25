import { CheckCircle2, Eye, Layers3, LoaderCircle } from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type {
  LeadBatchOwnerMode,
  LeadBatchRequest,
  LeadBatchResult,
} from "../../types/leadBatch";
import type { WorkspaceMember, WorkspaceSegmentConfig } from "../../types/leads";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

type Props = {
  open: boolean;
  workspacePublicId: string;
  leadPublicIds: string[];
  members: WorkspaceMember[];
  segmentConfig: WorkspaceSegmentConfig | null;
  canAssign: boolean;
  onClose: () => void;
  onApplied: () => void;
};

type ActiveOption = "keep" | "active" | "inactive";

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function fieldLabel(field: string) {
  const labels: Record<string, string> = {
    status: "Status",
    priority: "Prioridade",
    owner: "Responsável",
    active: "Ativo",
  };
  return labels[field] ?? field;
}

export function LeadBatchTriageModal({
  open,
  workspacePublicId,
  leadPublicIds,
  members,
  segmentConfig,
  canAssign,
  onClose,
  onApplied,
}: Props) {
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [ownerMode, setOwnerMode] = useState<LeadBatchOwnerMode>("keep");
  const [ownerUserPublicId, setOwnerUserPublicId] = useState("");
  const [activeOption, setActiveOption] = useState<ActiveOption>("keep");
  const [preview, setPreview] = useState<LeadBatchResult | null>(null);
  const [loading, setLoading] = useState<"preview" | "execute" | null>(null);
  const [error, setError] = useState<string | null>(null);

  const activeMembers = useMemo(
    () => members.filter((member) => member.membership_active && member.user_active),
    [members],
  );

  useEffect(() => {
    if (!open) return;
    setStatus("");
    setPriority("");
    setOwnerMode("keep");
    setOwnerUserPublicId("");
    setActiveOption("keep");
    setPreview(null);
    setError(null);
  }, [open]);

  function resetPreview() {
    setPreview(null);
    setError(null);
  }

  function buildPayload(dryRun: boolean): LeadBatchRequest {
    return {
      lead_public_ids: leadPublicIds,
      status: status || null,
      priority: priority || null,
      owner_mode: canAssign ? ownerMode : "keep",
      owner_user_public_id:
        canAssign && ownerMode === "assign" ? ownerUserPublicId || null : null,
      active:
        activeOption === "keep" ? null : activeOption === "active",
      dry_run: dryRun,
    };
  }

  async function run(dryRun: boolean) {
    const payload = buildPayload(dryRun);
    if (
      payload.status === null &&
      payload.priority === null &&
      payload.owner_mode === "keep" &&
      payload.active === null
    ) {
      setError("Escolha ao menos uma alteração para a triagem em lote.");
      return;
    }
    if (payload.owner_mode === "assign" && !payload.owner_user_public_id) {
      setError("Selecione o responsável que receberá os leads.");
      return;
    }

    setLoading(dryRun ? "preview" : "execute");
    setError(null);
    try {
      const result = await api.post<LeadBatchResult>(
        `/workspaces/${workspacePublicId}/leads/batch`,
        payload,
      );
      setPreview(result);
      if (!dryRun) {
        onApplied();
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível executar a triagem em lote.",
      );
    } finally {
      setLoading(null);
    }
  }

  return (
    <Modal
      open={open}
      title="Triagem e operações em lote"
      description={`${leadPublicIds.length} lead(s) selecionado(s). Faça a simulação antes de aplicar alterações.`}
      onClose={onClose}
      size="lg"
      footer={
        <>
          <Button variant="secondary" disabled={Boolean(loading)} onClick={onClose}>
            Fechar
          </Button>
          <Button
            variant="secondary"
            disabled={Boolean(loading)}
            onClick={() => void run(true)}
          >
            {loading === "preview" ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Eye size={16} />
            )}
            Simular
          </Button>
          <Button
            disabled={!preview || preview.changed === 0 || Boolean(loading)}
            onClick={() => void run(false)}
          >
            {loading === "execute" ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <CheckCircle2 size={16} />
            )}
            Aplicar alterações
          </Button>
        </>
      }
    >
      <div className="batch-triage-stack">
        {error && <div className="page-alert page-alert--error">{error}</div>}

        <div className="batch-triage-summary">
          <Layers3 size={18} />
          <div>
            <strong>{leadPublicIds.length} lead(s) selecionado(s)</strong>
            <span>Máximo de 100 registros por operação.</span>
          </div>
        </div>

        <div className="batch-triage-grid">
          <label>
            Status
            <select
              value={status}
              onChange={(event) => {
                setStatus(event.target.value);
                resetPreview();
              }}
            >
              <option value="">Manter atual</option>
              {segmentConfig?.pipeline.map((stage) => (
                <option key={stage} value={stage}>
                  {labelize(stage)}
                </option>
              ))}
            </select>
          </label>

          <label>
            Prioridade
            <select
              value={priority}
              onChange={(event) => {
                setPriority(event.target.value);
                resetPreview();
              }}
            >
              <option value="">Manter atual</option>
              <option value="baixa">Baixa</option>
              <option value="media">Média</option>
              <option value="alta">Alta</option>
              <option value="urgente">Urgente</option>
            </select>
          </label>

          {canAssign && (
            <label>
              Responsável
              <select
                value={ownerMode === "keep" ? "keep" : ownerMode === "clear" ? "clear" : ownerUserPublicId}
                onChange={(event) => {
                  const value = event.target.value;
                  if (value === "keep") {
                    setOwnerMode("keep");
                    setOwnerUserPublicId("");
                  } else if (value === "clear") {
                    setOwnerMode("clear");
                    setOwnerUserPublicId("");
                  } else {
                    setOwnerMode("assign");
                    setOwnerUserPublicId(value);
                  }
                  resetPreview();
                }}
              >
                <option value="keep">Manter atual</option>
                <option value="clear">Remover responsável</option>
                {activeMembers.map((member) => (
                  <option key={member.public_id} value={member.public_id}>
                    {member.name}
                  </option>
                ))}
              </select>
            </label>
          )}

          <label>
            Situação
            <select
              value={activeOption}
              onChange={(event) => {
                setActiveOption(event.target.value as ActiveOption);
                resetPreview();
              }}
            >
              <option value="keep">Manter atual</option>
              <option value="active">Ativar</option>
              <option value="inactive">Desativar</option>
            </select>
          </label>
        </div>

        {preview && (
          <section className="batch-preview">
            <div className="batch-preview__header">
              <div>
                <strong>{preview.dry_run ? "Prévia da operação" : "Operação aplicada"}</strong>
                <span>
                  {preview.changed} alterado(s) · {preview.unchanged} sem mudança
                </span>
              </div>
              <Badge tone={preview.changed > 0 ? "info" : "neutral"}>
                {preview.changed} mudança(s)
              </Badge>
            </div>

            <div className="batch-preview__list">
              {preview.items.slice(0, 20).map((item) => (
                <div className="batch-preview__item" key={item.lead_public_id}>
                  <div>
                    <strong>{item.lead_name}</strong>
                    <span>{item.lead_public_id}</span>
                  </div>
                  <div className="batch-preview__fields">
                    {item.changed_fields.length > 0 ? (
                      item.changed_fields.map((field) => (
                        <Badge key={field} tone="info">
                          {fieldLabel(field)}
                        </Badge>
                      ))
                    ) : (
                      <Badge tone="neutral">Sem alteração</Badge>
                    )}
                  </div>
                </div>
              ))}
              {preview.items.length > 20 && (
                <span className="batch-preview__more">
                  + {preview.items.length - 20} lead(s) na operação
                </span>
              )}
            </div>
          </section>
        )}
      </div>
    </Modal>
  );
}

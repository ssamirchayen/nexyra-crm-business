import {
  CheckCircle2,
  Eye,
  LoaderCircle,
  MessageSquareText,
  ShieldCheck,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type { WhatsAppTemplate } from "../../types/settings";
import type {
  WhatsAppBulkPreview,
  WhatsAppBulkPreviewRequest,
  WhatsAppBulkSendResult,
} from "../../types/whatsappBulk";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

type Props = {
  open: boolean;
  workspacePublicId: string;
  leadPublicIds: string[];
  onClose: () => void;
  onSent: () => void;
};

const VARIABLE_OPTIONS = [
  "{{lead_name}}",
  "{{interest}}",
  "{{phone}}",
  "{{email}}",
  "{{campaign}}",
  "{{source}}",
  "{{channel}}",
  "{{status}}",
  "{{priority}}",
];

function maskedPhone(phone: string | null) {
  if (!phone) return "Sem telefone";
  if (phone.length <= 6) return phone;
  return `${phone.slice(0, 4)}••••${phone.slice(-4)}`;
}

export function LeadBatchMessageModal({
  open,
  workspacePublicId,
  leadPublicIds,
  onClose,
  onSent,
}: Props) {
  const [integrations, setIntegrations] = useState<Array<{ public_id: string; name: string }>>([]);
  const [integrationId, setIntegrationId] = useState("");
  const [templates, setTemplates] = useState<WhatsAppTemplate[]>([]);
  const [templateKey, setTemplateKey] = useState("");
  const [parameterTemplates, setParameterTemplates] = useState<string[]>([]);
  const [preview, setPreview] = useState<WhatsAppBulkPreview | null>(null);
  const [result, setResult] = useState<WhatsAppBulkSendResult | null>(null);
  const [loading, setLoading] = useState<
    "integrations" | "templates" | "preview" | "send" | null
  >(null);
  const [error, setError] = useState<string | null>(null);

  const selectedTemplate = useMemo(() => {
    const [name, language] = templateKey.split("::");
    return templates.find(
      (item) => item.name === name && item.language === language,
    );
  }, [templateKey, templates]);

  useEffect(() => {
    if (!open) return;
    setIntegrations([]);
    setIntegrationId("");
    setTemplates([]);
    setTemplateKey("");
    setParameterTemplates([]);
    setPreview(null);
    setResult(null);
    setError(null);

    async function loadIntegrations() {
      setLoading("integrations");
      try {
        const whatsapp = await api.get<Array<{ public_id: string; name: string }>>(
          `/workspaces/${workspacePublicId}/whatsapp/bulk/sources`,
        );
        setIntegrations(whatsapp);
        if (whatsapp.length > 0) {
          setIntegrationId(whatsapp[0].public_id);
        }
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Não foi possível carregar as integrações WhatsApp.",
        );
      } finally {
        setLoading(null);
      }
    }

    void loadIntegrations();
  }, [open, workspacePublicId]);

  useEffect(() => {
    if (!open || !integrationId) {
      setTemplates([]);
      setTemplateKey("");
      return;
    }

    async function loadTemplates() {
      setLoading("templates");
      setError(null);
      setPreview(null);
      setResult(null);
      try {
        const items = await api.get<WhatsAppTemplate[]>(
          `/workspaces/${workspacePublicId}/whatsapp/bulk/templates/${integrationId}`,
        );
        const supported = items.filter((item) => item.supported);
        setTemplates(supported);
        if (supported.length > 0) {
          setTemplateKey(`${supported[0].name}::${supported[0].language}`);
        }
      } catch (requestError) {
        setError(
          requestError instanceof Error
            ? requestError.message
            : "Não foi possível carregar os templates aprovados.",
        );
      } finally {
        setLoading(null);
      }
    }

    void loadTemplates();
  }, [integrationId, open, workspacePublicId]);

  useEffect(() => {
    if (!selectedTemplate) {
      setParameterTemplates([]);
      return;
    }
    setParameterTemplates(
      Array.from({ length: selectedTemplate.parameter_count }, (_, index) =>
        index === 0 ? "{{lead_name}}" : index === 1 ? "{{interest}}" : "",
      ),
    );
    setPreview(null);
    setResult(null);
  }, [selectedTemplate]);

  function buildPayload(): WhatsAppBulkPreviewRequest | null {
    if (leadPublicIds.length > 25) {
      setError("Selecione no máximo 25 leads por envio em lote.");
      return null;
    }
    if (!selectedTemplate || !integrationId) {
      setError("Selecione uma integração e um template aprovado.");
      return null;
    }
    if (parameterTemplates.some((value) => !value.trim())) {
      setError("Preencha todos os parâmetros exigidos pelo template.");
      return null;
    }
    return {
      lead_public_ids: leadPublicIds,
      integration_public_id: integrationId,
      template_name: selectedTemplate.name,
      language_code: selectedTemplate.language,
      parameter_templates: parameterTemplates,
    };
  }

  async function runPreview() {
    const payload = buildPayload();
    if (!payload) return;
    setLoading("preview");
    setError(null);
    setResult(null);
    try {
      const response = await api.post<WhatsAppBulkPreview>(
        `/workspaces/${workspacePublicId}/whatsapp/bulk/preview`,
        payload,
      );
      setPreview(response);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível gerar a prévia do lote.",
      );
    } finally {
      setLoading(null);
    }
  }

  async function sendBatch() {
    const payload = buildPayload();
    if (!payload || !preview) return;
    setLoading("send");
    setError(null);
    try {
      const response = await api.post<WhatsAppBulkSendResult>(
        `/workspaces/${workspacePublicId}/whatsapp/bulk/send`,
        {
          ...payload,
          confirmation_token: preview.confirmation_token,
        },
      );
      setResult(response);
      onSent();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível concluir o envio em lote.",
      );
    } finally {
      setLoading(null);
    }
  }

  return (
    <Modal
      open={open}
      title="Mensagens em lote controladas"
      description={`${leadPublicIds.length} lead(s) selecionado(s). Limite de 25 por lote, com prévia e confirmação obrigatórias.`}
      onClose={onClose}
      size="lg"
      footer={
        <>
          <Button variant="secondary" disabled={Boolean(loading)} onClick={onClose}>
            Fechar
          </Button>
          <Button
            variant="secondary"
            disabled={Boolean(loading) || !selectedTemplate}
            onClick={() => void runPreview()}
          >
            {loading === "preview" ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <Eye size={16} />
            )}
            Gerar prévia
          </Button>
          <Button
            disabled={
              Boolean(loading) ||
              !preview ||
              preview.eligible === 0 ||
              Boolean(result)
            }
            onClick={() => void sendBatch()}
          >
            {loading === "send" ? (
              <LoaderCircle className="spin" size={16} />
            ) : (
              <CheckCircle2 size={16} />
            )}
            Confirmar e enviar
          </Button>
        </>
      }
    >
      <div className="batch-message-stack">
        {error && <div className="page-alert page-alert--error">{error}</div>}

        <div className="batch-triage-summary">
          <ShieldCheck size={18} />
          <div>
            <strong>Envio supervisionado</strong>
            <span>
              Opt-out, consentimento e configuração do WhatsApp são revalidados antes do envio.
            </span>
          </div>
        </div>

        <div className="batch-triage-grid">
          <label>
            Integração WhatsApp
            <select
              value={integrationId}
              disabled={loading === "integrations"}
              onChange={(event) => {
                setIntegrationId(event.target.value);
                setPreview(null);
                setResult(null);
              }}
            >
              {integrations.length === 0 && <option value="">Nenhuma integração ativa</option>}
              {integrations.map((item) => (
                <option key={item.public_id} value={item.public_id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>

          <label>
            Template aprovado
            <select
              value={templateKey}
              disabled={loading === "templates" || templates.length === 0}
              onChange={(event) => {
                setTemplateKey(event.target.value);
                setPreview(null);
                setResult(null);
              }}
            >
              {templates.length === 0 && <option value="">Nenhum template disponível</option>}
              {templates.map((item) => (
                <option key={`${item.name}-${item.language}`} value={`${item.name}::${item.language}`}>
                  {item.name} · {item.language}
                </option>
              ))}
            </select>
          </label>
        </div>

        {selectedTemplate && (
          <section className="batch-message-template">
            <div>
              <MessageSquareText size={17} />
              <strong>{selectedTemplate.name}</strong>
              <Badge tone="info">{selectedTemplate.language}</Badge>
            </div>
            <p>{selectedTemplate.body_text || "Template sem texto de corpo."}</p>
          </section>
        )}

        {selectedTemplate && selectedTemplate.parameter_count > 0 && (
          <section className="batch-message-parameters">
            <strong>Parâmetros por lead</strong>
            <span>
              Use texto fixo ou variáveis como {VARIABLE_OPTIONS.slice(0, 3).join(", ")}.
            </span>
            <div className="batch-triage-grid">
              {parameterTemplates.map((value, index) => (
                <label key={`parameter-${index + 1}`}>
                  Variável {`{{${index + 1}}}`}
                  <input
                    value={value}
                    placeholder={index === 0 ? "{{lead_name}}" : "{{interest}}"}
                    onChange={(event) => {
                      setParameterTemplates((current) =>
                        current.map((item, itemIndex) =>
                          itemIndex === index ? event.target.value : item,
                        ),
                      );
                      setPreview(null);
                      setResult(null);
                    }}
                  />
                </label>
              ))}
            </div>
          </section>
        )}

        {preview && (
          <section className="batch-preview">
            <div className="batch-preview__header">
              <div>
                <strong>Prévia do envio</strong>
                <span>
                  {preview.eligible} elegível(is) · {preview.blocked} bloqueado(s)
                </span>
              </div>
              <Badge tone={preview.blocked > 0 ? "warning" : "success"}>
                {preview.eligible}/{preview.requested} liberados
              </Badge>
            </div>
            <div className="batch-preview__list">
              {preview.recipients.map((item) => (
                <div className="batch-preview__item" key={item.lead_public_id}>
                  <div>
                    <strong>{item.lead_name}</strong>
                    <span>{maskedPhone(item.phone)}</span>
                  </div>
                  <div className="batch-message-recipient-status">
                    <Badge tone={item.eligible ? "success" : "danger"}>
                      {item.eligible ? "Elegível" : "Bloqueado"}
                    </Badge>
                    <span>{item.reason}</span>
                  </div>
                  {item.rendered_text && (
                    <p className="batch-message-rendered">{item.rendered_text}</p>
                  )}
                </div>
              ))}
            </div>
          </section>
        )}

        {result && (
          <section className="batch-preview">
            <div className="batch-preview__header">
              <div>
                <strong>Lote concluído</strong>
                <span>
                  {result.sent} enviado(s) · {result.failed} falha(s) · {result.blocked} bloqueado(s)
                </span>
              </div>
              <Badge tone={result.failed > 0 ? "warning" : "success"}>
                {result.sent} enviado(s)
              </Badge>
            </div>
          </section>
        )}
      </div>
    </Modal>
  );
}

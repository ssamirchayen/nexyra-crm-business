import {
  CheckCircle2,
  Clipboard,
  Instagram,
  Loader2,
  PlugZap,
  RefreshCw,
  ShieldCheck,
  Unplug,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type {
  IntegrationSource,
  MetaLeadAdsConnectionTest,
  MetaLeadAdsStatus,
  MetaLeadAdsSubscription,
} from "../../types/settings";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Card } from "../ui/Card";

type Props = {
  workspacePublicId: string;
  source: IntegrationSource;
  onToast(message: string): void;
  onError(message: string | null): void;
};

type FormState = {
  pageId: string;
  pageAccessToken: string;
  formIds: string;
  interestField: string;
  defaultInterest: string;
};

const EMPTY_FORM: FormState = {
  pageId: "",
  pageAccessToken: "",
  formIds: "",
  interestField: "",
  defaultInterest: "Meta Lead Ads",
};

export function MetaLeadAdsPanel({
  workspacePublicId,
  source,
  onToast,
  onError,
}: Props) {
  const [status, setStatus] = useState<MetaLeadAdsStatus | null>(null);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [subscribing, setSubscribing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [testResult, setTestResult] =
    useState<MetaLeadAdsConnectionTest | null>(null);

  const basePath = useMemo(
    () =>
      `/workspaces/${workspacePublicId}/integrations/${source.public_id}/meta`,
    [workspacePublicId, source.public_id],
  );

  async function loadStatus() {
    setLoading(true);
    onError(null);
    try {
      const current = await api.get<MetaLeadAdsStatus>(basePath);
      setStatus(current);
      setForm((previous) => ({
        pageId: current.page_id ?? "",
        pageAccessToken: "",
        formIds: current.form_ids.join(", "),
        interestField: current.interest_field ?? "",
        defaultInterest: current.default_interest ?? "Meta Lead Ads",
      }));
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a integração Meta.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, [basePath]);

  async function save() {
    const pageId = form.pageId.trim();
    const pageAccessToken = form.pageAccessToken.trim();
    if (!pageId) {
      onError("Informe o Page ID da página conectada à Meta.");
      return;
    }
    if (!pageAccessToken) {
      onError(
        status?.configured
          ? "Informe o Page Access Token para substituir a credencial atual."
          : "Informe o Page Access Token.",
      );
      return;
    }

    const formIds = form.formIds
      .split(/[\n,;]+/)
      .map((item) => item.trim())
      .filter(Boolean);

    setSaving(true);
    setTestResult(null);
    onError(null);
    try {
      const saved = await api.put<MetaLeadAdsStatus>(basePath, {
        page_id: pageId,
        page_access_token: pageAccessToken,
        form_ids: formIds,
        interest_field: form.interestField.trim() || null,
        default_interest: form.defaultInterest.trim() || null,
      });
      setStatus(saved);
      setForm((current) => ({ ...current, pageAccessToken: "" }));
      onToast("Credenciais Meta salvas de forma criptografada.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível configurar a Meta.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function subscribePage() {
    setSubscribing(true);
    onError(null);
    try {
      await api.post<MetaLeadAdsSubscription>(`${basePath}/subscribe`);
      const current = await api.get<MetaLeadAdsStatus>(basePath);
      setStatus(current);
      onToast("Página Meta assinada para novos Lead Ads.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível assinar a página Meta.",
      );
    } finally {
      setSubscribing(false);
    }
  }

  async function testConnection() {
    setTesting(true);
    setTestResult(null);
    onError(null);
    try {
      const result = await api.post<MetaLeadAdsConnectionTest>(`${basePath}/test`);
      setTestResult(result);
      onToast("Conexão com a Meta validada.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível validar a conexão com a Meta.",
      );
    } finally {
      setTesting(false);
    }
  }

  async function disconnect() {
    if (!window.confirm("Remover a credencial Meta desta fonte?")) return;
    setDisconnecting(true);
    setTestResult(null);
    onError(null);
    try {
      const current = await api.delete<MetaLeadAdsStatus>(basePath);
      setStatus(current);
      setForm(EMPTY_FORM);
      onToast("Credencial Meta removida.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível desconectar a Meta.",
      );
    } finally {
      setDisconnecting(false);
    }
  }

  async function copyWebhook() {
    const value = `/api/v1${status?.webhook_endpoint ?? "/meta/webhook"}`;
    try {
      await navigator.clipboard.writeText(value);
      onToast("Endpoint do webhook Meta copiado.");
    } catch {
      onToast(value);
    }
  }

  return (
    <Card
      title="Meta / Instagram Lead Ads"
      description="Receba leadgen webhooks da Meta e busque os dados completos pela Graph API."
    >
      {loading ? (
        <div className="meta-connector-loading">
          <Loader2 size={18} className="spin" /> Carregando conector Meta...
        </div>
      ) : (
        <div className="meta-connector">
          <div className="meta-connector__header">
            <div className="meta-connector__brand">
              <span className="meta-connector__icon"><Instagram size={20} /></span>
              <span>
                <strong>{source.name}</strong>
                <small>{source.source} / {source.channel}</small>
              </span>
            </div>
            <div className="meta-connector__badges">
              <Badge tone={status?.configured ? "success" : "neutral"}>
                {status?.configured ? "Credencial salva" : "Não configurada"}
              </Badge>
              <Badge tone={status?.server_ready ? "success" : "neutral"}>
                {status?.server_ready ? "Webhook pronto" : "Servidor pendente"}
              </Badge>
              <Badge tone={status?.subscribed ? "success" : "neutral"}>
                {status?.subscribed ? "Leadgen assinado" : "Leadgen pendente"}
              </Badge>
            </div>
          </div>

          <div className="meta-connector__notice">
            <ShieldCheck size={18} />
            <span>
              O Page Access Token é criptografado antes de ir para o banco. O App Secret e o Verify Token ficam no arquivo <code>.env</code> do servidor.
            </span>
          </div>

          <div className="meta-connector__grid">
            <label>
              <span>Page ID</span>
              <input
                value={form.pageId}
                placeholder="Ex.: 123456789012345"
                onChange={(event) =>
                  setForm((current) => ({ ...current, pageId: event.target.value }))
                }
              />
            </label>
            <label>
              <span>Page Access Token</span>
              <input
                type="password"
                value={form.pageAccessToken}
                placeholder={status?.configured ? `${status.token_hint ?? "Token salvo"} · informe apenas para trocar` : "Cole o token da página"}
                autoComplete="off"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    pageAccessToken: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              <span>Form IDs autorizados</span>
              <input
                value={form.formIds}
                placeholder="FORM_ID_1, FORM_ID_2 · vazio aceita todos"
                onChange={(event) =>
                  setForm((current) => ({ ...current, formIds: event.target.value }))
                }
              />
            </label>
            <label>
              <span>Campo de interesse</span>
              <input
                value={form.interestField}
                placeholder="Ex.: produto, curso, interesse"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    interestField: event.target.value,
                  }))
                }
              />
            </label>
            <label className="meta-connector__wide">
              <span>Interesse padrão</span>
              <input
                value={form.defaultInterest}
                placeholder="Meta Lead Ads"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    defaultInterest: event.target.value,
                  }))
                }
              />
            </label>
          </div>

          <div className="meta-connector__webhook">
            <div>
              <span>Callback URL</span>
              <code>/api/v1{status?.webhook_endpoint ?? "/meta/webhook"}</code>
            </div>
            <button
              type="button"
              className="table-action-button"
              onClick={() => void copyWebhook()}
              aria-label="Copiar webhook da Meta"
            >
              <Clipboard size={14} />
            </button>
            <small>
              Graph API {status?.graph_api_version ?? "v25.0"} · configure META_APP_SECRET e META_WEBHOOK_VERIFY_TOKEN no servidor.
            </small>
          </div>

          {testResult && (
            <div className="meta-connector__success">
              <CheckCircle2 size={17} />
              <span>
                <strong>Conexão válida</strong>
                <small>{testResult.page_name ?? "Página Meta"} · {testResult.page_id}</small>
              </span>
            </div>
          )}

          <div className="meta-connector__actions">
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? <Loader2 size={15} className="spin" /> : <PlugZap size={15} />}
              {status?.configured ? "Atualizar credencial" : "Conectar Meta"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => void subscribePage()}
              disabled={!status?.configured || !status?.server_ready || subscribing}
            >
              {subscribing ? <Loader2 size={15} className="spin" /> : <PlugZap size={15} />}
              {status?.subscribed ? "Reassinar leadgen" : "Assinar Lead Ads"}
            </Button>
            <Button
              variant="secondary"
              onClick={() => void testConnection()}
              disabled={!status?.configured || testing}
            >
              {testing ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}
              Testar conexão
            </Button>
            {status?.configured && (
              <Button
                variant="secondary"
                onClick={() => void disconnect()}
                disabled={disconnecting}
              >
                {disconnecting ? <Loader2 size={15} className="spin" /> : <Unplug size={15} />}
                Desconectar
              </Button>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}

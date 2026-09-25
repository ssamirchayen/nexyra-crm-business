import {
  CheckCircle2,
  Clipboard,
  History,
  Link2,
  Loader2,
  MessageCircle,
  PlugZap,
  RefreshCw,
  Send,
  ShieldCheck,
  Smartphone,
  Unplug,
  UsersRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import {
  loadMetaFacebookSdk,
  startWhatsAppCoexistenceSignup,
} from "../../lib/metaEmbeddedSignup";
import type {
  IntegrationSource,
  WhatsAppCoexistenceSyncResult,
  WhatsAppConnectionTest,
  WhatsAppEmbeddedSignupConfig,
  WhatsAppEmbeddedSignupResult,
  WhatsAppMessage,
  WhatsAppPhoneCandidate,
  WhatsAppMessagePreview,
  WhatsAppMessageSendResult,
  WhatsAppStatus,
  WhatsAppSubscription,
  WhatsAppTemplate,
  WhatsAppTemplatePreview,
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

type ConfigForm = {
  phoneNumberId: string;
  businessAccountId: string;
  accessToken: string;
  defaultInterest: string;
};

type Composer = {
  to: string;
  text: string;
};

type TemplateComposer = {
  to: string;
  templateKey: string;
  parameters: string[];
};

const EMPTY_CONFIG: ConfigForm = {
  phoneNumberId: "",
  businessAccountId: "",
  accessToken: "",
  defaultInterest: "WhatsApp",
};

const EMPTY_COMPOSER: Composer = {
  to: "",
  text: "",
};

const EMPTY_TEMPLATE_COMPOSER: TemplateComposer = {
  to: "",
  templateKey: "",
  parameters: [],
};

export function WhatsAppCloudPanel({
  workspacePublicId,
  source,
  onToast,
  onError,
}: Props) {
  const [status, setStatus] = useState<WhatsAppStatus | null>(null);
  const [form, setForm] = useState<ConfigForm>(EMPTY_CONFIG);
  const [composer, setComposer] = useState<Composer>(EMPTY_COMPOSER);
  const [preview, setPreview] = useState<WhatsAppMessagePreview | null>(null);
  const [messages, setMessages] = useState<WhatsAppMessage[]>([]);
  const [templates, setTemplates] = useState<WhatsAppTemplate[]>([]);
  const [templateComposer, setTemplateComposer] =
    useState<TemplateComposer>(EMPTY_TEMPLATE_COMPOSER);
  const [templatePreview, setTemplatePreview] =
    useState<WhatsAppTemplatePreview | null>(null);
  const [templatePreviewing, setTemplatePreviewing] = useState(false);
  const [templateSending, setTemplateSending] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [subscribing, setSubscribing] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [sending, setSending] = useState(false);
  const [testResult, setTestResult] =
    useState<WhatsAppConnectionTest | null>(null);
  const [embeddedConfig, setEmbeddedConfig] =
    useState<WhatsAppEmbeddedSignupConfig | null>(null);
  const [embeddedSdkReady, setEmbeddedSdkReady] = useState(false);
  const [embeddedBusy, setEmbeddedBusy] = useState(false);
  const [phoneCandidates, setPhoneCandidates] = useState<WhatsAppPhoneCandidate[]>([]);
  const [syncing, setSyncing] = useState<"history" | "smb_app_state_sync" | null>(null);

  const basePath = useMemo(
    () =>
      `/workspaces/${workspacePublicId}/integrations/${source.public_id}/whatsapp`,
    [workspacePublicId, source.public_id],
  );

  const selectedTemplate = useMemo(
    () =>
      templates.find(
        (item) => `${item.name}::${item.language}` === templateComposer.templateKey,
      ) ?? null,
    [templateComposer.templateKey, templates],
  );

  async function loadStatus() {
    setLoading(true);
    onError(null);
    try {
      const [current, recent, signupConfig] = await Promise.all([
        api.get<WhatsAppStatus>(basePath),
        api.get<WhatsAppMessage[]>(`${basePath}/messages?limit=12`),
        api.get<WhatsAppEmbeddedSignupConfig>(`${basePath}/embedded-signup/config`),
      ]);
      setStatus(current);
      setMessages(recent);
      setEmbeddedConfig(signupConfig);
      setForm((previous) => ({
        phoneNumberId: current.phone_number_id ?? "",
        businessAccountId: current.business_account_id ?? "",
        accessToken: "",
        defaultInterest: current.default_interest ?? "WhatsApp",
      }));
      if (current.configured && current.business_account_id) {
        try {
          const approvedTemplates = await api.get<WhatsAppTemplate[]>(
            `${basePath}/templates?limit=100`,
          );
          setTemplates(approvedTemplates);
        } catch {
          setTemplates([]);
        }
      } else {
        setTemplates([]);
      }
      if (!current.configured) {
        setComposer(EMPTY_COMPOSER);
        setPreview(null);
      }
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a integração WhatsApp.",
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadStatus();
  }, [basePath]);

  useEffect(() => {
    setEmbeddedSdkReady(false);
    if (!embeddedConfig?.enabled || !embeddedConfig.app_id) return;
    let cancelled = false;
    void loadMetaFacebookSdk(
      embeddedConfig.app_id,
      embeddedConfig.graph_api_version,
    )
      .then(() => {
        if (!cancelled) setEmbeddedSdkReady(true);
      })
      .catch((sdkError) => {
        if (!cancelled) {
          onError(
            sdkError instanceof Error
              ? sdkError.message
              : "Não foi possível carregar o SDK da Meta.",
          );
        }
      });
    return () => {
      cancelled = true;
    };
  }, [embeddedConfig?.app_id, embeddedConfig?.enabled, embeddedConfig?.graph_api_version]);

  async function connectWhatsAppBusinessApp() {
    if (!embeddedConfig?.enabled || !embeddedConfig.config_id) {
      onError(
        "Embedded Signup ainda não está configurado no servidor. Preencha o App ID e o Configuration ID no .env.",
      );
      return;
    }
    if (!embeddedSdkReady) {
      onError("SDK da Meta ainda está carregando. Aguarde alguns segundos e tente novamente.");
      return;
    }

    // Inicie o FB.login imediatamente no clique para evitar bloqueio do popup.
    const signupFlow = startWhatsAppCoexistenceSignup({
      configId: embeddedConfig.config_id,
      featureType: embeddedConfig.feature_type,
    });
    setEmbeddedBusy(true);
    setPhoneCandidates([]);
    onError(null);
    try {
      const { code, session } = await signupFlow;
      const result = await api.post<WhatsAppEmbeddedSignupResult>(
        `${basePath}/embedded-signup/complete`,
        {
          code,
          waba_id: session.data?.waba_id ?? null,
          phone_number_id: session.data?.phone_number_id ?? null,
          event: session.event,
          default_interest: form.defaultInterest.trim() || "WhatsApp",
        },
      );
      setPhoneCandidates(result.candidates);
      await loadStatus();
      if (result.selection_required) {
        onToast("Conta autorizada. Selecione o número do WhatsApp que será usado pelo Nexyra.");
      } else {
        onToast("WhatsApp Business conectado em modo de coexistência.");
      }
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível concluir o Embedded Signup do WhatsApp.",
      );
    } finally {
      setEmbeddedBusy(false);
    }
  }

  async function selectEmbeddedPhone(phoneNumberId: string) {
    setEmbeddedBusy(true);
    onError(null);
    try {
      await api.post<WhatsAppEmbeddedSignupResult>(
        `${basePath}/embedded-signup/select-phone`,
        {
          phone_number_id: phoneNumberId,
          default_interest: form.defaultInterest.trim() || "WhatsApp",
        },
      );
      setPhoneCandidates([]);
      await loadStatus();
      onToast("Número selecionado e conectado em coexistência.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível selecionar o número do WhatsApp.",
      );
    } finally {
      setEmbeddedBusy(false);
    }
  }

  async function requestCoexistenceSync(
    syncType: "history" | "smb_app_state_sync",
  ) {
    setSyncing(syncType);
    onError(null);
    try {
      const result = await api.post<WhatsAppCoexistenceSyncResult>(
        `${basePath}/coexistence/sync`,
        { sync_type: syncType },
      );
      onToast(
        result.request_id
          ? `Sincronização solicitada à Meta (${result.request_id}).`
          : "Sincronização solicitada à Meta.",
      );
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível solicitar a sincronização do WhatsApp Business App.",
      );
    } finally {
      setSyncing(null);
    }
  }

  async function save() {
    const phoneNumberId = form.phoneNumberId.trim();
    const accessToken = form.accessToken.trim();
    if (!phoneNumberId) {
      onError("Informe o Phone Number ID do WhatsApp Cloud API.");
      return;
    }
    if (!accessToken) {
      onError(
        status?.configured
          ? "Informe o Access Token para substituir a credencial atual."
          : "Informe o Access Token do WhatsApp.",
      );
      return;
    }

    setSaving(true);
    setTestResult(null);
    onError(null);
    try {
      const saved = await api.put<WhatsAppStatus>(basePath, {
        phone_number_id: phoneNumberId,
        business_account_id: form.businessAccountId.trim() || null,
        access_token: accessToken,
        default_interest: form.defaultInterest.trim() || null,
      });
      setStatus(saved);
      setForm((current) => ({ ...current, accessToken: "" }));
      onToast("Credencial WhatsApp salva de forma criptografada.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível configurar o WhatsApp.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function testConnection() {
    setTesting(true);
    setTestResult(null);
    onError(null);
    try {
      const result = await api.post<WhatsAppConnectionTest>(`${basePath}/test`);
      setTestResult(result);
      await loadStatus();
      onToast("Conexão com o WhatsApp Cloud API validada.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível validar a conexão com o WhatsApp.",
      );
    } finally {
      setTesting(false);
    }
  }

  async function subscribe() {
    setSubscribing(true);
    onError(null);
    try {
      await api.post<WhatsAppSubscription>(`${basePath}/subscribe`);
      await loadStatus();
      onToast("Conta do WhatsApp Business assinada para webhooks.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível assinar os webhooks do WhatsApp.",
      );
    } finally {
      setSubscribing(false);
    }
  }

  async function disconnect() {
    if (!window.confirm("Remover a credencial WhatsApp desta fonte?")) return;
    setDisconnecting(true);
    setTestResult(null);
    onError(null);
    try {
      const current = await api.delete<WhatsAppStatus>(basePath);
      setStatus(current);
      setForm(EMPTY_CONFIG);
      setComposer(EMPTY_COMPOSER);
      setPreview(null);
      setTemplates([]);
      setTemplateComposer(EMPTY_TEMPLATE_COMPOSER);
      setTemplatePreview(null);
      onToast("Credencial WhatsApp removida.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível desconectar o WhatsApp.",
      );
    } finally {
      setDisconnecting(false);
    }
  }

  async function copyWebhook() {
    const value = `/api/v1${status?.webhook_endpoint ?? "/whatsapp/webhook"}`;
    try {
      await navigator.clipboard.writeText(value);
      onToast("Endpoint do webhook WhatsApp copiado.");
    } catch {
      onToast(value);
    }
  }

  function updateComposer(next: Partial<Composer>) {
    setComposer((current) => ({ ...current, ...next }));
    setPreview(null);
  }

  async function createPreview() {
    setPreviewing(true);
    onError(null);
    try {
      const result = await api.post<WhatsAppMessagePreview>(
        `${basePath}/messages/preview`,
        { to: composer.to, text: composer.text },
      );
      setPreview(result);
      setComposer({ to: result.to, text: result.text });
      onToast("Prévia criada. Confirme antes do envio.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível gerar a prévia da mensagem.",
      );
    } finally {
      setPreviewing(false);
    }
  }

  async function confirmSend() {
    if (!preview) return;
    setSending(true);
    onError(null);
    try {
      const result = await api.post<WhatsAppMessageSendResult>(
        `${basePath}/messages/send`,
        {
          to: preview.to,
          text: preview.text,
          confirmation_token: preview.confirmation_token,
        },
      );
      setPreview(null);
      setComposer(EMPTY_COMPOSER);
      await loadStatus();
      onToast(
        result.lead_public_id
          ? "Mensagem enviada e registrada no histórico do lead."
          : "Mensagem enviada e registrada no histórico do WhatsApp.",
      );
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível enviar a mensagem.",
      );
    } finally {
      setSending(false);
    }
  }

  function updateTemplateComposer(next: Partial<TemplateComposer>) {
    setTemplateComposer((current) => ({ ...current, ...next }));
    setTemplatePreview(null);
  }

  function selectTemplate(templateKey: string) {
    const template = templates.find(
      (item) => `${item.name}::${item.language}` === templateKey,
    );
    setTemplateComposer((current) => ({
      ...current,
      templateKey,
      parameters: template
        ? Array.from({ length: template.parameter_count }, () => "")
        : [],
    }));
    setTemplatePreview(null);
  }

  function updateTemplateParameter(index: number, value: string) {
    setTemplateComposer((current) => {
      const parameters = [...current.parameters];
      parameters[index] = value;
      return { ...current, parameters };
    });
    setTemplatePreview(null);
  }

  async function createTemplatePreview() {
    if (!selectedTemplate) return;
    setTemplatePreviewing(true);
    onError(null);
    try {
      const result = await api.post<WhatsAppTemplatePreview>(
        `${basePath}/templates/preview`,
        {
          to: templateComposer.to,
          template_name: selectedTemplate.name,
          language_code: selectedTemplate.language,
          parameters: templateComposer.parameters,
        },
      );
      setTemplatePreview(result);
      setTemplateComposer((current) => ({ ...current, to: result.to }));
      onToast("Prévia do template criada. Confirme antes do envio.");
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível gerar a prévia do template.",
      );
    } finally {
      setTemplatePreviewing(false);
    }
  }

  async function confirmTemplateSend() {
    if (!templatePreview) return;
    setTemplateSending(true);
    onError(null);
    try {
      const result = await api.post<WhatsAppMessageSendResult>(
        `${basePath}/templates/send`,
        {
          to: templatePreview.to,
          template_name: templatePreview.template_name,
          language_code: templatePreview.language_code,
          parameters: templatePreview.parameters,
          confirmation_token: templatePreview.confirmation_token,
        },
      );
      setTemplatePreview(null);
      setTemplateComposer(EMPTY_TEMPLATE_COMPOSER);
      await loadStatus();
      onToast(
        result.lead_public_id
          ? "Template enviado e registrado no histórico do lead."
          : "Template enviado e registrado no histórico do WhatsApp.",
      );
    } catch (requestError) {
      onError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível enviar o template.",
      );
    } finally {
      setTemplateSending(false);
    }
  }

  return (
    <Card
      title="WhatsApp Cloud API"
      description="Receba mensagens, atualize leads e envie textos com prévia e confirmação."
    >
      {loading ? (
        <div className="meta-connector-loading">
          <Loader2 size={18} className="spin" /> Carregando conector WhatsApp...
        </div>
      ) : (
        <div className="meta-connector whatsapp-connector">
          <div className="meta-connector__header">
            <div className="meta-connector__brand">
              <span className="meta-connector__icon"><MessageCircle size={20} /></span>
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
                {status?.subscribed ? "Webhook assinado" : "Assinatura pendente"}
              </Badge>
            </div>
          </div>

          <div className="meta-connector__notice">
            <ShieldCheck size={18} />
            <span>
              O Access Token fica criptografado. O App Secret e o Verify Token ficam no <code>.env</code> do servidor. Mensagens de saída exigem prévia antes da confirmação.
            </span>
          </div>

          <div className="whatsapp-embedded-signup">
            <div className="whatsapp-embedded-signup__header">
              <div>
                <span className="whatsapp-embedded-signup__icon"><Smartphone size={20} /></span>
                <span>
                  <strong>WhatsApp Business no celular</strong>
                  <small>Embedded Signup + Coexistência oficial da Meta</small>
                </span>
              </div>
              <Badge tone={status?.coexistence ? "success" : "neutral"}>
                {status?.coexistence ? "Coexistência ativa" : "Não conectado"}
              </Badge>
            </div>

            <p className="whatsapp-embedded-signup__description">
              Conecte o número que já funciona no WhatsApp Business sem colocar o App Secret ou o Access Token no navegador. O código da Meta é trocado pelo backend e o token fica criptografado no Nexyra.
            </p>

            {!embeddedConfig?.enabled ? (
              <div className="whatsapp-embedded-signup__warning">
                <ShieldCheck size={17} />
                <span>
                  Preencha <code>WHATSAPP_META_APP_ID</code> e <code>WHATSAPP_EMBEDDED_SIGNUP_CONFIG_ID</code> no <code>.env</code>. O <code>WHATSAPP_APP_SECRET</code> também precisa estar configurado no servidor.
                </span>
              </div>
            ) : (
              <>
                <div className="whatsapp-embedded-signup__actions">
                  <Button
                    onClick={() => void connectWhatsAppBusinessApp()}
                    disabled={embeddedBusy || !embeddedSdkReady}
                  >
                    {embeddedBusy ? (
                      <Loader2 size={15} className="spin" />
                    ) : (
                      <Link2 size={15} />
                    )}
                    {status?.coexistence ? "Reconectar WhatsApp Business" : "Conectar WhatsApp Business"}
                  </Button>
                  <Badge tone={embeddedSdkReady ? "success" : "neutral"}>
                    {embeddedSdkReady ? "SDK Meta pronto" : "Carregando SDK Meta"}
                  </Badge>
                </div>
                <div className="whatsapp-embedded-signup__webhooks">
                  <span>Webhooks necessários na Meta:</span>
                  <div>
                    {embeddedConfig.required_webhook_fields.map((field) => (
                      <code key={field}>{field}</code>
                    ))}
                  </div>
                </div>
              </>
            )}

            {phoneCandidates.length > 0 && (
              <div className="whatsapp-phone-candidates">
                <strong>Escolha o número autorizado</strong>
                <small>A Meta compartilhou mais de um número nesta conta.</small>
                {phoneCandidates.map((candidate) => (
                  <button
                    type="button"
                    key={candidate.phone_number_id}
                    disabled={embeddedBusy}
                    onClick={() => void selectEmbeddedPhone(candidate.phone_number_id)}
                  >
                    <Smartphone size={16} />
                    <span>
                      <strong>{candidate.verified_name || "WhatsApp Business"}</strong>
                      <small>
                        {candidate.display_phone_number || candidate.phone_number_id}
                        {candidate.quality_rating ? ` · ${candidate.quality_rating}` : ""}
                      </small>
                    </span>
                  </button>
                ))}
              </div>
            )}

            {status?.coexistence && status.phone_number_id && (
              <div className="whatsapp-coexistence-sync">
                <div>
                  <CheckCircle2 size={18} />
                  <span>
                    <strong>{status.verified_name || "WhatsApp Business conectado"}</strong>
                    <small>
                      {status.display_phone_number || status.phone_number_id} · celular + Cloud API
                    </small>
                  </span>
                </div>
                <div className="whatsapp-coexistence-sync__actions">
                  <Button
                    variant="secondary"
                    disabled={syncing !== null}
                    onClick={() => void requestCoexistenceSync("smb_app_state_sync")}
                  >
                    {syncing === "smb_app_state_sync" ? (
                      <Loader2 size={15} className="spin" />
                    ) : (
                      <UsersRound size={15} />
                    )}
                    Sincronizar contatos
                  </Button>
                  <Button
                    variant="secondary"
                    disabled={syncing !== null}
                    onClick={() => void requestCoexistenceSync("history")}
                  >
                    {syncing === "history" ? (
                      <Loader2 size={15} className="spin" />
                    ) : (
                      <History size={15} />
                    )}
                    Sincronizar histórico
                  </Button>
                </div>
                <small className="whatsapp-coexistence-sync__hint">
                  Essas sincronizações são tratadas como ações explícitas porque a Meta pode limitar a execução após o onboarding. O Nexyra não dispara histórico automaticamente.
                </small>
              </div>
            )}
          </div>

          <div className="whatsapp-manual-config-title">
            <strong>Configuração manual</strong>
            <small>Fallback para Cloud API tradicional ou manutenção técnica.</small>
          </div>

          <div className="meta-connector__grid">
            <label>
              <span>Phone Number ID</span>
              <input
                value={form.phoneNumberId}
                placeholder="Ex.: 123456789012345"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    phoneNumberId: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              <span>WhatsApp Business Account ID</span>
              <input
                value={form.businessAccountId}
                placeholder="Ex.: 123456789012345"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    businessAccountId: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              <span>Access Token</span>
              <input
                type="password"
                value={form.accessToken}
                placeholder={
                  status?.configured
                    ? `${status.token_hint ?? "Token salvo"} · informe apenas para trocar`
                    : "Cole o token do WhatsApp Cloud API"
                }
                autoComplete="off"
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    accessToken: event.target.value,
                  }))
                }
              />
            </label>
            <label>
              <span>Interesse padrão</span>
              <input
                value={form.defaultInterest}
                placeholder="WhatsApp"
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
              <code>/api/v1{status?.webhook_endpoint ?? "/whatsapp/webhook"}</code>
            </div>
            <button
              type="button"
              className="table-action-button"
              onClick={() => void copyWebhook()}
              aria-label="Copiar webhook do WhatsApp"
            >
              <Clipboard size={14} />
            </button>
            <small>
              Configure este callback no app da Meta e assine o campo de mensagens do WhatsApp Business Account.
            </small>
          </div>

          {testResult && (
            <div className="meta-connector__success">
              <CheckCircle2 size={18} />
              <span>
                <strong>{testResult.verified_name || "Número validado"}</strong>
                <small>
                  {testResult.display_phone_number || testResult.phone_number_id}
                  {testResult.quality_rating ? ` · Qualidade ${testResult.quality_rating}` : ""}
                </small>
              </span>
            </div>
          )}

          <div className="meta-connector__actions">
            <Button onClick={() => void save()} disabled={saving}>
              {saving ? <Loader2 size={15} className="spin" /> : <ShieldCheck size={15} />}
              Salvar credencial
            </Button>
            <Button
              variant="secondary"
              onClick={() => void testConnection()}
              disabled={!status?.configured || testing}
            >
              {testing ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}
              Testar conexão
            </Button>
            <Button
              variant="secondary"
              onClick={() => void subscribe()}
              disabled={!status?.configured || subscribing || !status?.business_account_id}
            >
              {subscribing ? <Loader2 size={15} className="spin" /> : <PlugZap size={15} />}
              Assinar webhooks
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

          {status?.configured && (
            <div className="whatsapp-composer">
              <div className="whatsapp-composer__header">
                <div>
                  <strong>Envio controlado</strong>
                  <small>Gere a prévia e só depois confirme o envio.</small>
                </div>
                <Badge tone="neutral">{status.recent_messages} recentes</Badge>
              </div>
              <div className="whatsapp-composer__grid">
                <label>
                  <span>Número com DDI</span>
                  <input
                    value={composer.to}
                    placeholder="5592999999999"
                    onChange={(event) => updateComposer({ to: event.target.value })}
                  />
                </label>
                <label className="whatsapp-composer__message">
                  <span>Mensagem</span>
                  <textarea
                    rows={4}
                    value={composer.text}
                    placeholder="Digite a mensagem que será revisada antes do envio..."
                    onChange={(event) => updateComposer({ text: event.target.value })}
                  />
                </label>
              </div>
              <div className="meta-connector__actions">
                <Button
                  variant="secondary"
                  disabled={previewing || !composer.to.trim() || !composer.text.trim()}
                  onClick={() => void createPreview()}
                >
                  {previewing ? <Loader2 size={15} className="spin" /> : <RefreshCw size={15} />}
                  Gerar prévia
                </Button>
                {preview && (
                  <Button disabled={sending} onClick={() => void confirmSend()}>
                    {sending ? <Loader2 size={15} className="spin" /> : <Send size={15} />}
                    Confirmar e enviar
                  </Button>
                )}
              </div>
              {preview && (
                <div className="whatsapp-preview">
                  <strong>Prévia pronta</strong>
                  <span>Para: {preview.to}</span>
                  <p>{preview.text}</p>
                  <small>
                    Esta confirmação expira em {new Date(preview.expires_at).toLocaleTimeString("pt-BR")}.
                  </small>
                </div>
              )}
            </div>
          )}

          {status?.configured && status.business_account_id && (
            <div className="whatsapp-composer whatsapp-template-composer">
              <div className="whatsapp-composer__header">
                <div>
                  <strong>Templates aprovados</strong>
                  <small>Use templates da Meta para contatos fora da janela de conversa, sempre com prévia e confirmação.</small>
                </div>
                <Badge tone={templates.length > 0 ? "success" : "neutral"}>
                  {templates.length} disponível(is)
                </Badge>
              </div>
              {templates.length === 0 ? (
                <div className="whatsapp-template-empty">
                  Nenhum template aprovado foi carregado. Atualize o painel depois de criar ou aprovar templates no WhatsApp Manager.
                </div>
              ) : (
                <>
                  <div className="whatsapp-composer__grid">
                    <label>
                      <span>Número com DDI</span>
                      <input
                        value={templateComposer.to}
                        placeholder="5592999999999"
                        onChange={(event) =>
                          updateTemplateComposer({ to: event.target.value })
                        }
                      />
                    </label>
                    <label>
                      <span>Template aprovado</span>
                      <select
                        value={templateComposer.templateKey}
                        onChange={(event) => selectTemplate(event.target.value)}
                      >
                        <option value="">Selecione...</option>
                        {templates.map((template) => (
                          <option
                            key={`${template.name}::${template.language}`}
                            value={`${template.name}::${template.language}`}
                            disabled={!template.supported}
                          >
                            {template.name} · {template.language}
                            {!template.supported ? " · não suportado" : ""}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  {selectedTemplate && (
                    <div className="whatsapp-template-detail">
                      <p>{selectedTemplate.body_text || `[Template ${selectedTemplate.name}]`}</p>
                      <small>
                        Categoria: {selectedTemplate.category || "—"} · {selectedTemplate.parameter_count} variável(is) no corpo
                      </small>
                    </div>
                  )}
                  {selectedTemplate && selectedTemplate.parameter_count > 0 && (
                    <div className="whatsapp-template-params">
                      {templateComposer.parameters.map((parameter, index) => (
                        <label key={`${selectedTemplate.name}-param-${index}`}>
                          <span>Variável {index + 1}</span>
                          <input
                            value={parameter}
                            placeholder={`Valor para {{${index + 1}}}`}
                            onChange={(event) =>
                              updateTemplateParameter(index, event.target.value)
                            }
                          />
                        </label>
                      ))}
                    </div>
                  )}
                  <div className="meta-connector__actions">
                    <Button
                      variant="secondary"
                      disabled={
                        templatePreviewing ||
                        !selectedTemplate ||
                        !selectedTemplate.supported ||
                        !templateComposer.to.trim() ||
                        templateComposer.parameters.some((value) => !value.trim())
                      }
                      onClick={() => void createTemplatePreview()}
                    >
                      {templatePreviewing ? (
                        <Loader2 size={15} className="spin" />
                      ) : (
                        <RefreshCw size={15} />
                      )}
                      Gerar prévia do template
                    </Button>
                    {templatePreview && (
                      <Button
                        disabled={templateSending}
                        onClick={() => void confirmTemplateSend()}
                      >
                        {templateSending ? (
                          <Loader2 size={15} className="spin" />
                        ) : (
                          <Send size={15} />
                        )}
                        Confirmar e enviar template
                      </Button>
                    )}
                  </div>
                  {templatePreview && (
                    <div className="whatsapp-preview">
                      <strong>Prévia do template</strong>
                      <span>Para: {templatePreview.to}</span>
                      <p>{templatePreview.rendered_text}</p>
                      <small>
                        {templatePreview.template_name} · {templatePreview.language_code} · confirmação expira em {new Date(templatePreview.expires_at).toLocaleTimeString("pt-BR")}
                      </small>
                    </div>
                  )}
                </>
              )}
            </div>
          )}

          {messages.length > 0 && (
            <div className="whatsapp-recent">
              <div className="whatsapp-recent__header">
                <strong>Mensagens recentes</strong>
                <button type="button" className="text-button" onClick={() => void loadStatus()}>
                  Atualizar
                </button>
              </div>
              <div className="whatsapp-recent__list">
                {messages.map((message) => (
                  <div className="whatsapp-recent__item" key={message.public_id}>
                    <MessageCircle size={15} />
                    <div>
                      <span>
                        <strong>{message.direction === "inbound" ? "Recebida" : "Enviada"}</strong>
                        <Badge tone={message.status === "failed" ? "danger" : "neutral"}>
                          {message.status}
                        </Badge>
                      </span>
                      <p>{message.body || `[${message.message_type}]`}</p>
                      <small>
                        {message.direction === "inbound" ? message.from_phone : message.to_phone}
                      </small>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

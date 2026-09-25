import {
  CheckCheck,
  FileText,
  Inbox,
  MessageCircle,
  RefreshCw,
  Search,
  Send,
  UserRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Button } from "../components/ui/Button";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type {
  InboxConversation,
  InboxMarkReadResult,
  InboxThread,
} from "../types/inbox";
import type {
  WhatsAppMessagePreview,
  WhatsAppMessageSendResult,
  WhatsAppTemplate,
  WhatsAppTemplatePreview,
} from "../types/settings";

function formatPhone(value: string) {
  if (value.length === 13 && value.startsWith("55")) {
    return `+55 (${value.slice(2, 4)}) ${value.slice(4, 9)}-${value.slice(9)}`;
  }
  return `+${value}`;
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function statusLabel(value: string) {
  const labels: Record<string, string> = {
    sent: "Enviada",
    delivered: "Entregue",
    read: "Lida",
    received: "Recebida",
    failed: "Falhou",
    sent_from_business_app: "Enviada pelo app",
  };
  return labels[value] ?? value.replaceAll("_", " ");
}

export function InboxPage() {
  const { workspace } = useWorkspace();
  const [conversations, setConversations] = useState<InboxConversation[]>([]);
  const [selected, setSelected] = useState<InboxConversation | null>(null);
  const [thread, setThread] = useState<InboxThread | null>(null);
  const [query, setQuery] = useState("");
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [loading, setLoading] = useState(false);
  const [threadLoading, setThreadLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const [mode, setMode] = useState<"text" | "template">("text");
  const [text, setText] = useState("");
  const [textPreview, setTextPreview] = useState<WhatsAppMessagePreview | null>(null);
  const [templates, setTemplates] = useState<WhatsAppTemplate[]>([]);
  const [templateName, setTemplateName] = useState("");
  const [templateParameters, setTemplateParameters] = useState<string[]>([]);
  const [templatePreview, setTemplatePreview] = useState<WhatsAppTemplatePreview | null>(null);
  const [sending, setSending] = useState(false);

  const currentTemplate = useMemo(
    () => templates.find((item) => item.name === templateName) ?? null,
    [templateName, templates],
  );

  const loadConversations = useCallback(async () => {
    if (!workspace) {
      setConversations([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams({ limit: "100" });
      if (query.trim()) params.set("q", query.trim());
      if (unreadOnly) params.set("unread_only", "true");
      const result = await api.get<InboxConversation[]>(
        `/workspaces/${workspace.public_id}/inbox/conversations?${params.toString()}`,
      );
      setConversations(result);
      setSelected((current) => {
        if (!current) return result[0] ?? null;
        return result.find((item) => item.conversation_key === current.conversation_key) ?? result[0] ?? null;
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível carregar a caixa de entrada.");
    } finally {
      setLoading(false);
    }
  }, [query, unreadOnly, workspace]);

  const loadThread = useCallback(async (conversation: InboxConversation | null) => {
    if (!workspace || !conversation) {
      setThread(null);
      return;
    }
    setThreadLoading(true);
    setError(null);
    try {
      const base = `/workspaces/${workspace.public_id}/inbox/conversations/whatsapp/${conversation.integration_public_id}/${conversation.contact_phone}`;
      const result = await api.get<InboxThread>(base);
      setThread(result);
      if (conversation.unread_count > 0) {
        await api.post<InboxMarkReadResult>(`${base}/read`);
        setConversations((items) => items.map((item) => (
          item.conversation_key === conversation.conversation_key
            ? { ...item, unread_count: 0 }
            : item
        )));
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível abrir a conversa.");
    } finally {
      setThreadLoading(false);
    }
  }, [workspace]);

  const loadTemplates = useCallback(async (conversation: InboxConversation | null) => {
    if (!workspace || !conversation) {
      setTemplates([]);
      return;
    }
    try {
      const result = await api.get<WhatsAppTemplate[]>(
        `/workspaces/${workspace.public_id}/integrations/${conversation.integration_public_id}/whatsapp/templates?limit=100`,
      );
      setTemplates(result.filter((item) => item.supported));
    } catch {
      setTemplates([]);
    }
  }, [workspace]);

  useEffect(() => {
    const timer = window.setTimeout(() => void loadConversations(), query ? 250 : 0);
    return () => window.clearTimeout(timer);
  }, [loadConversations, query]);

  useEffect(() => {
    setThread(null);
    setText("");
    setTextPreview(null);
    setTemplateName("");
    setTemplateParameters([]);
    setTemplatePreview(null);
    void loadThread(selected);
    void loadTemplates(selected);
  }, [loadTemplates, loadThread, selected?.conversation_key]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  useEffect(() => {
    if (!currentTemplate) {
      setTemplateParameters([]);
      return;
    }
    setTemplateParameters(Array.from({ length: currentTemplate.parameter_count }, () => ""));
    setTemplatePreview(null);
  }, [currentTemplate?.name, currentTemplate?.parameter_count]);

  async function previewTextMessage() {
    if (!workspace || !selected || !text.trim()) return;
    setSending(true);
    setError(null);
    try {
      const result = await api.post<WhatsAppMessagePreview>(
        `/workspaces/${workspace.public_id}/integrations/${selected.integration_public_id}/whatsapp/messages/preview`,
        { to: selected.contact_phone, text: text.trim() },
      );
      setTextPreview(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível preparar a mensagem.");
    } finally {
      setSending(false);
    }
  }

  async function confirmTextMessage() {
    if (!workspace || !selected || !textPreview) return;
    setSending(true);
    try {
      await api.post<WhatsAppMessageSendResult>(
        `/workspaces/${workspace.public_id}/integrations/${selected.integration_public_id}/whatsapp/messages/send`,
        {
          to: textPreview.to,
          text: textPreview.text,
          confirmation_token: textPreview.confirmation_token,
        },
      );
      setText("");
      setTextPreview(null);
      setToast("Mensagem enviada pelo WhatsApp.");
      await Promise.all([loadThread(selected), loadConversations()]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível enviar a mensagem.");
    } finally {
      setSending(false);
    }
  }

  async function previewSelectedTemplate() {
    if (!workspace || !selected || !currentTemplate) return;
    setSending(true);
    setError(null);
    try {
      const result = await api.post<WhatsAppTemplatePreview>(
        `/workspaces/${workspace.public_id}/integrations/${selected.integration_public_id}/whatsapp/templates/preview`,
        {
          to: selected.contact_phone,
          template_name: currentTemplate.name,
          language_code: currentTemplate.language,
          parameters: templateParameters,
        },
      );
      setTemplatePreview(result);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível preparar o template.");
    } finally {
      setSending(false);
    }
  }

  async function confirmTemplate() {
    if (!workspace || !selected || !templatePreview) return;
    setSending(true);
    try {
      await api.post<WhatsAppMessageSendResult>(
        `/workspaces/${workspace.public_id}/integrations/${selected.integration_public_id}/whatsapp/templates/send`,
        {
          to: templatePreview.to,
          template_name: templatePreview.template_name,
          language_code: templatePreview.language_code,
          parameters: templatePreview.parameters,
          confirmation_token: templatePreview.confirmation_token,
        },
      );
      setTemplatePreview(null);
      setToast("Template enviado pelo WhatsApp.");
      await Promise.all([loadThread(selected), loadConversations()]);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Não foi possível enviar o template.");
    } finally {
      setSending(false);
    }
  }

  return (
    <section className="inbox-page">
      <header className="page-header inbox-page__header">
        <div>
          <span className="eyebrow">Atendimento</span>
          <h1>Caixa de entrada</h1>
          <p>Conversas do WhatsApp ligadas aos leads do CRM, em ordem operacional.</p>
        </div>
        <Button variant="secondary" onClick={() => void loadConversations()} disabled={loading}>
          <RefreshCw size={16} /> Atualizar
        </Button>
      </header>

      {error && <div className="inline-alert inline-alert--danger">{error}</div>}
      {toast && <div className="toast">{toast}</div>}

      <div className="inbox-layout">
        <aside className="inbox-list-panel">
          <div className="inbox-list-panel__toolbar">
            <label className="inbox-search">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Buscar nome, número ou mensagem" />
            </label>
            <label className="inbox-unread-toggle">
              <input type="checkbox" checked={unreadOnly} onChange={(event) => setUnreadOnly(event.target.checked)} />
              <span>Somente não lidas</span>
            </label>
          </div>

          <div className="inbox-conversation-list">
            {loading && conversations.length === 0 ? (
              <div className="inbox-empty">Carregando conversas...</div>
            ) : conversations.length === 0 ? (
              <div className="inbox-empty"><Inbox size={24} /><strong>Nenhuma conversa</strong><span>As mensagens recebidas pelo WhatsApp aparecerão aqui.</span></div>
            ) : conversations.map((conversation) => (
              <button
                type="button"
                key={conversation.conversation_key}
                className={`inbox-conversation ${selected?.conversation_key === conversation.conversation_key ? "inbox-conversation--active" : ""}`}
                onClick={() => setSelected(conversation)}
              >
                <div className="inbox-conversation__avatar"><MessageCircle size={18} /></div>
                <div className="inbox-conversation__copy">
                  <div className="inbox-conversation__topline">
                    <strong>{conversation.lead_name ?? formatPhone(conversation.contact_phone)}</strong>
                    <time>{formatTime(conversation.last_message_at)}</time>
                  </div>
                  <span className="inbox-conversation__phone">{formatPhone(conversation.contact_phone)}</span>
                  <div className="inbox-conversation__preview">
                    <span>{conversation.last_message_direction === "outbound" ? "Você: " : ""}{conversation.last_message_body ?? `[${conversation.last_message_type}]`}</span>
                    {conversation.unread_count > 0 && <b>{conversation.unread_count}</b>}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </aside>

        <main className="inbox-thread-panel">
          {!selected ? (
            <div className="inbox-empty inbox-empty--thread"><MessageCircle size={30} /><strong>Selecione uma conversa</strong><span>Abra um atendimento para visualizar o histórico e responder.</span></div>
          ) : (
            <>
              <div className="inbox-thread-header">
                <div>
                  <strong>{thread?.conversation.lead_name ?? selected.lead_name ?? formatPhone(selected.contact_phone)}</strong>
                  <span>{formatPhone(selected.contact_phone)} · {selected.integration_name}</span>
                </div>
                <div className="inbox-thread-header__meta">
                  {selected.owner_name ? <span><UserRound size={14} /> {selected.owner_name}</span> : <span>Sem responsável</span>}
                  {selected.lead_status && <span className="inbox-status-chip">{selected.lead_status.replaceAll("_", " ")}</span>}
                </div>
              </div>

              <div className="inbox-messages">
                {threadLoading ? <div className="inbox-empty">Carregando histórico...</div> : thread?.messages.map((message) => (
                  <article key={message.public_id} className={`inbox-message inbox-message--${message.direction === "outbound" ? "out" : "in"}`}>
                    <div className="inbox-message__bubble">
                      <p>{message.body ?? `[${message.message_type}]`}</p>
                      <footer>
                        <time>{formatTime(message.provider_timestamp ?? message.created_at)}</time>
                        {message.direction === "outbound" && <span><CheckCheck size={13} /> {statusLabel(message.status)}</span>}
                      </footer>
                      {message.error_message && <small>{message.error_message}</small>}
                    </div>
                  </article>
                ))}
              </div>

              <div className="inbox-composer">
                <div className="inbox-composer__tabs">
                  <button type="button" className={mode === "text" ? "is-active" : ""} onClick={() => setMode("text")}><MessageCircle size={15} /> Mensagem</button>
                  <button type="button" className={mode === "template" ? "is-active" : ""} onClick={() => setMode("template")}><FileText size={15} /> Template</button>
                </div>

                {mode === "text" ? (
                  <div className="inbox-composer__body">
                    <textarea
                      value={text}
                      onChange={(event) => { setText(event.target.value); setTextPreview(null); }}
                      placeholder="Digite a resposta..."
                      maxLength={4096}
                    />
                    {textPreview && <div className="inbox-preview"><strong>Prévia para confirmação</strong><p>{textPreview.text}</p></div>}
                    <div className="inbox-composer__actions">
                      {textPreview ? (
                        <Button onClick={() => void confirmTextMessage()} disabled={sending}><Send size={16} /> Confirmar envio</Button>
                      ) : (
                        <Button onClick={() => void previewTextMessage()} disabled={sending || !text.trim()}><Send size={16} /> Preparar envio</Button>
                      )}
                    </div>
                  </div>
                ) : (
                  <div className="inbox-composer__body">
                    <select value={templateName} onChange={(event) => setTemplateName(event.target.value)}>
                      <option value="">Selecione um template aprovado</option>
                      {templates.map((item) => <option key={`${item.name}:${item.language}`} value={item.name}>{item.name} · {item.language}</option>)}
                    </select>
                    {currentTemplate?.body_text && <div className="inbox-template-source">{currentTemplate.body_text}</div>}
                    {templateParameters.map((value, index) => (
                      <input
                        key={`${currentTemplate?.name ?? "template"}-${index}`}
                        value={value}
                        onChange={(event) => {
                          const next = [...templateParameters];
                          next[index] = event.target.value;
                          setTemplateParameters(next);
                          setTemplatePreview(null);
                        }}
                        placeholder={`Valor de {{${index + 1}}}`}
                      />
                    ))}
                    {templatePreview && <div className="inbox-preview"><strong>Prévia para confirmação</strong><p>{templatePreview.rendered_text}</p></div>}
                    <div className="inbox-composer__actions">
                      {templatePreview ? (
                        <Button onClick={() => void confirmTemplate()} disabled={sending}><Send size={16} /> Confirmar template</Button>
                      ) : (
                        <Button onClick={() => void previewSelectedTemplate()} disabled={sending || !currentTemplate || templateParameters.some((item) => !item.trim())}><Send size={16} /> Preparar template</Button>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
      </div>
    </section>
  );
}

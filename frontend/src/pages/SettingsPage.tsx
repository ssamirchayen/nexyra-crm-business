import {
  ArrowDown,
  ArrowUp,
  Building2,
  Check,
  ChevronRight,
  Clipboard,
  Code2,
  Database,
  Globe2,
  Instagram,
  KeyRound,
  LayoutList,
  Loader2,
  MessageCircle,
  Palette,
  Plus,
  RefreshCw,
  Save,
  Settings2,
  SlidersHorizontal,
  Trash2,
  Webhook,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { MetaLeadAdsPanel } from "../components/integrations/MetaLeadAdsPanel";
import { WhatsAppCloudPanel } from "../components/integrations/WhatsAppCloudPanel";
import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useTheme, type Theme } from "../contexts/ThemeContext";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import {
  getReportPeriodPreference,
  REPORT_PERIOD_OPTIONS,
  setReportPeriodPreference,
  type ReportPeriod,
} from "../lib/preferences";
import type { Workspace } from "../types/dashboard";
import type {
  CommercialSettingsForm,
  CompanySettingsForm,
  IntegrationCredential,
  IntegrationOverview,
  IntegrationProvider,
  IntegrationSource,
  IntegrationSourceForm,
  SegmentDefinition,
  WorkspaceSegmentConfig,
} from "../types/settings";

type SettingsSection = "company" | "commercial" | "preferences" | "integrations";

const sectionItems: Array<{
  id: SettingsSection;
  label: string;
  description: string;
  icon: typeof Building2;
}> = [
  {
    id: "company",
    label: "Empresa",
    description: "Identidade e dados do workspace",
    icon: Building2,
  },
  {
    id: "commercial",
    label: "Operação comercial",
    description: "Segmento, pipeline e campos",
    icon: SlidersHorizontal,
  },
  {
    id: "preferences",
    label: "Preferências",
    description: "Experiência neste dispositivo",
    icon: Palette,
  },
  {
    id: "integrations",
    label: "Integrações",
    description: "Fontes, intake e conectores",
    icon: Webhook,
  },
];

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function normalizeCode(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "")
    .slice(0, 60);
}

function normalizeSlug(value: string) {
  return value
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}

function nextCode(prefix: string, values: string[]) {
  if (!values.includes(prefix)) return prefix;
  let index = 2;
  while (values.includes(`${prefix}_${index}`)) index += 1;
  return `${prefix}_${index}`;
}

function providerIcon(provider: string) {
  if (provider === "meta") return Instagram;
  if (provider === "whatsapp") return MessageCircle;
  if (provider === "website") return Globe2;
  return Code2;
}

function providerBadge(provider: IntegrationProvider) {
  if (provider.availability === "available") {
    return { tone: "success" as const, label: "Disponível" };
  }
  return { tone: "neutral" as const, label: "Conector em breve" };
}

const EMPTY_INTEGRATION_FORM: IntegrationSourceForm = {
  provider: "website",
  name: "",
  source: "website",
  channel: "form",
  default_campaign: "",
};

export function SettingsPage() {
  const { workspace, loading: workspaceLoading, refreshWorkspaces } =
    useWorkspace();
  const { theme, setTheme } = useTheme();
  const [activeSection, setActiveSection] =
    useState<SettingsSection>("company");
  const [segments, setSegments] = useState<SegmentDefinition[]>([]);
  const [companyForm, setCompanyForm] = useState<CompanySettingsForm>({
    name: "",
    slug: "",
  });
  const [commercialForm, setCommercialForm] =
    useState<CommercialSettingsForm | null>(null);
  const [integrationOverview, setIntegrationOverview] =
    useState<IntegrationOverview | null>(null);
  const [integrationForm, setIntegrationForm] =
    useState<IntegrationSourceForm>(EMPTY_INTEGRATION_FORM);
  const [savingIntegration, setSavingIntegration] = useState(false);
  const [changingIntegration, setChangingIntegration] = useState<string | null>(null);
  const [credentialBusy, setCredentialBusy] = useState<string | null>(null);
  const [generatedCredential, setGeneratedCredential] =
    useState<IntegrationCredential | null>(null);
  const [openMetaIntegrationId, setOpenMetaIntegrationId] =
    useState<string | null>(null);
  const [openWhatsAppIntegrationId, setOpenWhatsAppIntegrationId] =
    useState<string | null>(null);
  const [reportPeriod, setReportPeriod] = useState<ReportPeriod>(30);
  const [loading, setLoading] = useState(false);
  const [savingCompany, setSavingCompany] = useState(false);
  const [savingCommercial, setSavingCommercial] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const selectedSegment = useMemo(
    () =>
      segments.find((item) => item.code === commercialForm?.segment_code) ??
      null,
    [commercialForm?.segment_code, segments],
  );

  const loadSettings = useCallback(async () => {
    if (!workspace) {
      setSegments([]);
      setCommercialForm(null);
      setIntegrationOverview(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const [catalog, config, integrations] = await Promise.all([
        api.get<SegmentDefinition[]>("/segments"),
        api.get<WorkspaceSegmentConfig>(
          `/workspaces/${workspace.public_id}/segment-config`,
        ),
        api.get<IntegrationOverview>(
          `/workspaces/${workspace.public_id}/integrations/overview`,
        ),
      ]);

      setSegments(catalog);
      setIntegrationOverview(integrations);
      setCommercialForm({
        segment_code: config.segment_code,
        interest_label: config.interest_label,
        pipeline: [...config.pipeline],
        custom_fields: [...config.custom_fields],
      });
      setCompanyForm({ name: workspace.name, slug: workspace.slug });
      setReportPeriod(getReportPeriodPreference(workspace.public_id));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as configurações.",
      );
    } finally {
      setLoading(false);
    }
  }, [workspace]);

  useEffect(() => {
    void loadSettings();
  }, [loadSettings, workspace?.public_id]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function saveCompany() {
    if (!workspace) return;

    const name = companyForm.name.trim().replace(/\s+/g, " ");
    const slug = normalizeSlug(companyForm.slug);

    if (name.length < 2) {
      setError("Informe um nome de empresa válido.");
      return;
    }
    if (slug.length < 2) {
      setError("Informe um identificador válido para a empresa.");
      return;
    }

    setSavingCompany(true);
    setError(null);
    try {
      await api.patch<Workspace>(`/workspaces/${workspace.public_id}`, {
        name,
        slug,
      });
      setCompanyForm({ name, slug });
      await refreshWorkspaces();
      setToast("Dados da empresa atualizados.");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível atualizar a empresa.",
      );
    } finally {
      setSavingCompany(false);
    }
  }

  function selectSegment(code: string) {
    const definition = segments.find((item) => item.code === code);
    if (!definition) return;

    setCommercialForm({
      segment_code: definition.code,
      interest_label: definition.interest_label,
      pipeline: [...definition.pipeline],
      custom_fields: [...definition.custom_fields],
    });
  }

  function updatePipeline(index: number, value: string) {
    setCommercialForm((current) => {
      if (!current) return current;
      const pipeline = [...current.pipeline];
      pipeline[index] = value;
      return { ...current, pipeline };
    });
  }

  function normalizePipelineItem(index: number) {
    setCommercialForm((current) => {
      if (!current) return current;
      const pipeline = [...current.pipeline];
      pipeline[index] = normalizeCode(pipeline[index]);
      return { ...current, pipeline };
    });
  }

  function addPipelineStage() {
    setCommercialForm((current) => {
      if (!current) return current;
      return {
        ...current,
        pipeline: [
          ...current.pipeline,
          nextCode("nova_etapa", current.pipeline),
        ],
      };
    });
  }

  function removePipelineStage(index: number) {
    setCommercialForm((current) => {
      if (!current || current.pipeline.length <= 2) return current;
      return {
        ...current,
        pipeline: current.pipeline.filter((_, itemIndex) => itemIndex !== index),
      };
    });
  }

  function movePipelineStage(index: number, direction: -1 | 1) {
    setCommercialForm((current) => {
      if (!current) return current;
      const target = index + direction;
      if (target < 0 || target >= current.pipeline.length) return current;
      const pipeline = [...current.pipeline];
      [pipeline[index], pipeline[target]] = [pipeline[target], pipeline[index]];
      return { ...current, pipeline };
    });
  }

  function updateCustomField(index: number, value: string) {
    setCommercialForm((current) => {
      if (!current) return current;
      const customFields = [...current.custom_fields];
      customFields[index] = value;
      return { ...current, custom_fields: customFields };
    });
  }

  function normalizeCustomField(index: number) {
    setCommercialForm((current) => {
      if (!current) return current;
      const customFields = [...current.custom_fields];
      customFields[index] = normalizeCode(customFields[index]);
      return { ...current, custom_fields: customFields };
    });
  }

  function addCustomField() {
    setCommercialForm((current) => {
      if (!current || current.custom_fields.length >= 50) return current;
      return {
        ...current,
        custom_fields: [
          ...current.custom_fields,
          nextCode("novo_campo", current.custom_fields),
        ],
      };
    });
  }

  function removeCustomField(index: number) {
    setCommercialForm((current) => {
      if (!current) return current;
      return {
        ...current,
        custom_fields: current.custom_fields.filter(
          (_, itemIndex) => itemIndex !== index,
        ),
      };
    });
  }

  async function saveCommercial() {
    if (!workspace || !commercialForm) return;

    const pipeline = commercialForm.pipeline
      .map(normalizeCode)
      .filter(Boolean);
    const customFields = commercialForm.custom_fields
      .map(normalizeCode)
      .filter(Boolean);
    const interestLabel = commercialForm.interest_label.trim();

    if (pipeline.length < 2) {
      setError("O pipeline precisa ter pelo menos duas etapas.");
      return;
    }
    if (new Set(pipeline).size !== pipeline.length) {
      setError("O pipeline não pode ter etapas repetidas.");
      return;
    }
    if (new Set(customFields).size !== customFields.length) {
      setError("Os campos personalizados não podem se repetir.");
      return;
    }
    if (interestLabel.length < 2) {
      setError("Informe um nome válido para o campo de interesse.");
      return;
    }

    setSavingCommercial(true);
    setError(null);
    try {
      const saved = await api.put<WorkspaceSegmentConfig>(
        `/workspaces/${workspace.public_id}/segment-config`,
        {
          segment_code: commercialForm.segment_code,
          interest_label: interestLabel,
          pipeline,
          custom_fields: customFields,
        },
      );
      setCommercialForm({
        segment_code: saved.segment_code,
        interest_label: saved.interest_label,
        pipeline: [...saved.pipeline],
        custom_fields: [...saved.custom_fields],
      });
      await refreshWorkspaces();
      setToast("Configuração comercial atualizada.");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível atualizar a configuração comercial.",
      );
    } finally {
      setSavingCommercial(false);
    }
  }

  function changeReportPeriod(value: number) {
    if (!workspace) return;
    const period = value as ReportPeriod;
    if (!REPORT_PERIOD_OPTIONS.includes(period)) return;
    setReportPeriod(period);
    setReportPeriodPreference(workspace.public_id, period);
    setToast("Preferência salva neste dispositivo.");
  }

  function selectIntegrationProvider(providerCode: string) {
    const provider = integrationOverview?.providers.find(
      (item) => item.code === providerCode,
    );
    if (!provider) return;

    setIntegrationForm((current) => ({
      ...current,
      provider: provider.code,
      source: provider.default_source,
      channel: provider.default_channel,
      name: current.name || provider.label,
    }));
  }

  async function saveIntegrationSource() {
    if (!workspace) return;

    const name = integrationForm.name.trim().replace(/\s+/g, " ");
    const source = normalizeCode(integrationForm.source);
    const channel = normalizeCode(integrationForm.channel);
    if (name.length < 2 || source.length < 2 || channel.length < 2) {
      setError("Preencha nome, origem e canal da fonte de leads.");
      return;
    }

    setSavingIntegration(true);
    setError(null);
    try {
      await api.post<IntegrationSource>(
        `/workspaces/${workspace.public_id}/integrations`,
        {
          provider: integrationForm.provider,
          name,
          source,
          channel,
          default_campaign: integrationForm.default_campaign.trim() || null,
          routing_config: {},
          provider_config: {},
          active: true,
        },
      );
      const integrations = await api.get<IntegrationOverview>(
        `/workspaces/${workspace.public_id}/integrations/overview`,
      );
      setIntegrationOverview(integrations);
      const provider = integrations.providers.find(
        (item) => item.code === integrationForm.provider,
      );
      setIntegrationForm({
        provider: provider?.code ?? "website",
        name: "",
        source: provider?.default_source ?? "website",
        channel: provider?.default_channel ?? "form",
        default_campaign: "",
      });
      setToast("Fonte de leads configurada.");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível configurar a fonte de leads.",
      );
    } finally {
      setSavingIntegration(false);
    }
  }

  async function toggleIntegrationSource(item: IntegrationSource) {
    if (!workspace) return;
    setChangingIntegration(item.public_id);
    setError(null);
    try {
      await api.post<IntegrationSource>(
        `/workspaces/${workspace.public_id}/integrations/${item.public_id}/${
          item.active ? "deactivate" : "activate"
        }`,
      );
      const integrations = await api.get<IntegrationOverview>(
        `/workspaces/${workspace.public_id}/integrations/overview`,
      );
      setIntegrationOverview(integrations);
      setToast(item.active ? "Fonte desativada." : "Fonte ativada.");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível alterar a fonte.",
      );
    } finally {
      setChangingIntegration(null);
    }
  }

  async function copyIntakeEndpoint() {
    if (!integrationOverview) return;
    const endpoint = `/api/v1${integrationOverview.intake_endpoint}`;
    try {
      await navigator.clipboard.writeText(endpoint);
      setToast("Endpoint de intake copiado.");
    } catch {
      setToast(endpoint);
    }
  }

  function externalIntakeEndpoint(item: IntegrationSource) {
    return `/api/v1/external/integrations/${item.public_id}/intake`;
  }

  async function copySourceIntakeEndpoint(item: IntegrationSource) {
    const endpoint = externalIntakeEndpoint(item);
    try {
      await navigator.clipboard.writeText(endpoint);
      setToast("Endpoint externo da fonte copiado.");
    } catch {
      setToast(endpoint);
    }
  }

  async function rotateExternalCredential(item: IntegrationSource) {
    if (!workspace) return;
    setCredentialBusy(item.public_id);
    setError(null);
    try {
      const credential = await api.post<IntegrationCredential>(
        `/workspaces/${workspace.public_id}/integrations/${item.public_id}/external-key/rotate`,
      );
      setGeneratedCredential(credential);
      const integrations = await api.get<IntegrationOverview>(
        `/workspaces/${workspace.public_id}/integrations/overview`,
      );
      setIntegrationOverview(integrations);
      setToast(
        item.external_intake_enabled
          ? "Chave externa rotacionada. A chave anterior deixou de funcionar."
          : "Entrada externa habilitada para esta fonte.",
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível gerar a chave externa.",
      );
    } finally {
      setCredentialBusy(null);
    }
  }

  async function revokeExternalCredential(item: IntegrationSource) {
    if (!workspace) return;
    setCredentialBusy(item.public_id);
    setError(null);
    try {
      await api.delete<IntegrationSource>(
        `/workspaces/${workspace.public_id}/integrations/${item.public_id}/external-key`,
      );
      const integrations = await api.get<IntegrationOverview>(
        `/workspaces/${workspace.public_id}/integrations/overview`,
      );
      setIntegrationOverview(integrations);
      if (generatedCredential?.integration_public_id === item.public_id) {
        setGeneratedCredential(null);
      }
      setToast("Chave externa revogada.");
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível revogar a chave externa.",
      );
    } finally {
      setCredentialBusy(null);
    }
  }

  async function copyCredentialValue(value: string, message: string) {
    try {
      await navigator.clipboard.writeText(value);
      setToast(message);
    } catch {
      setToast(value);
    }
  }

  if (workspaceLoading) {
    return <div className="page-state">Carregando empresa...</div>;
  }

  if (!workspace) {
    return (
      <div className="page-state page-state--empty">
        <Settings2 size={28} />
        <strong>Nenhuma empresa selecionada</strong>
        <span>Selecione uma empresa para abrir as configurações.</span>
      </div>
    );
  }

  return (
    <div className="page-stack settings-page">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Configurações</p>
          <h1>Administração do CRM</h1>
          <p>Empresa, operação comercial, preferências e integrações.</p>
        </div>
        <Button variant="secondary" onClick={() => void loadSettings()} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          Atualizar
        </Button>
      </header>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <button type="button" className="text-button" onClick={() => setError(null)}>
            Fechar
          </button>
        </div>
      )}

      <div className="settings-layout">
        <aside className="settings-nav" aria-label="Seções de configurações">
          <div className="settings-nav__workspace">
            <div className="settings-nav__workspace-icon">
              <Building2 size={18} />
            </div>
            <div>
              <strong>{workspace.name}</strong>
              <span>{workspace.public_id}</span>
            </div>
          </div>

          <div className="settings-nav__items">
            {sectionItems.map(({ id, label, description, icon: Icon }) => (
              <button
                key={id}
                type="button"
                className={`settings-nav__item ${activeSection === id ? "settings-nav__item--active" : ""}`}
                onClick={() => setActiveSection(id)}
              >
                <Icon size={17} />
                <span>
                  <strong>{label}</strong>
                  <small>{description}</small>
                </span>
                <ChevronRight size={14} />
              </button>
            ))}
          </div>
        </aside>

        <main className="settings-content">
          {loading ? (
            <div className="settings-loading">
              <Loader2 size={20} className="spin" />
              Carregando configurações...
            </div>
          ) : null}

          {!loading && activeSection === "company" && (
            <div className="settings-section-stack">
              <Card
                title="Empresa e workspace"
                description="Identidade usada em todo o Nexyra CRM."
                actions={
                  <Badge tone={workspace.active ? "success" : "neutral"}>
                    {workspace.active ? "Ativa" : "Inativa"}
                  </Badge>
                }
              >
                <div className="settings-card-body">
                  <div className="settings-info-strip">
                    <Database size={17} />
                    <div>
                      <strong>Workspace multiempresa</strong>
                      <span>
                        Leads, oportunidades, atividades e equipe permanecem isolados nesta empresa.
                      </span>
                    </div>
                  </div>

                  <div className="form-grid form-grid--2 settings-form-grid">
                    <label className="field">
                      <span>Nome da empresa</span>
                      <input
                        value={companyForm.name}
                        maxLength={160}
                        onChange={(event) =>
                          setCompanyForm((current) => ({
                            ...current,
                            name: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>Identificador (slug)</span>
                      <input
                        value={companyForm.slug}
                        maxLength={100}
                        onBlur={() =>
                          setCompanyForm((current) => ({
                            ...current,
                            slug: normalizeSlug(current.slug),
                          }))
                        }
                        onChange={(event) =>
                          setCompanyForm((current) => ({
                            ...current,
                            slug: event.target.value,
                          }))
                        }
                      />
                    </label>
                    <label className="field">
                      <span>ID público</span>
                      <input value={workspace.public_id} readOnly />
                    </label>
                    <label className="field">
                      <span>Segmento atual</span>
                      <input value={selectedSegment?.label ?? labelize(workspace.segment)} readOnly />
                    </label>
                  </div>
                </div>
                <div className="settings-card-footer">
                  <span>Alterações de nome e slug são registradas na auditoria.</span>
                  <Button onClick={() => void saveCompany()} disabled={savingCompany}>
                    {savingCompany ? <Loader2 size={15} className="spin" /> : <Save size={15} />}
                    Salvar empresa
                  </Button>
                </div>
              </Card>

            </div>
          )}

          {!loading && activeSection === "commercial" && commercialForm && (
            <div className="settings-section-stack">
              <Card
                title="Modelo comercial"
                description="Escolha o segmento e defina como o CRM representa o interesse do cliente."
              >
                <div className="settings-card-body">
                  <div className="form-grid form-grid--2 settings-form-grid">
                    <label className="field">
                      <span>Segmento</span>
                      <select
                        value={commercialForm.segment_code}
                        onChange={(event) => selectSegment(event.target.value)}
                      >
                        {segments.map((segment) => (
                          <option key={segment.code} value={segment.code}>
                            {segment.label}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label className="field">
                      <span>Nome do interesse principal</span>
                      <input
                        value={commercialForm.interest_label}
                        maxLength={80}
                        onChange={(event) =>
                          setCommercialForm((current) =>
                            current
                              ? { ...current, interest_label: event.target.value }
                              : current,
                          )
                        }
                      />
                    </label>
                  </div>
                  {selectedSegment && (
                    <div className="settings-template-note">
                      <Check size={16} />
                      <span>
                        Modelo <strong>{selectedSegment.label}</strong> selecionado. Ao trocar o segmento, pipeline e campos são carregados com o padrão do novo modelo antes de você salvar.
                      </span>
                    </div>
                  )}
                </div>
              </Card>

              <Card
                title="Pipeline"
                description="Ordem das etapas usadas por leads e oportunidades nesta empresa."
                actions={
                  <Button variant="secondary" onClick={addPipelineStage}>
                    <Plus size={14} />
                    Nova etapa
                  </Button>
                }
              >
                <div className="settings-list-editor">
                  {commercialForm.pipeline.map((stage, index) => (
                    <div className="settings-list-row" key={`${stage}-${index}`}>
                      <span className="settings-list-row__number">{index + 1}</span>
                      <div className="settings-list-row__main">
                        <input
                          aria-label={`Etapa ${index + 1}`}
                          value={stage}
                          onBlur={() => normalizePipelineItem(index)}
                          onChange={(event) => updatePipeline(index, event.target.value)}
                        />
                        <small>{labelize(normalizeCode(stage) || stage)}</small>
                      </div>
                      <div className="settings-list-row__actions">
                        <button
                          type="button"
                          className="table-action-button"
                          aria-label="Mover etapa para cima"
                          disabled={index === 0}
                          onClick={() => movePipelineStage(index, -1)}
                        >
                          <ArrowUp size={14} />
                        </button>
                        <button
                          type="button"
                          className="table-action-button"
                          aria-label="Mover etapa para baixo"
                          disabled={index === commercialForm.pipeline.length - 1}
                          onClick={() => movePipelineStage(index, 1)}
                        >
                          <ArrowDown size={14} />
                        </button>
                        <button
                          type="button"
                          className="table-action-button table-action-button--danger"
                          aria-label="Remover etapa"
                          disabled={commercialForm.pipeline.length <= 2}
                          onClick={() => removePipelineStage(index)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>

              <Card
                title="Campos personalizados"
                description="Dados extras permitidos nos leads deste workspace."
                actions={
                  <Button variant="secondary" onClick={addCustomField} disabled={commercialForm.custom_fields.length >= 50}>
                    <Plus size={14} />
                    Novo campo
                  </Button>
                }
              >
                {commercialForm.custom_fields.length === 0 ? (
                  <div className="settings-inline-empty">
                    <LayoutList size={19} />
                    <div>
                      <strong>Nenhum campo extra</strong>
                      <span>O CRM continuará usando apenas os campos principais do lead.</span>
                    </div>
                  </div>
                ) : (
                  <div className="settings-fields-grid">
                    {commercialForm.custom_fields.map((field, index) => (
                      <div className="settings-field-item" key={`${field}-${index}`}>
                        <div>
                          <span>Campo {index + 1}</span>
                          <input
                            value={field}
                            onBlur={() => normalizeCustomField(index)}
                            onChange={(event) => updateCustomField(index, event.target.value)}
                          />
                          <small>{labelize(normalizeCode(field) || field)}</small>
                        </div>
                        <button
                          type="button"
                          className="table-action-button table-action-button--danger"
                          aria-label="Remover campo"
                          onClick={() => removeCustomField(index)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </Card>

              <div className="settings-save-bar">
                <div>
                  <strong>Configuração comercial</strong>
                  <span>Salvar atualiza o segmento, pipeline e campos do workspace.</span>
                </div>
                <Button onClick={() => void saveCommercial()} disabled={savingCommercial}>
                  {savingCommercial ? <Loader2 size={15} className="spin" /> : <Save size={15} />}
                  Salvar operação
                </Button>
              </div>
            </div>
          )}

          {!loading && activeSection === "preferences" && (
            <div className="settings-section-stack">
              <Card
                title="Preferências do aplicativo"
                description="Ajustes locais desta instalação do Nexyra CRM."
              >
                <div className="settings-preference-list">
                  <div className="settings-preference-row">
                    <div className="settings-preference-icon"><Palette size={18} /></div>
                    <div className="settings-preference-copy">
                      <strong>Aparência</strong>
                      <span>Escolha o tema da interface neste dispositivo.</span>
                    </div>
                    <select
                      value={theme}
                      onChange={(event) => setTheme(event.target.value as Theme)}
                    >
                      <option value="light">Claro</option>
                      <option value="dark">Escuro</option>
                    </select>
                  </div>
                  <div className="settings-preference-row">
                    <div className="settings-preference-icon"><LayoutList size={18} /></div>
                    <div className="settings-preference-copy">
                      <strong>Período padrão dos relatórios</strong>
                      <span>A tela de Analytics abrirá usando este período para esta empresa.</span>
                    </div>
                    <select
                      value={reportPeriod}
                      onChange={(event) => changeReportPeriod(Number(event.target.value))}
                    >
                      {REPORT_PERIOD_OPTIONS.map((period) => (
                        <option key={period} value={period}>
                          {period} dias
                        </option>
                      ))}
                    </select>
                  </div>
                </div>
                <div className="settings-local-note">
                  <Settings2 size={16} />
                  <span>
                    Essas preferências são da interface e ficam salvas neste dispositivo. Configurações comerciais permanecem no banco do CRM.
                  </span>
                </div>
              </Card>
            </div>
          )}

          {!loading && activeSection === "integrations" && (
            <div className="settings-section-stack">
              <div className="settings-integration-intro">
                <div>
                  <Webhook size={19} />
                  <span>
                    <strong>Central de integrações e fontes de leads</strong>
                    <small>
                      Cadastre as origens do workspace e receba leads externos por API, webhook ou formulários com chave própria por fonte. Meta Lead Ads e WhatsApp Cloud API possuem conectores oficiais.
                    </small>
                  </span>
                </div>
                <Badge tone="info">
                  {integrationOverview?.active_sources ?? 0} fontes ativas
                </Badge>
              </div>

              <div className="settings-integrations-grid">
                {(integrationOverview?.providers ?? []).map((provider) => {
                  const Icon = providerIcon(provider.code);
                  const badge = providerBadge(provider);
                  return (
                    <article className="integration-card" key={provider.code}>
                      <div className="integration-card__top">
                        <div className="integration-card__icon"><Icon size={19} /></div>
                        <Badge tone={badge.tone}>{badge.label}</Badge>
                      </div>
                      <strong>{provider.label}</strong>
                      <p>{provider.description}</p>
                      {provider.code === "api_intake" ? (
                        <button
                          type="button"
                          className="integration-endpoint"
                          onClick={() => void copyIntakeEndpoint()}
                        >
                          <code>{integrationOverview?.intake_endpoint ?? "/leads/intake"}</code>
                          <Clipboard size={13} />
                        </button>
                      ) : (
                        <span className="integration-card__footer">
                          {provider.default_source} · {provider.default_channel}
                        </span>
                      )}
                    </article>
                  );
                })}
              </div>

              <Card
                title="Nova fonte de leads"
                description="Configure a identificação padrão usada pelos leads recebidos desta origem."
              >
                <div className="integration-source-form">
                  <label>
                    <span>Tipo de integração</span>
                    <select
                      value={integrationForm.provider}
                      onChange={(event) => selectIntegrationProvider(event.target.value)}
                    >
                      {(integrationOverview?.providers ?? []).map((provider) => (
                        <option key={provider.code} value={provider.code}>
                          {provider.label}{provider.availability === "connector_pending" ? " (preparação)" : ""}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label>
                    <span>Nome da fonte</span>
                    <input
                      value={integrationForm.name}
                      placeholder="Ex.: Landing Page Black Friday"
                      onChange={(event) =>
                        setIntegrationForm((current) => ({
                          ...current,
                          name: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    <span>Source</span>
                    <input
                      value={integrationForm.source}
                      onBlur={() =>
                        setIntegrationForm((current) => ({
                          ...current,
                          source: normalizeCode(current.source),
                        }))
                      }
                      onChange={(event) =>
                        setIntegrationForm((current) => ({
                          ...current,
                          source: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label>
                    <span>Channel</span>
                    <input
                      value={integrationForm.channel}
                      onBlur={() =>
                        setIntegrationForm((current) => ({
                          ...current,
                          channel: normalizeCode(current.channel),
                        }))
                      }
                      onChange={(event) =>
                        setIntegrationForm((current) => ({
                          ...current,
                          channel: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <label className="integration-source-form__campaign">
                    <span>Campanha padrão</span>
                    <input
                      value={integrationForm.default_campaign}
                      placeholder="Opcional"
                      onChange={(event) =>
                        setIntegrationForm((current) => ({
                          ...current,
                          default_campaign: event.target.value,
                        }))
                      }
                    />
                  </label>
                  <div className="integration-source-form__action">
                    <Button
                      onClick={() => void saveIntegrationSource()}
                      disabled={savingIntegration}
                    >
                      {savingIntegration ? (
                        <Loader2 size={15} className="spin" />
                      ) : (
                        <Plus size={15} />
                      )}
                      Adicionar fonte
                    </Button>
                  </div>
                </div>
              </Card>

              {generatedCredential && (
                <div className="integration-credential-panel">
                  <div className="integration-credential-panel__title">
                    <KeyRound size={18} />
                    <span>
                      <strong>Chave externa gerada</strong>
                      <small>
                        Copie agora. Por segurança, o CRM salva somente o hash e não consegue mostrar esta chave novamente.
                      </small>
                    </span>
                  </div>
                  <div className="integration-credential-panel__fields">
                    <div>
                      <span>Endpoint</span>
                      <code>/api/v1{generatedCredential.intake_endpoint}</code>
                      <button
                        type="button"
                        className="table-action-button"
                        aria-label="Copiar endpoint externo"
                        onClick={() =>
                          void copyCredentialValue(
                            `/api/v1${generatedCredential.intake_endpoint}`,
                            "Endpoint externo copiado.",
                          )
                        }
                      >
                        <Clipboard size={14} />
                      </button>
                    </div>
                    <div>
                      <span>{generatedCredential.header_name}</span>
                      <code>{generatedCredential.intake_key}</code>
                      <button
                        type="button"
                        className="table-action-button"
                        aria-label="Copiar chave externa"
                        onClick={() =>
                          void copyCredentialValue(
                            generatedCredential.intake_key,
                            "Chave externa copiada.",
                          )
                        }
                      >
                        <Clipboard size={14} />
                      </button>
                    </div>
                  </div>
                  <div className="integration-credential-panel__footer">
                    <code>X-Idempotency-Key: opcional</code>
                    <Button
                      variant="secondary"
                      onClick={() => setGeneratedCredential(null)}
                    >
                      Já copiei
                    </Button>
                  </div>
                </div>
              )}

              <Card
                title="Fontes configuradas"
                description="Origens cadastradas para este workspace. Desativar uma fonte preserva o histórico existente."
              >
                {(integrationOverview?.sources ?? []).length === 0 ? (
                  <div className="integration-empty-state">
                    <Database size={20} />
                    <span>
                      <strong>Nenhuma fonte cadastrada</strong>
                      <small>Adicione uma fonte acima para começar a padronizar a captação.</small>
                    </span>
                  </div>
                ) : (
                  <div className="integration-source-list">
                    {(integrationOverview?.sources ?? []).map((item) => {
                      const provider = integrationOverview?.providers.find(
                        (candidate) => candidate.code === item.provider,
                      );
                      return (
                        <div className="integration-source-row" key={item.public_id}>
                          <div className="integration-source-row__status">
                            <span className={item.active ? "status-dot status-dot--success" : "status-dot"} />
                          </div>
                          <div className="integration-source-row__main">
                            <strong>{item.name}</strong>
                            <span>
                              {provider?.label ?? item.provider} · {item.source} / {item.channel}
                            </span>
                          </div>
                          <div className="integration-source-row__campaign">
                            <span>Campanha</span>
                            <strong>{item.default_campaign || "—"}</strong>
                          </div>
                          <div className="integration-source-row__external">
                            <span>Entrada externa</span>
                            <strong>
                              {provider?.capabilities.includes("meta_lead_ads")
                                ? `${item.intake_count} recebidos via Meta`
                                : provider?.capabilities.includes("whatsapp_cloud")
                                  ? `${item.intake_count} recebidos via WhatsApp`
                                  : item.external_intake_enabled
                                  ? `${item.intake_count} recebidos · ${item.intake_key_prefix ?? "chave ativa"}`
                                  : provider?.capabilities.includes("external_intake")
                                    ? "Não configurada"
                                    : "Indisponível"}
                            </strong>
                          </div>
                          <Badge tone={item.active ? "success" : "neutral"}>
                            {item.active ? "Ativa" : "Inativa"}
                          </Badge>
                          <div className="integration-source-row__actions">
                            {provider?.capabilities.includes("meta_lead_ads") && (
                              <Button
                                variant="secondary"
                                onClick={() =>
                                  setOpenMetaIntegrationId((current) =>
                                    current === item.public_id ? null : item.public_id,
                                  )
                                }
                              >
                                <Instagram size={14} />
                                {openMetaIntegrationId === item.public_id
                                  ? "Fechar Meta"
                                  : "Configurar Meta"}
                              </Button>
                            )}
                            {provider?.capabilities.includes("whatsapp_cloud") && (
                              <Button
                                variant="secondary"
                                onClick={() =>
                                  setOpenWhatsAppIntegrationId((current) =>
                                    current === item.public_id ? null : item.public_id,
                                  )
                                }
                              >
                                <MessageCircle size={14} />
                                {openWhatsAppIntegrationId === item.public_id
                                  ? "Fechar WhatsApp"
                                  : "Configurar WhatsApp"}
                              </Button>
                            )}
                            {provider?.capabilities.includes("external_intake") && (
                              <>
                                <button
                                  type="button"
                                  className="table-action-button"
                                  aria-label="Copiar endpoint externo"
                                  title="Copiar endpoint externo"
                                  onClick={() => void copySourceIntakeEndpoint(item)}
                                >
                                  <Clipboard size={14} />
                                </button>
                                <Button
                                  variant="secondary"
                                  disabled={credentialBusy === item.public_id}
                                  onClick={() => void rotateExternalCredential(item)}
                                >
                                  {credentialBusy === item.public_id ? (
                                    <Loader2 size={14} className="spin" />
                                  ) : (
                                    <KeyRound size={14} />
                                  )}
                                  {item.external_intake_enabled ? "Rotacionar chave" : "Gerar chave"}
                                </Button>
                                {item.external_intake_enabled && (
                                  <button
                                    type="button"
                                    className="table-action-button table-action-button--danger"
                                    aria-label="Revogar chave externa"
                                    title="Revogar chave externa"
                                    disabled={credentialBusy === item.public_id}
                                    onClick={() => void revokeExternalCredential(item)}
                                  >
                                    <Trash2 size={14} />
                                  </button>
                                )}
                              </>
                            )}
                            <Button
                              variant="secondary"
                              disabled={changingIntegration === item.public_id}
                              onClick={() => void toggleIntegrationSource(item)}
                            >
                              {changingIntegration === item.public_id ? (
                                <Loader2 size={14} className="spin" />
                              ) : item.active ? (
                                "Desativar"
                              ) : (
                                "Ativar"
                              )}
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </Card>

              {openMetaIntegrationId && workspace && (() => {
                const metaSource = (integrationOverview?.sources ?? []).find(
                  (item) => item.public_id === openMetaIntegrationId && item.provider === "meta",
                );
                if (!metaSource) return null;
                return (
                  <MetaLeadAdsPanel
                    workspacePublicId={workspace.public_id}
                    source={metaSource}
                    onToast={setToast}
                    onError={setError}
                  />
                );
              })()}

              {openWhatsAppIntegrationId && workspace && (() => {
                const whatsAppSource = (integrationOverview?.sources ?? []).find(
                  (item) =>
                    item.public_id === openWhatsAppIntegrationId &&
                    item.provider === "whatsapp",
                );
                if (!whatsAppSource) return null;
                return (
                  <WhatsAppCloudPanel
                    workspacePublicId={workspace.public_id}
                    source={whatsAppSource}
                    onToast={setToast}
                    onError={setError}
                  />
                );
              })()}
            </div>
          )}
        </main>
      </div>

      {toast && <div className="toast toast--success">{toast}</div>}
    </div>
  );
}

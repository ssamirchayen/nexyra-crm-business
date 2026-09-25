import {
  Bot,
  Check,
  LoaderCircle,
  Play,
  Plus,
  RefreshCw,
  Trash2,
  UsersRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { api } from "../../lib/api";
import type {
  LeadDistributionConfig,
  LeadDistributionRule,
  LeadDistributionRunResult,
  LeadDistributionSummary,
  LeadDistributionStrategy,
} from "../../types/leadDistribution";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

const PRIORITIES = ["baixa", "media", "alta", "urgente"];
const ROLES = [
  ["seller", "Vendedor"],
  ["operator", "Operador"],
  ["manager", "Gerente"],
  ["admin", "Administrador"],
] as const;

const emptyRule = (): LeadDistributionRule => ({
  name: "Nova regra",
  enabled: true,
  source: null,
  channel: null,
  interest_contains: null,
  campaign_contains: null,
  priorities: [],
  eligible_user_public_ids: [],
  strategy: null,
});

type Props = {
  open: boolean;
  workspacePublicId: string;
  onClose: () => void;
  onChanged: () => void;
};

function strategyLabel(strategy: LeadDistributionStrategy) {
  return strategy === "least_loaded" ? "Menor carga" : "Round-robin";
}

export function LeadDistributionModal({
  open,
  workspacePublicId,
  onClose,
  onChanged,
}: Props) {
  const [summary, setSummary] = useState<LeadDistributionSummary | null>(null);
  const [config, setConfig] = useState<LeadDistributionConfig | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState<"preview" | "execute" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<LeadDistributionRunResult | null>(null);

  const load = useCallback(async () => {
    if (!open) return;
    setLoading(true);
    setError(null);
    try {
      const payload = await api.get<LeadDistributionSummary>(
        `/workspaces/${workspacePublicId}/lead-distribution/summary`,
      );
      setSummary(payload);
      setConfig(payload.config);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar a distribuição de leads.",
      );
    } finally {
      setLoading(false);
    }
  }, [open, workspacePublicId]);

  useEffect(() => {
    if (open) {
      setNotice(null);
      setRunResult(null);
      void load();
    }
  }, [load, open]);

  const activeMembers = useMemo(
    () => summary?.members.filter((member) => member.active) ?? [],
    [summary],
  );

  function updateConfig(patch: Partial<LeadDistributionConfig>) {
    setConfig((current) => (current ? { ...current, ...patch } : current));
  }

  function updateRule(index: number, patch: Partial<LeadDistributionRule>) {
    setConfig((current) => {
      if (!current) return current;
      const rules = current.rules.map((rule, ruleIndex) =>
        ruleIndex === index ? { ...rule, ...patch } : rule,
      );
      return { ...current, rules };
    });
  }

  function toggleRole(role: string) {
    if (!config) return;
    const exists = config.eligible_roles.includes(role);
    const roles = exists
      ? config.eligible_roles.filter((item) => item !== role)
      : [...config.eligible_roles, role];
    if (roles.length > 0) updateConfig({ eligible_roles: roles });
  }

  function toggleUser(userPublicId: string) {
    if (!config) return;
    const exists = config.eligible_user_public_ids.includes(userPublicId);
    updateConfig({
      eligible_user_public_ids: exists
        ? config.eligible_user_public_ids.filter((item) => item !== userPublicId)
        : [...config.eligible_user_public_ids, userPublicId],
    });
  }

  function toggleRulePriority(index: number, priority: string) {
    const rule = config?.rules[index];
    if (!rule) return;
    updateRule(index, {
      priorities: rule.priorities.includes(priority)
        ? rule.priorities.filter((item) => item !== priority)
        : [...rule.priorities, priority],
    });
  }

  async function save() {
    if (!config) return;
    setSaving(true);
    setError(null);
    try {
      const saved = await api.put<LeadDistributionConfig>(
        `/workspaces/${workspacePublicId}/lead-distribution/config`,
        config,
      );
      setConfig(saved);
      setNotice("Configuração de distribuição salva.");
      await load();
      onChanged();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível salvar a distribuição.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function run(dryRun: boolean) {
    if (!config?.enabled) {
      setError("Ative e salve a distribuição automática antes de executar a fila.");
      return;
    }
    setRunning(dryRun ? "preview" : "execute");
    setError(null);
    setNotice(null);
    try {
      const result = await api.post<LeadDistributionRunResult>(
        `/workspaces/${workspacePublicId}/lead-distribution/run`,
        { limit: 100, dry_run: dryRun },
      );
      setRunResult(result);
      setNotice(
        dryRun
          ? `Simulação: ${result.assigned} lead(s) receberiam responsável.`
          : `Distribuição concluída: ${result.assigned} lead(s) atribuído(s).`,
      );
      if (!dryRun) {
        await load();
        onChanged();
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível executar a distribuição.",
      );
    } finally {
      setRunning(null);
    }
  }

  return (
    <Modal
      open={open}
      title="Distribuição inteligente de leads"
      description="Direcione novas entradas automaticamente e equilibre a carga comercial."
      onClose={onClose}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose} disabled={saving || Boolean(running)}>
            Fechar
          </Button>
          <Button onClick={() => void save()} disabled={!config || saving || Boolean(running)}>
            {saving ? "Salvando..." : "Salvar configuração"}
          </Button>
        </>
      }
    >
      {loading && !config ? (
        <div className="distribution-loading">
          <LoaderCircle className="spin" size={20} />
          Carregando distribuição...
        </div>
      ) : config ? (
        <div className="distribution-stack">
          {error && <div className="page-alert page-alert--error">{error}</div>}
          {notice && <div className="page-alert page-alert--success">{notice}</div>}

          <div className="distribution-summary-grid">
            <div className="distribution-stat">
              <span>Leads ativos</span>
              <strong>{summary?.total_active_leads ?? 0}</strong>
            </div>
            <div className="distribution-stat">
              <span>Sem responsável</span>
              <strong>{summary?.unassigned_active_leads ?? 0}</strong>
            </div>
            <div className="distribution-stat">
              <span>Estratégia</span>
              <strong>{strategyLabel(config.strategy)}</strong>
            </div>
          </div>

          <section className="distribution-section">
            <div className="distribution-section__title">
              <div>
                <span className="distribution-icon"><Bot size={17} /></span>
                <div>
                  <strong>Automação</strong>
                  <p>Entradas sem responsável passam pelo motor de distribuição.</p>
                </div>
              </div>
              <label className="distribution-switch">
                <input
                  type="checkbox"
                  checked={config.enabled}
                  onChange={(event) => updateConfig({ enabled: event.target.checked })}
                />
                <span>{config.enabled ? "Ativa" : "Desativada"}</span>
              </label>
            </div>

            <div className="distribution-field-grid">
              <label>
                Estratégia padrão
                <select
                  value={config.strategy}
                  onChange={(event) =>
                    updateConfig({ strategy: event.target.value as LeadDistributionStrategy })
                  }
                >
                  <option value="least_loaded">Menor carga atual</option>
                  <option value="round_robin">Round-robin</option>
                </select>
              </label>
              <div className="distribution-help">
                <strong>Menor carga</strong> usa a quantidade atual de leads ativos. Round-robin alterna os consultores elegíveis.
              </div>
            </div>
          </section>

          <section className="distribution-section">
            <div className="distribution-section__title">
              <div>
                <span className="distribution-icon"><UsersRound size={17} /></span>
                <div>
                  <strong>Equipe elegível</strong>
                  <p>Defina quais perfis e pessoas podem receber leads automaticamente.</p>
                </div>
              </div>
            </div>

            <div className="distribution-role-list">
              {ROLES.map(([role, label]) => (
                <label key={role} className="distribution-chip">
                  <input
                    type="checkbox"
                    checked={config.eligible_roles.includes(role)}
                    onChange={() => toggleRole(role)}
                  />
                  {label}
                </label>
              ))}
            </div>

            <p className="distribution-caption">
              Se nenhuma pessoa for marcada abaixo, todos os membros ativos dos perfis selecionados participam.
            </p>
            <div className="distribution-member-list">
              {activeMembers.map((member) => (
                <label key={member.user_public_id} className="distribution-member-row">
                  <input
                    type="checkbox"
                    checked={config.eligible_user_public_ids.includes(member.user_public_id)}
                    onChange={() => toggleUser(member.user_public_id)}
                  />
                  <div>
                    <strong>{member.name}</strong>
                    <span>{member.role}</span>
                  </div>
                  <b>{member.assigned_active_leads} ativo(s)</b>
                </label>
              ))}
            </div>
          </section>

          <section className="distribution-section">
            <div className="distribution-section__title distribution-section__title--action">
              <div>
                <div>
                  <strong>Regras de direcionamento</strong>
                  <p>O primeiro critério compatível pode restringir os consultores e trocar a estratégia.</p>
                </div>
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => updateConfig({ rules: [...config.rules, emptyRule()] })}
              >
                <Plus size={15} />
                Nova regra
              </Button>
            </div>

            {config.rules.length === 0 ? (
              <div className="distribution-empty-rule">
                Sem regras específicas. Todos os leads usam a estratégia padrão.
              </div>
            ) : (
              <div className="distribution-rules">
                {config.rules.map((rule, index) => (
                  <div className="distribution-rule" key={`${index}-${rule.name}`}>
                    <div className="distribution-rule__header">
                      <input
                        value={rule.name}
                        onChange={(event) => updateRule(index, { name: event.target.value })}
                        aria-label="Nome da regra"
                      />
                      <label className="distribution-chip">
                        <input
                          type="checkbox"
                          checked={rule.enabled}
                          onChange={(event) => updateRule(index, { enabled: event.target.checked })}
                        />
                        Ativa
                      </label>
                      <Button
                        type="button"
                        variant="ghost"
                        onClick={() =>
                          updateConfig({
                            rules: config.rules.filter((_, ruleIndex) => ruleIndex !== index),
                          })
                        }
                        aria-label="Remover regra"
                      >
                        <Trash2 size={15} />
                      </Button>
                    </div>
                    <div className="distribution-field-grid distribution-field-grid--rules">
                      <label>
                        Origem
                        <input
                          placeholder="Ex.: instagram"
                          value={rule.source ?? ""}
                          onChange={(event) => updateRule(index, { source: event.target.value || null })}
                        />
                      </label>
                      <label>
                        Canal
                        <input
                          placeholder="Ex.: social"
                          value={rule.channel ?? ""}
                          onChange={(event) => updateRule(index, { channel: event.target.value || null })}
                        />
                      </label>
                      <label>
                        Curso / interesse contém
                        <input
                          placeholder="Ex.: Radiologia"
                          value={rule.interest_contains ?? ""}
                          onChange={(event) =>
                            updateRule(index, { interest_contains: event.target.value || null })
                          }
                        />
                      </label>
                      <label>
                        Campanha contém
                        <input
                          placeholder="Ex.: setembro"
                          value={rule.campaign_contains ?? ""}
                          onChange={(event) =>
                            updateRule(index, { campaign_contains: event.target.value || null })
                          }
                        />
                      </label>
                      <label>
                        Estratégia da regra
                        <select
                          value={rule.strategy ?? ""}
                          onChange={(event) =>
                            updateRule(index, {
                              strategy: (event.target.value || null) as LeadDistributionStrategy | null,
                            })
                          }
                        >
                          <option value="">Usar padrão</option>
                          <option value="least_loaded">Menor carga</option>
                          <option value="round_robin">Round-robin</option>
                        </select>
                      </label>
                      <label>
                        Destino preferencial
                        <select
                          value={rule.eligible_user_public_ids[0] ?? ""}
                          onChange={(event) =>
                            updateRule(index, {
                              eligible_user_public_ids: event.target.value ? [event.target.value] : [],
                            })
                          }
                        >
                          <option value="">Equipe elegível</option>
                          {activeMembers.map((member) => (
                            <option key={member.user_public_id} value={member.user_public_id}>
                              {member.name}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <div className="distribution-priorities">
                      <span>Prioridades:</span>
                      {PRIORITIES.map((priority) => (
                        <label key={priority} className="distribution-chip">
                          <input
                            type="checkbox"
                            checked={rule.priorities.includes(priority)}
                            onChange={() => toggleRulePriority(index, priority)}
                          />
                          {priority}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </section>

          <section className="distribution-section distribution-run-section">
            <div>
              <strong>Fila atual</strong>
              <p>Simule antes de atribuir os leads que já estão sem responsável.</p>
            </div>
            <div className="distribution-run-actions">
              <Button
                variant="secondary"
                disabled={Boolean(running) || saving}
                onClick={() => void run(true)}
              >
                {running === "preview" ? <RefreshCw className="spin" size={15} /> : <RefreshCw size={15} />}
                Simular
              </Button>
              <Button
                disabled={Boolean(running) || saving}
                onClick={() => void run(false)}
              >
                {running === "execute" ? <LoaderCircle className="spin" size={15} /> : <Play size={15} />}
                Distribuir agora
              </Button>
            </div>
          </section>

          {runResult && runResult.assignments.length > 0 && (
            <div className="distribution-preview">
              <div className="distribution-preview__header">
                <Check size={16} />
                <strong>{runResult.dry_run ? "Prévia" : "Última execução"}</strong>
                <span>{runResult.assigned} atribuição(ões)</span>
              </div>
              <div className="distribution-preview__rows">
                {runResult.assignments.slice(0, 8).map((assignment) => (
                  <div key={assignment.lead_public_id}>
                    <code>{assignment.lead_public_id}</code>
                    <span>→</span>
                    <strong>{assignment.user_name}</strong>
                    <small>{assignment.rule_name ?? strategyLabel(assignment.strategy)}</small>
                  </div>
                ))}
                {runResult.assignments.length > 8 && (
                  <p>+ {runResult.assignments.length - 8} atribuição(ões) na mesma execução.</p>
                )}
              </div>
            </div>
          )}
        </div>
      ) : null}
    </Modal>
  );
}

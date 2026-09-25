import {
  AlertTriangle,
  ArrowRight,
  BarChart3,
  CheckCircle2,
  CircleDollarSign,
  Clock3,
  ContactRound,
  FilterX,
  Gauge,
  MessageCircle,
  RefreshCw,
  ShieldAlert,
  Sparkles,
  UsersRound,
  Workflow,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type { OperationalDashboard } from "../types/operationalDashboard";

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

function currency(value: string | number) {
  return currencyFormatter.format(Number(value));
}

function percent(value: number) {
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

function roleLabel(role: string) {
  const labels: Record<string, string> = {
    admin: "Administrador",
    manager: "Gestor",
    seller: "Vendedor",
    operator: "Operador",
  };
  return labels[role] ?? role;
}

function labelize(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function Metric({
  icon,
  label,
  value,
  helper,
  tone = "neutral",
}: {
  icon: ReactNode;
  label: string;
  value: string | number;
  helper: string;
  tone?: "neutral" | "warning" | "danger" | "success";
}) {
  return (
    <div className={`ops-metric ops-metric--${tone}`}>
      <div className="ops-metric__icon">{icon}</div>
      <div>
        <span>{label}</span>
        <strong>{value}</strong>
        <small>{helper}</small>
      </div>
    </div>
  );
}

export function OperationalDashboardPage() {
  const navigate = useNavigate();
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [dashboard, setDashboard] = useState<OperationalDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [periodDays, setPeriodDays] = useState(30);
  const [ownerFilter, setOwnerFilter] = useState("");

  const loadDashboard = useCallback(async () => {
    if (!workspace) {
      setDashboard(null);
      return;
    }

    const params = new URLSearchParams({ period_days: String(periodDays) });
    if (ownerFilter) {
      params.set("owner_user_public_id", ownerFilter);
    }

    setLoading(true);
    setError(null);
    try {
      const payload = await api.get<OperationalDashboard>(
        `/workspaces/${workspace.public_id}/dashboard/operations?${params.toString()}`,
      );
      setDashboard(payload);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar o dashboard operacional.",
      );
    } finally {
      setLoading(false);
    }
  }, [ownerFilter, periodDays, workspace]);

  useEffect(() => {
    setOwnerFilter("");
    setPeriodDays(30);
  }, [workspace?.public_id]);

  useEffect(() => {
    void loadDashboard();
  }, [loadDashboard]);

  const maximumPipelineShare = useMemo(
    () => Math.max(...(dashboard?.pipeline_stages ?? []).map((item) => item.share_percent), 1),
    [dashboard?.pipeline_stages],
  );

  if (workspaceLoading) {
    return <div className="page-state">Carregando empresa...</div>;
  }

  if (!workspace) {
    return (
      <div className="page-state page-state--empty">
        <Gauge size={28} />
        <strong>Nenhuma empresa selecionada</strong>
        <span>Selecione uma empresa para acompanhar a operação.</span>
      </div>
    );
  }

  return (
    <div className="page-stack operational-dashboard-page">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Sprint 5 · Etapa 8</p>
          <h1>Dashboard operacional</h1>
          <p>SLA, carteira, WhatsApp, cadências, pipeline e riscos em uma visão gerencial.</p>
        </div>
        <Button variant="secondary" onClick={() => void loadDashboard()} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          Atualizar
        </Button>
      </header>

      <Card className="ops-filter-card">
        <div className="ops-filters">
          <label>
            <span>Período</span>
            <select value={periodDays} onChange={(event) => setPeriodDays(Number(event.target.value))}>
              <option value={7}>Últimos 7 dias</option>
              <option value={30}>Últimos 30 dias</option>
              <option value={90}>Últimos 90 dias</option>
              <option value={180}>Últimos 180 dias</option>
              <option value={365}>Últimos 12 meses</option>
            </select>
          </label>
          <label>
            <span>Responsável</span>
            <select value={ownerFilter} onChange={(event) => setOwnerFilter(event.target.value)}>
              <option value="">Toda a equipe</option>
              {(dashboard?.available_members ?? []).map((member) => (
                <option key={member.public_id} value={member.public_id}>
                  {member.name} · {roleLabel(member.role)}
                </option>
              ))}
            </select>
          </label>
          {(ownerFilter || periodDays !== 30) && (
            <Button
              variant="ghost"
              onClick={() => {
                setOwnerFilter("");
                setPeriodDays(30);
              }}
            >
              <FilterX size={16} />
              Limpar filtros
            </Button>
          )}
        </div>
      </Card>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <Button variant="secondary" onClick={() => void loadDashboard()}>
            Tentar novamente
          </Button>
        </div>
      )}

      {loading && !dashboard ? (
        <div className="page-state">Consolidando indicadores operacionais...</div>
      ) : dashboard ? (
        <>
          <section className="ops-metrics-grid">
            <Metric
              icon={<ContactRound size={19} />}
              label="Leads ativos"
              value={dashboard.active_leads}
              helper={`${dashboard.leads_created} novos no período`}
            />
            <Metric
              icon={<Clock3 size={19} />}
              label="Exigem atenção"
              value={dashboard.sla.total_attention}
              helper={`${percent(dashboard.sla.attention_share_percent)} da carteira`}
              tone={dashboard.sla.total_attention > 0 ? "warning" : "success"}
            />
            <Metric
              icon={<ShieldAlert size={19} />}
              label="SLA estourado"
              value={dashboard.sla.breached}
              helper={`${dashboard.sla.warning} em alerta`}
              tone={dashboard.sla.breached > 0 ? "danger" : "success"}
            />
            <Metric
              icon={<CircleDollarSign size={19} />}
              label="Pipeline aberto"
              value={currency(dashboard.open_pipeline_value)}
              helper={`${dashboard.open_opportunities} oportunidades`}
            />
            <Metric
              icon={<CheckCircle2 size={19} />}
              label="Conversão"
              value={percent(dashboard.conversion_rate)}
              helper={`${currency(dashboard.won_value)} ganhos no período`}
              tone="success"
            />
            <Metric
              icon={<AlertTriangle size={19} />}
              label="Follow-ups vencidos"
              value={dashboard.sla.overdue_followups}
              helper={`${dashboard.overdue_activities} atividades vencidas`}
              tone={dashboard.sla.overdue_followups > 0 ? "danger" : "success"}
            />
          </section>

          <section className="ops-columns ops-columns--attention">
            <Card
              title="Gargalos que pedem ação"
              description="Priorizados por severidade e volume"
              className="ops-bottlenecks-card"
            >
              {dashboard.bottlenecks.length ? (
                <div className="ops-bottleneck-list">
                  {dashboard.bottlenecks.map((item) => (
                    <button
                      type="button"
                      key={item.code}
                      className="ops-bottleneck-row"
                      onClick={() => navigate(item.route)}
                    >
                      <span className={`ops-bottleneck-dot ops-bottleneck-dot--${item.severity}`} />
                      <span className="ops-bottleneck-copy">
                        <strong>{item.title}</strong>
                        <small>{item.count} item(ns) precisam de atenção</small>
                      </span>
                      <Badge tone={item.severity === "critical" ? "danger" : "warning"}>
                        {item.count}
                      </Badge>
                      <ArrowRight size={16} />
                    </button>
                  ))}
                </div>
              ) : (
                <div className="ops-empty-state">
                  <CheckCircle2 size={22} />
                  <div>
                    <strong>Nenhum gargalo crítico agora</strong>
                    <span>A operação não possui alertas relevantes nos indicadores acompanhados.</span>
                  </div>
                </div>
              )}
            </Card>

            <Card title="Recomendações comerciais" description="Sinais do motor de próximo melhor passo">
              <div className="ops-signal-grid">
                <div><Sparkles size={17} /><span>Críticas</span><strong>{dashboard.recommendations.critical}</strong></div>
                <div><AlertTriangle size={17} /><span>Alta urgência</span><strong>{dashboard.recommendations.high}</strong></div>
                <div><MessageCircle size={17} /><span>Aguardando resposta</span><strong>{dashboard.recommendations.awaiting_reply}</strong></div>
                <div><CircleDollarSign size={17} /><span>Oportunidades em risco</span><strong>{dashboard.recommendations.opportunities_at_risk}</strong></div>
              </div>
              <button type="button" className="card-footer-action" onClick={() => navigate("/recommendations")}>
                Abrir recomendações
                <ArrowRight size={15} />
              </button>
            </Card>
          </section>

          <section className="ops-columns">
            <Card title="WhatsApp operacional" description={`Desempenho nos últimos ${dashboard.period_days} dias`}>
              <div className="ops-channel-headline">
                <div>
                  <span>Taxa de entrega</span>
                  <strong>{percent(dashboard.whatsapp.delivery_rate)}</strong>
                </div>
                <div>
                  <span>Taxa de leitura</span>
                  <strong>{percent(dashboard.whatsapp.read_rate)}</strong>
                </div>
              </div>
              <div className="ops-stat-list">
                <div><span>Recebidas</span><strong>{dashboard.whatsapp.inbound}</strong></div>
                <div><span>Enviadas</span><strong>{dashboard.whatsapp.outbound}</strong></div>
                <div><span>Entregues</span><strong>{dashboard.whatsapp.delivered}</strong></div>
                <div><span>Lidas</span><strong>{dashboard.whatsapp.read}</strong></div>
                <div className={dashboard.whatsapp.failed > 0 ? "ops-stat--danger" : ""}><span>Falhas</span><strong>{dashboard.whatsapp.failed}</strong></div>
              </div>
              <button type="button" className="card-footer-action" onClick={() => navigate("/inbox")}>
                Abrir caixa de entrada
                <ArrowRight size={15} />
              </button>
            </Card>

            <Card title="Cadências" description="Cobertura e execução da automação comercial">
              <div className="ops-coverage">
                <div className="ops-coverage__value">
                  <Workflow size={18} />
                  <strong>{percent(dashboard.cadences.coverage_percent)}</strong>
                  <span>da carteira em cadência ativa</span>
                </div>
                <div className="progress-track">
                  <div className="progress-value" style={{ width: `${Math.min(100, dashboard.cadences.coverage_percent)}%` }} />
                </div>
              </div>
              <div className="ops-stat-list ops-stat-list--two">
                <div><span>Inscrições ativas</span><strong>{dashboard.cadences.active_enrollments}</strong></div>
                <div><span>Leads ativos</span><strong>{dashboard.cadences.active_leads}</strong></div>
                <div><span>Concluídas no período</span><strong>{dashboard.cadences.completed_in_period}</strong></div>
                <div><span>Canceladas no período</span><strong>{dashboard.cadences.cancelled_in_period}</strong></div>
              </div>
              <button type="button" className="card-footer-action" onClick={() => navigate("/cadences")}>
                Abrir cadências
                <ArrowRight size={15} />
              </button>
            </Card>
          </section>

          <section className="ops-columns ops-columns--bottom">
            <Card title="Pipeline por etapa" description="Distribuição das oportunidades abertas">
              {dashboard.pipeline_stages.length ? (
                <div className="ops-pipeline-list">
                  {dashboard.pipeline_stages.map((item) => (
                    <div className="ops-pipeline-row" key={item.stage}>
                      <div>
                        <span>{labelize(item.stage)}</span>
                        <strong>{currency(item.value)}</strong>
                      </div>
                      <div className="progress-track">
                        <div
                          className="progress-value"
                          style={{ width: `${(item.share_percent / maximumPipelineShare) * 100}%` }}
                        />
                      </div>
                      <small>{item.opportunities} oportunidade(s) · {percent(item.share_percent)}</small>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="ops-empty-state">
                  <BarChart3 size={22} />
                  <div><strong>Pipeline vazio</strong><span>As oportunidades abertas aparecerão aqui.</span></div>
                </div>
              )}
            </Card>

            <Card title="Equipe no período" description="Carga, atividades e conversão por responsável">
              {dashboard.member_performance.length ? (
                <div className="table-wrap">
                  <table className="data-table ops-team-table">
                    <thead>
                      <tr>
                        <th>Responsável</th>
                        <th>Leads</th>
                        <th>Atividades</th>
                        <th>Abertas</th>
                        <th>Conversão</th>
                        <th>Receita</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dashboard.member_performance.map((member) => (
                        <tr key={member.public_id}>
                          <td><strong>{member.name}</strong><small>{roleLabel(member.role)}</small></td>
                          <td>{member.leads}</td>
                          <td>{member.completed_activities}</td>
                          <td>{member.open_opportunities}</td>
                          <td>{percent(member.conversion_rate)}</td>
                          <td>{currency(member.won_value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <div className="ops-empty-state">
                  <UsersRound size={22} />
                  <div><strong>Sem desempenho para exibir</strong><span>Os indicadores surgirão conforme a equipe operar o CRM.</span></div>
                </div>
              )}
            </Card>
          </section>
        </>
      ) : null}
    </div>
  );
}

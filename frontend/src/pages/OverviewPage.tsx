import {
  AlertCircle,
  ArrowRight,
  CalendarClock,
  CheckCircle2,
  CircleDollarSign,
  ContactRound,
  Inbox,
  MoreHorizontal,
  RefreshCw,
  TrendingUp,
  UsersRound,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { MetricCard } from "../components/ui/MetricCard";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import type {
  DashboardActivity,
  DashboardRevenuePoint,
  DashboardSummary,
} from "../types/dashboard";

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const compactCurrencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  notation: "compact",
  maximumFractionDigits: 1,
});

function formatCurrency(value: string | number) {
  return currencyFormatter.format(Number(value));
}

function sourceLabel(value: string) {
  const labels: Record<string, string> = {
    instagram: "Instagram",
    instagram_lead_ads: "Instagram Lead Ads",
    facebook: "Facebook",
    google_ads: "Google Ads",
    whatsapp: "WhatsApp",
    site: "Site",
    referral: "Indicação",
    indicacao: "Indicação",
    internet: "Internet",
  };

  return (
    labels[value] ??
    value
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

function statusTone(status: string) {
  if (["ganho", "matricula", "venda", "won"].includes(status)) {
    return "success" as const;
  }
  if (["contatado", "qualificado", "proposta"].includes(status)) {
    return "info" as const;
  }
  if (["perdido", "lost"].includes(status)) {
    return "danger" as const;
  }
  return "neutral" as const;
}

function statusLabel(status: string) {
  return status
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function activityTypeLabel(activity: DashboardActivity) {
  const labels: Record<string, string> = {
    call: "Ligação",
    whatsapp: "WhatsApp",
    email: "E-mail",
    meeting: "Reunião",
    task: "Tarefa",
    follow_up: "Follow-up",
    note: "Nota",
  };
  return labels[activity.activity_type] ?? activity.activity_type;
}

function formatActivityDate(value: string | null) {
  if (!value) {
    return "Sem prazo definido";
  }

  const date = new Date(value);
  return new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

function trendText(value: number | null) {
  if (value === null) {
    return "novo período";
  }
  const signal = value > 0 ? "+" : "";
  return `${signal}${value.toLocaleString("pt-BR", {
    maximumFractionDigits: 1,
  })}%`;
}

function conversionDeltaText(value: number) {
  const signal = value > 0 ? "+" : "";
  return `${signal}${value.toLocaleString("pt-BR", {
    maximumFractionDigits: 1,
  })} p.p.`;
}

function chartPoints(points: DashboardRevenuePoint[]) {
  const values = points.map((point) => Number(point.amount));
  const maximum = Math.max(...values, 1);

  return values
    .map((value, index) => {
      const x = values.length === 1 ? 50 : (index / (values.length - 1)) * 100;
      const y = 88 - (value / maximum) * 68;
      return `${x.toFixed(2)},${y.toFixed(2)}`;
    })
    .join(" ");
}

function chartAreaPoints(points: DashboardRevenuePoint[]) {
  const line = chartPoints(points);
  return `0,100 ${line} 100,100`;
}

function revenueLabel(point: DashboardRevenuePoint) {
  const start = new Date(point.period_start);
  const end = new Date(point.period_end);
  const formatter = new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
  return `${formatter.format(start)}–${formatter.format(end)}`;
}

export function OverviewPage() {
  const {
    workspace,
    loading: workspaceLoading,
    error: workspaceError,
    refreshWorkspaces,
  } = useWorkspace();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadDashboard = async () => {
    if (!workspace) {
      setSummary(null);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await api.get<DashboardSummary>(
        `/workspaces/${workspace.public_id}/dashboard/summary`,
      );
      setSummary(result);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar o dashboard.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadDashboard();
    // loadDashboard changes whenever the selected workspace changes.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [workspace?.public_id]);

  const maximumRevenue = useMemo(() => {
    if (!summary) {
      return 0;
    }
    return Math.max(
      ...summary.revenue_series.map((point) => Number(point.amount)),
      0,
    );
  }, [summary]);

  if (workspaceLoading) {
    return <DashboardLoading />;
  }

  if (workspaceError) {
    return (
      <DashboardError
        title="Não foi possível acessar a API do CRM"
        description={workspaceError}
        onRetry={() => void refreshWorkspaces()}
      />
    );
  }

  if (!workspace) {
    return <EmptyWorkspace />;
  }

  if (loading && !summary) {
    return <DashboardLoading />;
  }

  if (error && !summary) {
    return (
      <DashboardError
        title="Não foi possível carregar o dashboard"
        description={error}
        onRetry={() => void loadDashboard()}
      />
    );
  }

  if (!summary) {
    return null;
  }

  return (
    <div className="page-stack">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Visão geral</p>
          <h1>{summary.workspace_name}</h1>
          <p>
            Desempenho comercial dos últimos {summary.period_days} dias.
          </p>
        </div>

        <div className="page-header__actions">
          <Button
            variant="secondary"
            type="button"
            onClick={() => void loadDashboard()}
            disabled={loading}
          >
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Atualizar
          </Button>
          <Button>
            Novo lead
            <ArrowRight size={17} />
          </Button>
        </div>
      </header>

      {error && (
        <div className="inline-warning">
          <AlertCircle size={16} />
          <span>{error}</span>
        </div>
      )}

      <section className="metrics-grid">
        <MetricCard
          icon={ContactRound}
          label={`Leads · ${summary.period_days} dias`}
          value={summary.leads_in_period.toLocaleString("pt-BR")}
          helper={trendText(summary.leads_trend_percent)}
          trend={
            summary.leads_trend_percent === null ||
            summary.leads_trend_percent === 0
              ? "neutral"
              : summary.leads_trend_percent > 0
                ? "up"
                : "down"
          }
        />
        <MetricCard
          icon={CircleDollarSign}
          label="Pipeline aberto"
          value={formatCurrency(summary.open_pipeline_value)}
          helper={`${summary.open_opportunities} oportunidades`}
          trend="neutral"
        />
        <MetricCard
          icon={CheckCircle2}
          label="Conversão"
          value={`${summary.conversion_rate.toLocaleString("pt-BR", {
            maximumFractionDigits: 1,
          })}%`}
          helper={conversionDeltaText(summary.conversion_delta_pp)}
          trend={
            summary.conversion_delta_pp === 0
              ? "neutral"
              : summary.conversion_delta_pp > 0
                ? "up"
                : "down"
          }
        />
        <MetricCard
          icon={UsersRound}
          label="Oportunidades abertas"
          value={summary.open_opportunities.toLocaleString("pt-BR")}
          helper={`${summary.won_opportunities_in_period} ganhas no período`}
          trend="neutral"
        />
      </section>

      <section className="dashboard-grid">
        <Card
          className="dashboard-grid__performance"
          title="Receita ganha"
          description="Evolução nas últimas quatro semanas"
          actions={
            <button className="text-button" type="button">
              Ver relatório
              <ArrowRight size={15} />
            </button>
          }
        >
          <div className="performance-chart performance-chart--real">
            <div className="chart-scale">
              <span>{compactCurrencyFormatter.format(maximumRevenue)}</span>
              <span>{compactCurrencyFormatter.format(maximumRevenue * 0.75)}</span>
              <span>{compactCurrencyFormatter.format(maximumRevenue * 0.5)}</span>
              <span>{compactCurrencyFormatter.format(maximumRevenue * 0.25)}</span>
              <span>R$ 0</span>
            </div>
            <div className="chart-area">
              {summary.revenue_series.some((point) => Number(point.amount) > 0) ? (
                <svg
                  viewBox="0 0 100 100"
                  preserveAspectRatio="none"
                  aria-label="Gráfico de receita ganha"
                >
                  <polygon
                    className="chart-area__fill-dynamic"
                    points={chartAreaPoints(summary.revenue_series)}
                  />
                  <polyline
                    className="chart-area__line-dynamic"
                    points={chartPoints(summary.revenue_series)}
                  />
                </svg>
              ) : (
                <div className="chart-empty">
                  <TrendingUp size={20} />
                  <span>A receita aparecerá aqui após a primeira venda ganha.</span>
                </div>
              )}
              <div className="chart-labels">
                {summary.revenue_series.map((point) => (
                  <span key={point.period_start}>{revenueLabel(point)}</span>
                ))}
              </div>
            </div>
          </div>

          <div className="performance-summary">
            <div>
              <span>Receita ganha</span>
              <strong>{formatCurrency(summary.won_value_in_period)}</strong>
            </div>
            <div>
              <span>Ticket médio</span>
              <strong>
                {formatCurrency(summary.average_won_value_in_period)}
              </strong>
            </div>
            <div>
              <span>Oportunidades ganhas</span>
              <strong>{summary.won_opportunities_in_period}</strong>
            </div>
          </div>
        </Card>

        <Card
          className="dashboard-grid__tasks"
          title="Próximas atividades"
          description="Pendências mais próximas"
          actions={
            <button className="icon-button icon-button--compact" type="button">
              <MoreHorizontal size={17} />
            </button>
          }
        >
          {summary.upcoming_activities.length > 0 ? (
            <div className="task-list">
              {summary.upcoming_activities.map((activity) => (
                <div className="task-item" key={activity.public_id}>
                  <div className="task-item__icon">
                    <CalendarClock size={17} />
                  </div>
                  <div className="task-item__copy">
                    <strong>{activity.title}</strong>
                    <span>
                      {activityTypeLabel(activity)} · {formatActivityDate(activity.due_at)}
                    </span>
                  </div>
                  <Badge tone={activity.overdue ? "danger" : "warning"}>
                    {activity.overdue ? "Atrasada" : "Pendente"}
                  </Badge>
                </div>
              ))}
            </div>
          ) : (
            <CardEmpty
              title="Nenhuma atividade pendente"
              description="As próximas tarefas e follow-ups aparecerão aqui."
            />
          )}

          <button className="card-footer-action" type="button">
            Ver todas as atividades
            <ArrowRight size={15} />
          </button>
        </Card>
      </section>

      <section className="dashboard-grid dashboard-grid--bottom">
        <Card
          className="dashboard-grid__leads"
          title="Leads recentes"
          description="Últimas entradas registradas no CRM"
          actions={
            <button className="text-button" type="button">
              Ver todos
              <ArrowRight size={15} />
            </button>
          }
        >
          {summary.recent_leads.length > 0 ? (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Lead</th>
                    <th>Origem</th>
                    <th>Interesse</th>
                    <th>Responsável</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.recent_leads.map((lead) => (
                    <tr key={lead.public_id}>
                      <td>
                        <div className="lead-cell">
                          <span className="lead-avatar">
                            {lead.name
                              .split(" ")
                              .slice(0, 2)
                              .map((part) => part[0])
                              .join("")}
                          </span>
                          <strong>{lead.name}</strong>
                        </div>
                      </td>
                      <td>{sourceLabel(lead.source)}</td>
                      <td>{lead.interest ?? "—"}</td>
                      <td>{lead.owner_name ?? "Não atribuído"}</td>
                      <td>
                        <Badge tone={statusTone(lead.status)}>
                          {statusLabel(lead.status)}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <CardEmpty
              title="Nenhum lead cadastrado"
              description="Os novos leads aparecerão aqui assim que entrarem no CRM."
            />
          )}
        </Card>

        <Card
          className="dashboard-grid__sources"
          title="Origem dos leads"
          description={`Distribuição nos últimos ${summary.period_days} dias`}
        >
          {summary.source_distribution.length > 0 ? (
            <>
              <div className="source-list">
                {summary.source_distribution.map((item) => (
                  <div className="source-row" key={item.source}>
                    <div className="source-row__header">
                      <span>{sourceLabel(item.source)}</span>
                      <strong>{item.percentage.toLocaleString("pt-BR")}%</strong>
                    </div>
                    <div className="progress-track">
                      <div
                        className="progress-value"
                        style={{ width: `${item.percentage}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>

              <div className="source-highlight">
                <TrendingUp size={18} />
                <div>
                  <strong>
                    {sourceLabel(summary.source_distribution[0].source)} lidera em volume
                  </strong>
                  <span>
                    {summary.source_distribution[0].count} leads captados no período
                  </span>
                </div>
              </div>
            </>
          ) : (
            <CardEmpty
              title="Sem origens para analisar"
              description="A distribuição será calculada conforme novos leads forem captados."
            />
          )}
        </Card>
      </section>
    </div>
  );
}

function DashboardLoading() {
  return (
    <div className="page-stack">
      <div className="skeleton skeleton--header" />
      <section className="metrics-grid">
        {Array.from({ length: 4 }).map((_, index) => (
          <div className="metric-card skeleton-card" key={index}>
            <div className="skeleton skeleton--short" />
            <div className="skeleton skeleton--value" />
          </div>
        ))}
      </section>
      <div className="card skeleton-panel" />
    </div>
  );
}

type DashboardErrorProps = {
  title: string;
  description: string;
  onRetry: () => void;
};

function DashboardError({
  title,
  description,
  onRetry,
}: DashboardErrorProps) {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="page-eyebrow">Visão geral</p>
          <h1>Nexyra CRM</h1>
          <p>Conectando ao backend do CRM.</p>
        </div>
      </header>
      <Card>
        <div className="state-panel state-panel--error">
          <div className="state-panel__icon">
            <AlertCircle size={22} />
          </div>
          <div>
            <strong>{title}</strong>
            <p>{description}</p>
          </div>
          <Button variant="secondary" onClick={onRetry}>
            <RefreshCw size={16} />
            Tentar novamente
          </Button>
        </div>
      </Card>
    </div>
  );
}

function EmptyWorkspace() {
  return (
    <div className="page-stack">
      <header className="page-header">
        <div>
          <p className="page-eyebrow">Visão geral</p>
          <h1>Nexyra CRM</h1>
          <p>Seu ambiente comercial está pronto.</p>
        </div>
      </header>
      <Card>
        <div className="state-panel">
          <div className="state-panel__icon">
            <Inbox size={22} />
          </div>
          <div>
            <strong>Nenhuma empresa ativa encontrada</strong>
            <p>
              Cadastre um workspace pela API para começar a visualizar os dados do CRM.
            </p>
          </div>
        </div>
      </Card>
    </div>
  );
}

type CardEmptyProps = {
  title: string;
  description: string;
};

function CardEmpty({ title, description }: CardEmptyProps) {
  return (
    <div className="card-empty">
      <Inbox size={18} />
      <strong>{title}</strong>
      <span>{description}</span>
    </div>
  );
}

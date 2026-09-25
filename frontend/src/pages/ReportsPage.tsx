import {
  Activity,
  AlertTriangle,
  BarChart3,
  BriefcaseBusiness,
  CircleDollarSign,
  ContactRound,
  Download,
  FilterX,
  RefreshCw,
  Target,
  Trophy,
  UsersRound,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useWorkspace } from "../contexts/WorkspaceContext";
import { api } from "../lib/api";
import { getReportPeriodPreference } from "../lib/preferences";
import type {
  ReportAnalytics,
  ReportRevenuePoint,
} from "../types/reports";

const currencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 0,
});

const decimalCurrencyFormatter = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

function currency(value: string | number) {
  return currencyFormatter.format(Number(value));
}

function decimalCurrency(value: string | number) {
  return decimalCurrencyFormatter.format(Number(value));
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
    outros: "Outros",
  };
  return (
    labels[value] ??
    value
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

function labelize(value: string) {
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function percent(value: number) {
  return `${value.toLocaleString("pt-BR", { maximumFractionDigits: 1 })}%`;
}

function chartPoints(points: ReportRevenuePoint[]) {
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

function revenueLabel(point: ReportRevenuePoint) {
  const formatter = new Intl.DateTimeFormat("pt-BR", {
    day: "2-digit",
    month: "2-digit",
  });
  return `${formatter.format(new Date(point.period_start))}–${formatter.format(
    new Date(point.period_end),
  )}`;
}

function roleLabel(role: string) {
  const labels: Record<string, string> = {
    admin: "Administrador",
    manager: "Gestor",
    seller: "Vendedor",
    operator: "Operador",
  };
  return labels[role] ?? labelize(role);
}

function csvCell(value: string | number) {
  const text = String(value).replaceAll('"', '""');
  return `"${text}"`;
}

function downloadCsv(report: ReportAnalytics) {
  const rows: Array<Array<string | number>> = [
    ["Nexyra CRM — Relatório comercial"],
    ["Empresa", report.workspace_name],
    ["Período (dias)", report.period_days],
    ["Gerado em", new Date(report.generated_at).toLocaleString("pt-BR")],
    [],
    ["Resumo"],
    ["Leads", report.total_leads],
    ["Oportunidades criadas", report.opportunities_created],
    ["Pipeline aberto", report.open_pipeline_value],
    ["Oportunidades ganhas", report.won_opportunities],
    ["Oportunidades perdidas", report.lost_opportunities],
    ["Conversão (%)", report.conversion_rate],
    ["Receita ganha", report.won_value],
    ["Ticket médio", report.average_ticket],
    [],
    ["Origem", "Leads", "Ganhas", "Perdidas", "Conversão (%)", "Receita"],
    ...report.source_performance.map((item) => [
      sourceLabel(item.source),
      item.leads,
      item.won_opportunities,
      item.lost_opportunities,
      item.conversion_rate,
      item.won_value,
    ]),
    [],
    ["Equipe", "Função", "Leads", "Abertas", "Ganhas", "Perdidas", "Conversão (%)", "Receita"],
    ...report.member_performance.map((item) => [
      item.name,
      roleLabel(item.role),
      item.leads,
      item.open_opportunities,
      item.won_opportunities,
      item.lost_opportunities,
      item.conversion_rate,
      item.won_value,
    ]),
  ];

  const content = rows.map((row) => row.map(csvCell).join(";")).join("\r\n");
  const blob = new Blob(["\ufeff", content], {
    type: "text/csv;charset=utf-8;",
  });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  const date = new Date().toISOString().slice(0, 10);
  anchor.href = url;
  anchor.download = `nexyra-relatorio-${date}.csv`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export function ReportsPage() {
  const { workspace, loading: workspaceLoading } = useWorkspace();
  const [report, setReport] = useState<ReportAnalytics | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [periodDays, setPeriodDays] = useState(30);
  const [sourceFilter, setSourceFilter] = useState("");
  const [ownerFilter, setOwnerFilter] = useState("");

  const loadReport = useCallback(async () => {
    if (!workspace) {
      setReport(null);
      return;
    }

    const params = new URLSearchParams({ period_days: String(periodDays) });
    if (sourceFilter) params.set("source", sourceFilter);
    if (ownerFilter) params.set("owner_user_public_id", ownerFilter);

    setLoading(true);
    setError(null);
    try {
      const payload = await api.get<ReportAnalytics>(
        `/workspaces/${workspace.public_id}/reports/analytics?${params.toString()}`,
      );
      setReport(payload);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar os relatórios.",
      );
    } finally {
      setLoading(false);
    }
  }, [ownerFilter, periodDays, sourceFilter, workspace]);

  useEffect(() => {
    setSourceFilter("");
    setOwnerFilter("");
    setPeriodDays(
      workspace ? getReportPeriodPreference(workspace.public_id) : 30,
    );
  }, [workspace?.public_id]);

  useEffect(() => {
    void loadReport();
  }, [loadReport]);

  const maximumRevenue = useMemo(
    () => Math.max(...(report?.revenue_series ?? []).map((item) => Number(item.amount)), 0),
    [report?.revenue_series],
  );

  const preferredPeriod = workspace
    ? getReportPeriodPreference(workspace.public_id)
    : 30;
  const hasFilters =
    periodDays !== preferredPeriod || Boolean(sourceFilter) || Boolean(ownerFilter);

  function clearFilters() {
    setPeriodDays(preferredPeriod);
    setSourceFilter("");
    setOwnerFilter("");
  }

  if (workspaceLoading) {
    return <div className="page-state">Carregando empresa...</div>;
  }

  if (!workspace) {
    return (
      <div className="page-state page-state--empty">
        <BarChart3 size={28} />
        <strong>Nenhuma empresa selecionada</strong>
        <span>Selecione uma empresa para visualizar os relatórios.</span>
      </div>
    );
  }

  return (
    <div className="page-stack reports-page">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Relatórios</p>
          <h1>Analytics comercial</h1>
          <p>Conversão, receita, fontes, pipeline e desempenho da equipe.</p>
        </div>
        <div className="page-header__actions">
          <Button variant="secondary" onClick={() => void loadReport()} disabled={loading}>
            <RefreshCw size={16} className={loading ? "spin" : ""} />
            Atualizar
          </Button>
          <Button onClick={() => report && downloadCsv(report)} disabled={!report}>
            <Download size={16} />
            Exportar CSV
          </Button>
        </div>
      </header>

      <Card className="report-filter-card">
        <div className="report-filters">
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
            <span>Origem</span>
            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)}>
              <option value="">Todas as origens</option>
              {(report?.available_sources ?? []).map((source) => (
                <option key={source} value={source}>{sourceLabel(source)}</option>
              ))}
            </select>
          </label>
          <label>
            <span>Responsável</span>
            <select value={ownerFilter} onChange={(event) => setOwnerFilter(event.target.value)}>
              <option value="">Toda a equipe</option>
              {(report?.available_members ?? []).map((member) => (
                <option key={member.public_id} value={member.public_id}>
                  {member.name} · {roleLabel(member.role)}
                </option>
              ))}
            </select>
          </label>
          {hasFilters && (
            <Button variant="ghost" onClick={clearFilters}>
              <FilterX size={16} />
              Limpar filtros
            </Button>
          )}
        </div>
      </Card>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <Button variant="secondary" onClick={() => void loadReport()}>
            Tentar novamente
          </Button>
        </div>
      )}

      {loading && !report ? (
        <div className="page-state">Carregando indicadores...</div>
      ) : report ? (
        <>
          <section className="report-metrics">
            <article className="report-metric">
              <ContactRound />
              <div><span>Leads</span><strong>{report.total_leads}</strong><small>{report.opportunities_created} oportunidades criadas</small></div>
            </article>
            <article className="report-metric">
              <CircleDollarSign />
              <div><span>Receita ganha</span><strong>{currency(report.won_value)}</strong><small>Ticket médio {currency(report.average_ticket)}</small></div>
            </article>
            <article className="report-metric">
              <Target />
              <div><span>Conversão</span><strong>{percent(report.conversion_rate)}</strong><small>{report.won_opportunities} ganhas · {report.lost_opportunities} perdidas</small></div>
            </article>
            <article className="report-metric">
              <BriefcaseBusiness />
              <div><span>Pipeline aberto</span><strong>{currency(report.open_pipeline_value)}</strong><small>{report.open_opportunities} oportunidades abertas</small></div>
            </article>
          </section>

          <section className="report-grid report-grid--hero">
            <Card title="Receita no período" description={`Últimos ${report.period_days} dias`}>
              <div className="report-revenue-chart">
                {report.revenue_series.length ? (
                  <>
                    <div className="report-chart-axis">
                      <strong>{currency(maximumRevenue)}</strong>
                      <span>{currency(maximumRevenue / 2)}</span>
                      <span>R$ 0</span>
                    </div>
                    <div className="report-chart-canvas">
                      <svg viewBox="0 0 100 100" preserveAspectRatio="none" aria-label="Receita no período">
                        <polyline className="report-chart-line" points={chartPoints(report.revenue_series)} />
                      </svg>
                      <div className="report-chart-labels">
                        {report.revenue_series.map((point) => (
                          <span key={point.period_start}>{revenueLabel(point)}</span>
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="table-state">Sem receita no período selecionado.</div>
                )}
              </div>
              <div className="report-revenue-footer">
                <div><span>Receita total</span><strong>{decimalCurrency(report.won_value)}</strong></div>
                <div><span>Vendas ganhas</span><strong>{report.won_opportunities}</strong></div>
                <div><span>Ticket médio</span><strong>{decimalCurrency(report.average_ticket)}</strong></div>
              </div>
            </Card>

            <Card title="Operação comercial" description="Atividades e follow-ups">
              <div className="report-operation-grid">
                <div><Activity /><span>Atividades criadas</span><strong>{report.activities_created}</strong></div>
                <div><Trophy /><span>Concluídas</span><strong>{report.completed_activities}</strong></div>
                <div><Target /><span>Pendentes</span><strong>{report.pending_activities}</strong></div>
                <div className={report.overdue_activities ? "report-operation--danger" : ""}>
                  <AlertTriangle /><span>Atrasadas</span><strong>{report.overdue_activities}</strong>
                </div>
              </div>
            </Card>
          </section>

          <section className="report-grid">
            <Card title="Desempenho por origem" description="Volume, conversão e receita por canal de aquisição">
              {report.source_performance.length ? (
                <div className="table-wrap">
                  <table className="data-table report-table">
                    <thead><tr><th>Origem</th><th>Leads</th><th>Participação</th><th>Ganhas</th><th>Conversão</th><th>Receita</th></tr></thead>
                    <tbody>
                      {report.source_performance.map((item) => (
                        <tr key={item.source}>
                          <td><strong>{sourceLabel(item.source)}</strong></td>
                          <td>{item.leads}</td>
                          <td>{percent(item.lead_share_percent)}</td>
                          <td>{item.won_opportunities}</td>
                          <td><Badge tone={item.conversion_rate >= 30 ? "success" : item.conversion_rate > 0 ? "info" : "neutral"}>{percent(item.conversion_rate)}</Badge></td>
                          <td><strong>{currency(item.won_value)}</strong></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <div className="table-state">Nenhuma origem com dados neste período.</div>}
            </Card>

            <Card title="Pipeline atual" description="Distribuição das oportunidades abertas">
              {report.pipeline_stages.length ? (
                <div className="report-progress-list">
                  {report.pipeline_stages.map((stage) => (
                    <div className="report-progress-item" key={stage.stage}>
                      <div><span>{labelize(stage.stage)}</span><strong>{currency(stage.value)}</strong></div>
                      <div className="progress-track"><div className="progress-value" style={{ width: `${Math.max(stage.share_percent, 2)}%` }} /></div>
                      <small>{stage.opportunities} oportunidades · {percent(stage.share_percent)}</small>
                    </div>
                  ))}
                </div>
              ) : <div className="table-state">Nenhuma oportunidade aberta.</div>}
            </Card>
          </section>

          <Card title="Desempenho da equipe" description="Ranking comercial no período selecionado">
            {report.member_performance.length ? (
              <div className="table-wrap">
                <table className="data-table report-table report-team-table">
                  <thead><tr><th>Profissional</th><th>Função</th><th>Leads</th><th>Abertas</th><th>Ganhas</th><th>Conversão</th><th>Ticket médio</th><th>Receita</th><th>Atividades</th></tr></thead>
                  <tbody>
                    {report.member_performance.map((member, index) => (
                      <tr key={member.public_id}>
                        <td>
                          <div className="report-member-cell">
                            <span className="report-rank">{index + 1}</span>
                            <div><strong>{member.name}</strong><span>{member.public_id}</span></div>
                          </div>
                        </td>
                        <td>{roleLabel(member.role)}</td>
                        <td>{member.leads}</td>
                        <td>{member.open_opportunities}</td>
                        <td>{member.won_opportunities}</td>
                        <td>{percent(member.conversion_rate)}</td>
                        <td>{currency(member.average_ticket)}</td>
                        <td><strong>{currency(member.won_value)}</strong></td>
                        <td>{member.completed_activities}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <div className="table-state">Nenhum membro com dados para os filtros selecionados.</div>}
          </Card>

          <section className="report-grid report-grid--bottom">
            <Card title="Interesses com resultado" description="Produtos, cursos ou interesses mais relevantes">
              {report.interest_performance.length ? (
                <div className="report-interest-list">
                  {report.interest_performance.map((item) => (
                    <div key={item.interest}>
                      <div><strong>{item.interest}</strong><span>{item.leads} leads</span></div>
                      <div><strong>{currency(item.won_value)}</strong><span>{item.won_opportunities} ganhas</span></div>
                    </div>
                  ))}
                </div>
              ) : <div className="table-state">Sem dados de interesse no período.</div>}
            </Card>

            <Card title="Motivos de perda" description="Principais razões das oportunidades perdidas">
              {report.loss_reasons.length ? (
                <div className="report-loss-list">
                  {report.loss_reasons.map((item) => (
                    <div key={item.reason}>
                      <div><strong>{item.reason}</strong><span>{item.count} perdas</span></div>
                      <Badge tone="danger">{percent(item.percentage)}</Badge>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="report-clean-state"><Trophy size={23} /><strong>Nenhuma perda registrada</strong><span>Não há motivos de perda no período selecionado.</span></div>
              )}
            </Card>
          </section>

          <div className="report-footnote">
            <UsersRound size={15} />
            <span>Os indicadores respeitam a empresa selecionada e os filtros de período, origem e responsável.</span>
          </div>
        </>
      ) : null}
    </div>
  );
}

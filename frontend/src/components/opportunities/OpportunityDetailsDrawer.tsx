import {
  CalendarClock,
  CircleDollarSign,
  Clock3,
  Mail,
  Phone,
  Tag,
  UserRound,
} from "lucide-react";

import type {
  OpportunityCard,
  OpportunityHistory,
} from "../../types/opportunities";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Drawer } from "../ui/Drawer";

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function formatCurrency(value: string, currency: string) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency,
  }).format(Number(value || 0));
}

function formatDate(value: string | null) {
  if (!value) {
    return "Não informado";
  }

  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
  }).format(new Date(`${value}T12:00:00`));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusTone(status: string) {
  if (status === "won") return "success" as const;
  if (status === "lost") return "danger" as const;
  return "info" as const;
}

type OpportunityDetailsDrawerProps = {
  opportunity: OpportunityCard | null;
  history: OpportunityHistory[];
  historyLoading: boolean;
  onClose: () => void;
  onEdit: (opportunity: OpportunityCard) => void;
  onWon: (opportunity: OpportunityCard) => void;
  onLost: (opportunity: OpportunityCard) => void;
};

export function OpportunityDetailsDrawer({
  opportunity,
  history,
  historyLoading,
  onClose,
  onEdit,
  onWon,
  onLost,
}: OpportunityDetailsDrawerProps) {
  if (!opportunity) {
    return null;
  }

  return (
    <Drawer
      open
      title={opportunity.title}
      subtitle={opportunity.public_id}
      onClose={onClose}
      actions={
        <>
          <Button variant="secondary" onClick={() => onEdit(opportunity)}>
            Editar
          </Button>
          {opportunity.status === "open" && (
            <>
              <Button onClick={() => onWon(opportunity)}>Marcar ganha</Button>
              <Button variant="ghost" onClick={() => onLost(opportunity)}>
                Marcar perdida
              </Button>
            </>
          )}
        </>
      }
    >
      <div className="lead-detail-statusbar">
        <Badge tone={statusTone(opportunity.status)}>
          {opportunity.status === "open"
            ? "Aberta"
            : opportunity.status === "won"
              ? "Ganha"
              : "Perdida"}
        </Badge>
        <Badge tone="neutral">{labelize(opportunity.stage)}</Badge>
      </div>

      <section className="detail-section opportunity-value-section">
        <span>Valor da oportunidade</span>
        <strong>
          {formatCurrency(opportunity.value_amount, opportunity.currency)}
        </strong>
      </section>

      <section className="detail-section">
        <h3>Lead</h3>
        <div className="detail-list">
          <div className="detail-row">
            <UserRound size={16} />
            <span>Nome</span>
            <strong>{opportunity.lead_name}</strong>
          </div>
          <div className="detail-row">
            <Tag size={16} />
            <span>Interesse</span>
            <strong>{opportunity.lead_interest ?? "Não informado"}</strong>
          </div>
          <div className="detail-row">
            <Phone size={16} />
            <span>Telefone</span>
            <strong>{opportunity.lead_phone ?? "Não informado"}</strong>
          </div>
          <div className="detail-row">
            <Mail size={16} />
            <span>E-mail</span>
            <strong>{opportunity.lead_email ?? "Não informado"}</strong>
          </div>
        </div>
      </section>

      <section className="detail-section">
        <h3>Negociação</h3>
        <div className="detail-list">
          <div className="detail-row">
            <CircleDollarSign size={16} />
            <span>Etapa</span>
            <strong>{labelize(opportunity.stage)}</strong>
          </div>
          <div className="detail-row">
            <UserRound size={16} />
            <span>Responsável</span>
            <strong>{opportunity.owner_name ?? "Sem responsável"}</strong>
          </div>
          <div className="detail-row">
            <CalendarClock size={16} />
            <span>Previsão</span>
            <strong>{formatDate(opportunity.expected_close_date)}</strong>
          </div>
          {opportunity.loss_reason && (
            <div className="detail-row detail-row--stack">
              <Clock3 size={16} />
              <span>Motivo da perda</span>
              <strong>{opportunity.loss_reason}</strong>
            </div>
          )}
        </div>
      </section>

      <section className="detail-section">
        <h3>Histórico do pipeline</h3>
        {historyLoading ? (
          <div className="opportunity-history-empty">Carregando histórico...</div>
        ) : history.length > 0 ? (
          <div className="opportunity-history">
            {[...history].reverse().map((item, index) => (
              <div
                className="opportunity-history__item"
                key={`${item.created_at}-${index}`}
              >
                <span className="opportunity-history__dot" />
                <div>
                  <strong>
                    {item.from_stage && item.from_stage !== item.to_stage
                      ? `${labelize(item.from_stage)} → ${labelize(item.to_stage)}`
                      : labelize(item.to_stage)}
                  </strong>
                  <span>{item.note ?? "Alteração registrada."}</span>
                  <small>{formatDateTime(item.created_at)}</small>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="opportunity-history-empty">
            Nenhuma movimentação registrada.
          </div>
        )}
      </section>

      <section className="detail-section">
        <h3>Registro</h3>
        <div className="detail-list">
          <div className="detail-row">
            <CalendarClock size={16} />
            <span>Criada em</span>
            <strong>{formatDateTime(opportunity.created_at)}</strong>
          </div>
          <div className="detail-row">
            <CalendarClock size={16} />
            <span>Atualizada em</span>
            <strong>{formatDateTime(opportunity.updated_at)}</strong>
          </div>
        </div>
      </section>
    </Drawer>
  );
}

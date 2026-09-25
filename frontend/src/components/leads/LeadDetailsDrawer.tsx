import {
  CalendarClock,
  Mail,
  MessageSquareText,
  Phone,
  ShieldCheck,
  Tag,
  UserRound,
} from "lucide-react";

import type { Lead, WorkspaceMember } from "../../types/leads";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Drawer } from "../ui/Drawer";

function labelize(value: string) {
  return value
    .replaceAll("_", " ")
    .replace(/\w/g, (letter) => letter.toUpperCase());
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function priorityTone(priority: string) {
  if (priority === "urgente") return "danger" as const;
  if (priority === "alta") return "warning" as const;
  if (priority === "baixa") return "neutral" as const;
  return "info" as const;
}

type LeadDetailsDrawerProps = {
  lead: Lead | null;
  members: WorkspaceMember[];
  onClose: () => void;
  onEdit: (lead: Lead) => void;
  onDeactivate: (lead: Lead) => void;
  onManageConsent: (lead: Lead) => void;
};

export function LeadDetailsDrawer({
  lead,
  members,
  onClose,
  onEdit,
  onDeactivate,
  onManageConsent,
}: LeadDetailsDrawerProps) {
  if (!lead) {
    return null;
  }

  const owner = members.find(
    (member) => member.public_id === lead.owner_user_public_id,
  );

  return (
    <Drawer
      open
      title={lead.name}
      subtitle={lead.public_id}
      onClose={onClose}
      actions={
        <>
          <Button variant="secondary" onClick={() => onManageConsent(lead)}>
            <ShieldCheck size={15} />
            Consentimentos
          </Button>
          <Button variant="secondary" onClick={() => onEdit(lead)}>
            Editar
          </Button>
          {lead.active && (
            <Button variant="ghost" onClick={() => onDeactivate(lead)}>
              Desativar
            </Button>
          )}
        </>
      }
    >
      <div className="lead-detail-statusbar">
        <Badge tone="info">{labelize(lead.status)}</Badge>
        <Badge tone={priorityTone(lead.priority)}>
          {labelize(lead.priority)}
        </Badge>
        {!lead.active && <Badge tone="danger">Inativo</Badge>}
      </div>

      <section className="detail-section">
        <h3>Contato</h3>
        <div className="detail-list">
          <div className="detail-row">
            <Phone size={16} />
            <span>Telefone</span>
            <strong>{lead.phone ?? "Não informado"}</strong>
          </div>
          <div className="detail-row">
            <Mail size={16} />
            <span>E-mail</span>
            <strong>{lead.email ?? "Não informado"}</strong>
          </div>
          <div className="detail-row">
            <UserRound size={16} />
            <span>Responsável</span>
            <strong>{owner?.name ?? "Sem responsável"}</strong>
          </div>
        </div>
      </section>

      <section className="detail-section">
        <h3>Origem comercial</h3>
        <div className="detail-grid">
          <div>
            <span>Origem</span>
            <strong>{labelize(lead.source)}</strong>
          </div>
          <div>
            <span>Canal</span>
            <strong>{labelize(lead.channel)}</strong>
          </div>
          <div>
            <span>Campanha</span>
            <strong>{lead.campaign ?? "—"}</strong>
          </div>
          <div>
            <span>ID externo</span>
            <strong>{lead.external_id ?? "—"}</strong>
          </div>
        </div>
      </section>

      <section className="detail-section">
        <h3>Interesse e contexto</h3>
        <div className="detail-list">
          <div className="detail-row">
            <Tag size={16} />
            <span>Interesse</span>
            <strong>{lead.interest ?? "Não informado"}</strong>
          </div>
          <div className="detail-row detail-row--stack">
            <MessageSquareText size={16} />
            <span>Mensagem</span>
            <strong>{lead.message ?? "Sem observação registrada."}</strong>
          </div>
        </div>
      </section>

      {Object.keys(lead.custom_fields).length > 0 && (
        <section className="detail-section">
          <h3>Campos do segmento</h3>
          <div className="detail-grid">
            {Object.entries(lead.custom_fields).map(([key, value]) => (
              <div key={key}>
                <span>{labelize(key)}</span>
                <strong>{String(value ?? "—")}</strong>
              </div>
            ))}
          </div>
        </section>
      )}

      <section className="detail-section">
        <h3>Registro</h3>
        <div className="detail-list">
          <div className="detail-row">
            <CalendarClock size={16} />
            <span>Criado em</span>
            <strong>{formatDate(lead.created_at)}</strong>
          </div>
          <div className="detail-row">
            <CalendarClock size={16} />
            <span>Atualizado em</span>
            <strong>{formatDate(lead.updated_at)}</strong>
          </div>
        </div>
        <div className="consent-state">
          <span className={lead.consent ? "status-dot status-dot--ok" : "status-dot"} />
          {lead.consent
            ? "Consentimento legado registrado"
            : "Sem consentimento legado"}
        </div>
      </section>
    </Drawer>
  );
}

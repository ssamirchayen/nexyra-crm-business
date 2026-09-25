import {
  CalendarClock,
  CheckCircle2,
  CircleX,
  Link2,
  Pencil,
  UserRound,
} from "lucide-react";

import type { ActivityCard } from "../../types/activities";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Drawer } from "../ui/Drawer";

const typeLabels: Record<string, string> = {
  call: "Ligação",
  whatsapp: "WhatsApp",
  email: "E-mail",
  meeting: "Reunião",
  task: "Tarefa",
  follow_up: "Follow-up",
  note: "Nota",
};

function formatDateTime(value: string | null) {
  if (!value) return "Sem data definida";
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function statusTone(activity: ActivityCard) {
  if (activity.status === "completed") return "success" as const;
  if (activity.status === "cancelled") return "neutral" as const;
  if (activity.overdue) return "danger" as const;
  return "warning" as const;
}

function statusLabel(activity: ActivityCard) {
  if (activity.status === "completed") return "Concluída";
  if (activity.status === "cancelled") return "Cancelada";
  if (activity.overdue) return "Atrasada";
  return "Pendente";
}

type Props = {
  activity: ActivityCard | null;
  busy: boolean;
  onClose: () => void;
  onEdit: (activity: ActivityCard) => void;
  onComplete: (activity: ActivityCard) => void;
  onCancel: (activity: ActivityCard) => void;
};

export function ActivityDetailsDrawer({
  activity,
  busy,
  onClose,
  onEdit,
  onComplete,
  onCancel,
}: Props) {
  if (!activity) return null;

  const pending = activity.status === "pending";

  return (
    <Drawer
      open
      title={activity.title}
      subtitle={`${typeLabels[activity.activity_type] ?? activity.activity_type} · ${activity.public_id}`}
      onClose={onClose}
      actions={
        pending ? (
          <div className="activity-drawer-actions">
            <Button variant="secondary" disabled={busy} onClick={() => onEdit(activity)}>
              <Pencil size={15} />
              Editar
            </Button>
            <Button variant="secondary" disabled={busy} onClick={() => onComplete(activity)}>
              <CheckCircle2 size={15} />
              Concluir
            </Button>
            <Button variant="ghost" disabled={busy} onClick={() => onCancel(activity)}>
              <CircleX size={15} />
              Cancelar
            </Button>
          </div>
        ) : undefined
      }
    >
      <div className="activity-drawer-stack">
        <section className="detail-section">
          <div className="detail-section__title">Situação</div>
          <div className="activity-status-panel">
            <Badge tone={statusTone(activity)}>{statusLabel(activity)}</Badge>
            <div>
              <CalendarClock size={17} />
              <span>{formatDateTime(activity.due_at)}</span>
            </div>
          </div>
        </section>

        <section className="detail-section">
          <div className="detail-section__title">Responsável</div>
          <div className="activity-detail-line">
            <UserRound size={17} />
            <div>
              <span>Responsável comercial</span>
              <strong>{activity.owner_name ?? "Sem responsável"}</strong>
            </div>
          </div>
        </section>

        <section className="detail-section">
          <div className="detail-section__title">Contexto comercial</div>
          <div className="activity-detail-line">
            <Link2 size={17} />
            <div>
              <span>Lead</span>
              <strong>{activity.lead_name ?? "Atividade interna"}</strong>
            </div>
          </div>
          {activity.opportunity_title && (
            <div className="activity-detail-line activity-detail-line--indent">
              <div>
                <span>Oportunidade</span>
                <strong>{activity.opportunity_title}</strong>
              </div>
            </div>
          )}
        </section>

        <section className="detail-section">
          <div className="detail-section__title">Descrição</div>
          <p className="activity-description">
            {activity.description ?? "Nenhuma observação registrada."}
          </p>
        </section>

        <section className="detail-section detail-section--muted">
          <div className="activity-meta-grid">
            <div>
              <span>Criada em</span>
              <strong>{formatDateTime(activity.created_at)}</strong>
            </div>
            {activity.completed_at && (
              <div>
                <span>Concluída em</span>
                <strong>{formatDateTime(activity.completed_at)}</strong>
              </div>
            )}
            {activity.cancelled_at && (
              <div>
                <span>Cancelada em</span>
                <strong>{formatDateTime(activity.cancelled_at)}</strong>
              </div>
            )}
          </div>
        </section>
      </div>
    </Drawer>
  );
}

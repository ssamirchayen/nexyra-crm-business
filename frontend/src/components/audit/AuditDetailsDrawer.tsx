import {
  ArrowRight,
  Braces,
  Clock3,
  FileKey2,
  Fingerprint,
  ShieldCheck,
  UserRound,
} from "lucide-react";

import { Badge } from "../ui/Badge";
import { Drawer } from "../ui/Drawer";
import {
  actorLabel,
  actorTone,
  auditChangedKeys,
  formatAuditDate,
  formatAuditValue,
  labelizeAuditAction,
  labelizeEntity,
  roleLabels,
} from "../../lib/audit";
import type { AuditEvent } from "../../types/audit";

type AuditDetailsDrawerProps = {
  event: AuditEvent | null;
  onClose: () => void;
};

function DataBlock({
  title,
  data,
}: {
  title: string;
  data: Record<string, unknown> | null;
}) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <div className="audit-json-block audit-json-block--empty">
        <span>{title}</span>
        <strong>Sem dados registrados</strong>
      </div>
    );
  }

  return (
    <div className="audit-json-block">
      <span>{title}</span>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  );
}

export function AuditDetailsDrawer({ event, onClose }: AuditDetailsDrawerProps) {
  if (!event) return null;

  const changedKeys = auditChangedKeys(event.before_data, event.after_data);
  const actorName = event.actor_user_name ?? actorLabel(event.actor_type);

  return (
    <Drawer
      open
      title={labelizeAuditAction(event.action)}
      subtitle={event.public_id}
      onClose={onClose}
    >
      <div className="audit-drawer-stack">
        <section className="audit-detail-summary">
          <div>
            <Clock3 size={17} />
            <span>Data e hora</span>
            <strong>{formatAuditDate(event.created_at)}</strong>
          </div>
          <div>
            <UserRound size={17} />
            <span>Responsável / origem</span>
            <strong>{actorName}</strong>
            <small>
              {event.actor_role
                ? roleLabels[event.actor_role] ?? event.actor_role
                : actorLabel(event.actor_type)}
            </small>
          </div>
          <div>
            <FileKey2 size={17} />
            <span>Entidade</span>
            <strong>{labelizeEntity(event.entity_type)}</strong>
            <small>{event.entity_public_id}</small>
          </div>
          <div>
            <ShieldCheck size={17} />
            <span>Origem técnica</span>
            <Badge tone={actorTone(event.actor_type)}>
              {actorLabel(event.actor_type)}
            </Badge>
          </div>
        </section>

        <section className="audit-drawer-section">
          <header>
            <Fingerprint size={17} />
            <div>
              <strong>Alterações registradas</strong>
              <span>
                {changedKeys.length > 0
                  ? `${changedKeys.length} campo(s) alterado(s)`
                  : "Evento sem diferença de campos"}
              </span>
            </div>
          </header>

          {changedKeys.length > 0 ? (
            <div className="audit-diff-list">
              {changedKeys.map((key) => (
                <div className="audit-diff-row" key={key}>
                  <div className="audit-diff-key">{key}</div>
                  <div className="audit-diff-value audit-diff-value--before">
                    <span>Antes</span>
                    <strong>{formatAuditValue(event.before_data?.[key])}</strong>
                  </div>
                  <ArrowRight size={15} />
                  <div className="audit-diff-value audit-diff-value--after">
                    <span>Depois</span>
                    <strong>{formatAuditValue(event.after_data?.[key])}</strong>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="audit-empty-diff">
              <ShieldCheck size={21} />
              <span>Nenhuma alteração comparável neste evento.</span>
            </div>
          )}
        </section>

        <section className="audit-drawer-section">
          <header>
            <Braces size={17} />
            <div>
              <strong>Dados técnicos</strong>
              <span>Snapshots e metadados preservados pela auditoria.</span>
            </div>
          </header>
          <div className="audit-json-grid">
            <DataBlock title="Estado anterior" data={event.before_data} />
            <DataBlock title="Estado posterior" data={event.after_data} />
          </div>
          <DataBlock title="Metadados" data={event.metadata} />
        </section>
      </div>
    </Drawer>
  );
}

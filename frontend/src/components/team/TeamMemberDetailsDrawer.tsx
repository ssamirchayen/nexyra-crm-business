import {
  BriefcaseBusiness,
  CheckCircle2,
  CircleDollarSign,
  ContactRound,
  KeyRound,
  Mail,
  ShieldCheck,
  UserRoundCog,
} from "lucide-react";

import type { RoleDefinition, TeamMember, TeamRole } from "../../types/team";
import { Badge } from "../ui/Badge";
import { Button } from "../ui/Button";
import { Drawer } from "../ui/Drawer";

import { TeamMemberPasswordReset } from "./TeamMemberPasswordReset";
import { TeamMemberSessions } from "./TeamMemberSessions";

const roleLabels: Record<TeamRole, string> = {
  admin: "Administrador",
  manager: "Gestor",
  seller: "Vendedor",
  operator: "Operador",
};

const permissionLabels: Record<string, string> = {
  "workspace.read": "Visualizar empresa",
  "workspace.update": "Editar empresa",
  "members.reset_password": "Redefinir senhas de membros",
  "sessions.manage": "Gerenciar sessões",
  "members.read": "Visualizar equipe",
  "members.create": "Adicionar membros",
  "members.update": "Alterar membros",
  "members.deactivate": "Desativar membros",
  "leads.read": "Visualizar leads",
  "leads.create": "Criar leads",
  "leads.update": "Editar leads",
  "leads.assign": "Distribuir leads",
  "pipeline.read": "Visualizar pipeline",
  "pipeline.update": "Alterar pipeline",
  "analytics.read": "Visualizar indicadores",
  "settings.read": "Visualizar configurações",
  "settings.update": "Alterar configurações",
  "atlas.use": "Usar recursos do Atlas",
  "atlas.execute": "Confirmar execuções do Atlas",
};

function currency(value: string) {
  return new Intl.NumberFormat("pt-BR", {
    style: "currency",
    currency: "BRL",
  }).format(Number(value));
}

type TeamMemberDetailsDrawerProps = {
  workspaceId: string;
  canEdit: boolean;
  canChangeStatus: boolean;
  saving: boolean;
  member: TeamMember | null;
  roles: RoleDefinition[];
  onClose: () => void;
  onEdit: (member: TeamMember) => void;
  onToggleActive: (member: TeamMember) => void;
};

export function TeamMemberDetailsDrawer({
  workspaceId,
  canEdit,
  canChangeStatus,
  saving,
  member,
  roles,
  onClose,
  onEdit,
  onToggleActive,
}: TeamMemberDetailsDrawerProps) {
  if (!member) {
    return null;
  }

  const role = roles.find((item) => item.role === member.role);

  return (
    <Drawer
      open
      title={member.name}
      subtitle={member.email}
      onClose={onClose}
      actions={
        <>
          {canEdit && <Button variant="secondary" disabled={saving} onClick={() => onEdit(member)}>
            <UserRoundCog size={16} />
            Editar acesso
          </Button>}
          {canChangeStatus && <Button variant="ghost" disabled={saving} onClick={() => onToggleActive(member)}>
            {member.membership_active ? "Desativar" : "Reativar"}
          </Button>}
        </>
      }
    >
      <div className="team-detail-statusbar">
        <Badge tone="info">{roleLabels[member.role]}</Badge>
        <Badge tone={member.membership_active ? "success" : "neutral"}>
          {member.membership_active ? "Ativo" : "Inativo"}
        </Badge>
      </div>

      <section className="detail-section">
        <h3>Usuário</h3>
        <div className="detail-list">
          <div className="detail-row">
            <Mail size={16} />
            <span>E-mail</span>
            <strong>{member.email}</strong>
          </div>
          <div className="detail-row">
            <KeyRound size={16} />
            <span>ID do usuário</span>
            <strong>{member.public_id}</strong>
          </div>
        </div>
      </section>

      <section className="detail-section">
        <h3>Desempenho comercial</h3>
        <div className="team-performance-grid">
          <div>
            <ContactRound size={16} />
            <span>Leads atribuídos</span>
            <strong>{member.assigned_leads}</strong>
          </div>
          <div>
            <BriefcaseBusiness size={16} />
            <span>Oportunidades abertas</span>
            <strong>{member.open_opportunities}</strong>
          </div>
          <div>
            <CheckCircle2 size={16} />
            <span>Conversão</span>
            <strong>{member.conversion_rate.toFixed(1)}%</strong>
          </div>
          <div>
            <CircleDollarSign size={16} />
            <span>Receita ganha</span>
            <strong>{currency(member.won_value)}</strong>
          </div>
        </div>
      </section>

      <section className="detail-section">
        <h3>Atividades</h3>
        <div className="detail-grid">
          <div>
            <span>Pendentes</span>
            <strong>{member.pending_activities}</strong>
          </div>
          <div>
            <span>Atrasadas</span>
            <strong className={member.overdue_activities > 0 ? "text-danger" : ""}>
              {member.overdue_activities}
            </strong>
          </div>
          <div>
            <span>Ganhos</span>
            <strong>{member.won_opportunities}</strong>
          </div>
          <div>
            <span>Perdidos</span>
            <strong>{member.lost_opportunities}</strong>
          </div>
        </div>
      </section>

      <TeamMemberPasswordReset key={`password:${workspaceId}:${member.public_id}`} workspaceId={workspaceId} member={member} />

      <TeamMemberSessions key={`${workspaceId}:${member.public_id}`} workspaceId={workspaceId} userId={member.public_id} />

      <section className="detail-section">
        <h3>Permissões</h3>
        <div className="permission-list">
          {(role?.permissions ?? []).map((permission) => (
            <div className="permission-item" key={permission}>
              <ShieldCheck size={15} />
              <div>
                <strong>{permissionLabels[permission] ?? permission}</strong>
                <span>{permission}</span>
              </div>
            </div>
          ))}
        </div>
      </section>
    </Drawer>
  );
}

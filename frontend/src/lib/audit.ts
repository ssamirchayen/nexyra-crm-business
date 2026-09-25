import type { AuditActorType } from "../types/audit";

export const auditActionLabels: Record<string, string> = {
  "workspace.created": "Empresa criada",
  "workspace.updated": "Empresa atualizada",
  "workspace.deactivated": "Empresa desativada",
  "segment_config.initialized": "Segmento inicializado",
  "segment_config.updated": "Configuração de segmento atualizada",
  "membership.created": "Membro adicionado",
  "membership.updated": "Acesso de membro atualizado",
  "membership.deactivated": "Membro desativado",
  "lead.created": "Lead criado",
  "lead.updated": "Lead atualizado",
  "lead.deactivated": "Lead desativado",
  "opportunity.created": "Oportunidade criada",
  "opportunity.updated": "Oportunidade atualizada",
  "opportunity.moved": "Oportunidade movimentada",
  "opportunity.won": "Oportunidade ganha",
  "opportunity.lost": "Oportunidade perdida",
  "activity.created": "Atividade criada",
  "activity.updated": "Atividade atualizada",
  "activity.completed": "Atividade concluída",
  "activity.cancelled": "Atividade cancelada",
  "integration.lead_intake": "Lead recebido por integração",
  "atlas.action.executed": "Ação do Atlas executada",
};

export const entityLabels: Record<string, string> = {
  workspace: "Empresa",
  segment_config: "Segmento",
  membership: "Membro",
  lead: "Lead",
  opportunity: "Oportunidade",
  activity: "Atividade",
  integration: "Integração",
  atlas_action: "Ação Atlas",
};

export const actorLabels: Record<string, string> = {
  system: "Sistema",
  user: "Usuário",
  atlas: "Atlas",
  integration: "Integração",
};

export const roleLabels: Record<string, string> = {
  admin: "Administrador",
  manager: "Gestor",
  seller: "Vendedor",
  operator: "Operador",
};

export function labelizeAuditAction(action: string) {
  return (
    auditActionLabels[action] ??
    action
      .split(".")
      .map((part) =>
        part
          .split("_")
          .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
          .join(" "),
      )
      .join(" · ")
  );
}

export function labelizeEntity(entityType: string) {
  return (
    entityLabels[entityType] ??
    entityType
      .split("_")
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(" ")
  );
}

export function actorLabel(actorType: AuditActorType) {
  return actorLabels[actorType] ?? actorType;
}

export function actorTone(actorType: AuditActorType) {
  if (actorType === "user") return "info" as const;
  if (actorType === "atlas") return "success" as const;
  if (actorType === "integration") return "warning" as const;
  return "neutral" as const;
}

export function formatAuditDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "medium",
  }).format(new Date(value));
}

export function formatAuditValue(value: unknown): string {
  if (value === null || value === undefined || value === "") {
    return "—";
  }

  if (typeof value === "boolean") {
    return value ? "Sim" : "Não";
  }

  if (typeof value === "object") {
    return JSON.stringify(value, null, 2) ?? "—";
  }

  return String(value);
}

export function auditChangedKeys(
  before: Record<string, unknown> | null,
  after: Record<string, unknown> | null,
) {
  const keys = new Set([
    ...Object.keys(before ?? {}),
    ...Object.keys(after ?? {}),
  ]);

  return [...keys].filter((key) => {
    const oldValue = before?.[key];
    const newValue = after?.[key];
    return JSON.stringify(oldValue) !== JSON.stringify(newValue);
  });
}

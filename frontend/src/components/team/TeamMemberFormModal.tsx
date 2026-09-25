import { useEffect, useMemo, useState } from "react";

import type {
  TeamMember,
  TeamMemberCreatePayload,
  TeamMemberUpdatePayload,
  TeamRole,
} from "../../types/team";
import { Button } from "../ui/Button";
import { Modal } from "../ui/Modal";

const roleLabels: Record<TeamRole, string> = {
  admin: "Administrador",
  manager: "Gestor",
  seller: "Vendedor",
  operator: "Operador",
};

type FormState = {
  name: string;
  email: string;
  role: TeamRole;
  active: boolean;
  initialPassword: string;
};

type TeamMemberFormModalProps = {
  open: boolean;
  allowedRoles: TeamRole[];
  canChangeStatus: boolean;
  mode: "create" | "edit";
  member: TeamMember | null;
  saving: boolean;
  error: string | null;
  onClose: () => void;
  onCreate: (payload: TeamMemberCreatePayload) => Promise<void>;
  onUpdate: (payload: TeamMemberUpdatePayload) => Promise<void>;
};

function initialState(member: TeamMember | null): FormState {
  if (member) {
    return {
      name: member.name,
      email: member.email,
      role: member.role,
      active: member.membership_active,
      initialPassword: "",
    };
  }

  return {
    name: "",
    email: "",
    role: "seller",
    active: true,
    initialPassword: "",
  };
}

export function TeamMemberFormModal({
  open,
  allowedRoles,
  canChangeStatus,
  mode,
  member,
  saving,
  error,
  onClose,
  onCreate,
  onUpdate,
}: TeamMemberFormModalProps) {
  const initial = useMemo(() => initialState(member), [member]);
  const [form, setForm] = useState<FormState>(initial);

  useEffect(() => {
    if (open) {
      setForm(initial);
    }
  }, [initial, open]);

  async function handleSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (mode === "create") {
      await onCreate({
        name: form.name.trim(),
        email: form.email.trim().toLowerCase(),
        role: form.role,
        initial_password: form.initialPassword || undefined,
      });
      return;
    }

    await onUpdate({
      role: form.role,
      ...(canChangeStatus ? { active: form.active } : {}),
    });
  }

  return (
    <Modal
      open={open}
      title={mode === "create" ? "Novo membro" : "Editar acesso"}
      description={
        mode === "create"
          ? "Adicione uma pessoa à equipe desta empresa."
          : "Atualize o papel e o vínculo do usuário neste workspace."
      }
      onClose={onClose}
      size="md"
    >
      <form className="team-form" onSubmit={handleSubmit}>
        {error && <div className="form-alert form-alert--error">{error}</div>}

        <div className="form-section">
          <div className="form-grid form-grid--2">
            <label className="field field--full">
              <span>Nome *</span>
              <input
                required
                minLength={2}
                value={form.name}
                disabled={mode === "edit"}
                onChange={(event) =>
                  setForm((current) => ({ ...current, name: event.target.value }))
                }
                placeholder="Nome completo"
              />
            </label>

            <label className="field field--full">
              <span>E-mail *</span>
              <input
                required
                type="email"
                value={form.email}
                disabled={mode === "edit"}
                onChange={(event) =>
                  setForm((current) => ({ ...current, email: event.target.value }))
                }
                placeholder="usuario@empresa.com"
              />
            </label>

            {mode === "create" && (
              <label className="field field--full">
                <span>Senha inicial</span>
                <input
                  type="password"
                  minLength={12}
                  maxLength={128}
                  autoComplete="new-password"
                  value={form.initialPassword}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      initialPassword: event.target.value,
                    }))
                  }
                  placeholder="Opcional · mínimo 12 caracteres"
                />
                <small>
                  Use maiúscula, minúscula, número e símbolo. A senha inicial será
                  temporária e deverá ser trocada no primeiro acesso.
                </small>
              </label>
            )}

            <label className="field">
              <span>Função</span>
              <select
                value={form.role}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    role: event.target.value as TeamRole,
                  }))
                }
              >
                {allowedRoles.map((role) => (
                  <option key={role} value={role}>
                    {roleLabels[role]}
                  </option>
                ))}
              </select>
            </label>

            {mode === "edit" && canChangeStatus && (
              <label className="field">
                <span>Status do vínculo</span>
                <select
                  value={form.active ? "active" : "inactive"}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      active: event.target.value === "active",
                    }))
                  }
                >
                  <option value="active">Ativo</option>
                  <option value="inactive">Inativo</option>
                </select>
              </label>
            )}
          </div>
        </div>

        <div className="team-role-help">
          <strong>Permissões por função</strong>
          <p>
            Administradores gerenciam todos os perfis e o status dos membros. Gestores
            podem criar e editar vendedores e operadores. Vendedores atuam no fluxo comercial e operadores
            possuem acesso operacional mais restrito.
          </p>
        </div>

        <div className="team-form__actions">
          <Button type="button" variant="secondary" disabled={saving} onClick={onClose}>
            Cancelar
          </Button>
          <Button type="submit" disabled={saving}>
            {saving ? "Salvando..." : mode === "create" ? "Adicionar membro" : "Salvar alterações"}
          </Button>
        </div>
      </form>
    </Modal>
  );
}

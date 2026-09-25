import {
  KeyRound,
  Laptop,
  Loader2,
  LogOut,
  RefreshCw,
  ShieldCheck,
  Smartphone,
} from "lucide-react";
import { type FormEvent, useCallback, useEffect, useMemo, useState } from "react";

import { Badge } from "../components/ui/Badge";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { useAuth } from "../contexts/AuthContext";
import { api } from "../lib/api";
import type {
  AuthMessageResponse,
  AuthSession,
  AuthSessionsRevokedResponse,
} from "../types/auth";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("pt-BR", {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(value));
}

function sessionDevice(userAgent: string | null) {
  const agent = (userAgent ?? "").toLowerCase();
  if (agent.includes("android") || agent.includes("iphone") || agent.includes("mobile")) {
    return { label: "Dispositivo móvel", icon: Smartphone };
  }
  return { label: "Computador", icon: Laptop };
}

export function SecurityPage() {
  const auth = useAuth();
  const [sessions, setSessions] = useState<AuthSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");

  const activeSessions = useMemo(
    () => sessions.filter((session) => !session.revoked_at),
    [sessions],
  );

  const loadSessions = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSessions(await api.get<AuthSession[]>("/auth/sessions"));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível carregar as sessões.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadSessions();
  }, [loadSessions]);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 3200);
    return () => window.clearTimeout(timer);
  }, [toast]);

  async function revokeOthers() {
    setBusy(true);
    setError(null);
    try {
      const response = await api.post<AuthSessionsRevokedResponse>(
        "/auth/sessions/revoke-others",
      );
      setToast(response.message);
      await loadSessions();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível encerrar as outras sessões.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function revokeSession(publicId: string) {
    setBusy(true);
    setError(null);
    try {
      const response = await api.post<AuthMessageResponse>(
        `/auth/sessions/${publicId}/revoke`,
      );
      setToast(response.message);
      await loadSessions();
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível encerrar a sessão.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (newPassword !== confirmation) {
      setError("A confirmação da nova senha não confere.");
      return;
    }

    setBusy(true);
    try {
      await auth.changePassword(currentPassword, newPassword);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível alterar a senha.",
      );
      setBusy(false);
    }
  }

  return (
    <div className="page-stack security-page">
      <header className="page-header page-header--with-action">
        <div>
          <p className="page-eyebrow">Conta e segurança</p>
          <h1>Segurança de acesso</h1>
          <p>Gerencie sua senha e as sessões conectadas ao Nexyra CRM.</p>
        </div>
        <Button variant="secondary" onClick={() => void loadSessions()} disabled={loading}>
          <RefreshCw size={16} className={loading ? "spin" : ""} />
          Atualizar
        </Button>
      </header>

      {error && (
        <div className="page-alert page-alert--error">
          <span>{error}</span>
          <button type="button" className="text-button" onClick={() => setError(null)}>
            Fechar
          </button>
        </div>
      )}

      <div className="security-grid">
        <Card
          title="Sessões conectadas"
          description="Revogue acessos que você não reconhece ou não utiliza mais."
          actions={<Badge tone="success">{activeSessions.length} ativa(s)</Badge>}
        >
          <div className="security-card-body">
            {loading ? (
              <div className="settings-loading">
                <Loader2 size={20} className="spin" />
                Carregando sessões...
              </div>
            ) : sessions.length === 0 ? (
              <div className="settings-inline-empty">
                <ShieldCheck size={19} />
                <div><strong>Nenhuma sessão encontrada</strong></div>
              </div>
            ) : (
              <div className="security-session-list">
                {sessions.map((session) => {
                  const device = sessionDevice(session.user_agent);
                  const DeviceIcon = device.icon;
                  return (
                    <article className="security-session" key={session.public_id}>
                      <div className="security-session__icon"><DeviceIcon size={18} /></div>
                      <div className="security-session__copy">
                        <div className="security-session__title">
                          <strong>{device.label}</strong>
                          {session.current && <Badge tone="success">Sessão atual</Badge>}
                          {session.revoked_at && <Badge tone="neutral">Encerrada</Badge>}
                        </div>
                        <span>{session.ip_address ?? "IP não identificado"}</span>
                        <small>
                          Criada em {formatDate(session.created_at)} · Último uso {formatDate(session.last_seen_at)}
                        </small>
                      </div>
                      {!session.current && !session.revoked_at && (
                        <button
                          type="button"
                          className="table-action-button table-action-button--danger"
                          disabled={busy}
                          onClick={() => void revokeSession(session.public_id)}
                          aria-label="Encerrar sessão"
                        >
                          <LogOut size={15} />
                        </button>
                      )}
                    </article>
                  );
                })}
              </div>
            )}
          </div>
          <div className="settings-card-footer">
            <span>A sessão atual permanece conectada.</span>
            <Button variant="secondary" onClick={() => void revokeOthers()} disabled={busy || activeSessions.length <= 1}>
              Encerrar outras sessões
            </Button>
          </div>
        </Card>

        <Card
          title="Alterar senha"
          description="Ao trocar a senha, todas as sessões — inclusive esta — serão encerradas."
        >
          <form className="security-password-form" onSubmit={changePassword}>
            <label className="field">
              <span>Senha atual</span>
              <input
                type="password"
                autoComplete="current-password"
                required
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </label>
            <label className="field">
              <span>Nova senha</span>
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
              />
              <small>Mínimo 12 caracteres, com maiúscula, minúscula, número e símbolo.</small>
            </label>
            <label className="field">
              <span>Confirmar nova senha</span>
              <input
                type="password"
                autoComplete="new-password"
                minLength={12}
                required
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>
            <div className="security-password-form__footer">
              <KeyRound size={16} />
              <Button type="submit" disabled={busy}>Alterar senha</Button>
            </div>
          </form>
        </Card>
      </div>

      {toast && <div className="toast toast--success">{toast}</div>}
    </div>
  );
}

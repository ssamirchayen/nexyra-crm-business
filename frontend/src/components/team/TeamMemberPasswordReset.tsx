import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { api } from "../../lib/api";
import type { TeamMember } from "../../types/team";
import { Button } from "../ui/Button";

type ResetResult = { temporary_password: string; message: string; must_change_password: boolean };

export function TeamMemberPasswordReset({ workspaceId, member }: { workspaceId: string; member: TeamMember }) {
  const { user, workspaces } = useAuth();
  const allowed = workspaces.find((item) => item.public_id === workspaceId)?.permissions.includes("members.reset_password");
  const [expanded, setExpanded] = useState(false);
  const [password, setPassword] = useState("");
  const [result, setResult] = useState<ResetResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);

  function close() {
    setExpanded(false); setPassword(""); setResult(null); setError("");
  }

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy) return;
    setBusy(true); setError("");
    try {
      const data = await api.post<ResetResult>(
        `/workspaces/${workspaceId}/members/${member.public_id}/reset-password`,
        { current_password: password },
      );
      if (mounted.current) setResult(data);
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : "Não foi possível redefinir a senha. Atualize a lista antes de tentar novamente.");
    } finally {
      if (mounted.current) { setBusy(false); setPassword(""); }
    }
  }

  if (!allowed || user?.public_id === member.public_id) return null;
  return <section className="detail-section" aria-busy={busy}>
    <h3>Redefinir senha</h3>
    <p>Gere uma senha temporária para {member.name}. Os acessos anteriores serão encerrados e a pessoa deverá trocar a senha ao entrar.</p>
    {!expanded ? <Button variant="secondary" disabled={!member.user_active || !member.membership_active} onClick={() => setExpanded(true)}>
      Redefinir senha do membro
    </Button> : result ? <div role="status">
      <p>{result.message}</p>
      <label className="field">
        <span>Senha temporária — guarde antes de fechar</span>
        <input readOnly value={result.temporary_password} autoComplete="off" onFocus={(event) => event.currentTarget.select()} />
      </label>
      <p>Esta senha não poderá ser consultada novamente após fechar este painel. Nenhum e-mail é enviado automaticamente.</p>
      <Button variant="secondary" onClick={close}>Já guardei, fechar</Button>
    </div> : <form className="team-form" onSubmit={(event) => void submit(event)}>
      <p>Confirme sua senha de administrador para autorizar esta alteração.</p>
      <label className="field">
        <span>Sua senha atual</span>
        <input required type="password" autoComplete="current-password" maxLength={128} value={password} disabled={busy} onChange={(event) => setPassword(event.target.value)} />
      </label>
      {error && <p role="alert" className="text-danger">{error}</p>}
      <div className="team-form__actions">
        <Button type="button" variant="secondary" disabled={busy} onClick={close}>Cancelar</Button>
        <Button type="submit" disabled={busy || !password}>{busy ? "Gerando…" : "Confirmar e gerar senha"}</Button>
      </div>
    </form>}
    {(!member.user_active || !member.membership_active) && <p>Reative o membro antes de redefinir a senha.</p>}
  </section>;
}

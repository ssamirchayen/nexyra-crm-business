import { useEffect, useRef, useState } from "react";
import { useAuth } from "../../contexts/AuthContext";
import { api } from "../../lib/api";
import type { AuthSession } from "../../types/auth";
import { Button } from "../ui/Button";

export function TeamMemberSessions({ workspaceId, userId }: { workspaceId: string; userId: string }) {
  const { workspaces } = useAuth();
  const allowed = workspaces.find((w) => w.public_id === workspaceId)?.permissions.includes("sessions.manage");
  const [sessions, setSessions] = useState<AuthSession[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const path = `/workspaces/${workspaceId}/members/${userId}/sessions`;

  async function load() {
    setBusy(true); setError(""); setNotice("");
    try {
      const result = await api.get<AuthSession[]>(path);
      if (mounted.current) setSessions(result);
    } catch (err) {
      if (mounted.current) { setSessions(null); setError(err instanceof Error ? err.message : "Não foi possível carregar as sessões."); }
    } finally { if (mounted.current) setBusy(false); }
  }

  async function revoke(session: AuthSession) {
    if (!window.confirm("Encerrar esta sessão? O usuário precisará entrar novamente nesse acesso.")) return;
    setBusy(true); setError(""); setNotice("");
    try {
      await api.post(`${path}/${session.public_id}/revoke`);
      if (mounted.current) {
        setSessions((items) => items?.filter((item) => item.public_id !== session.public_id) ?? null);
        setNotice("Sessão encerrada. Os demais acessos foram preservados.");
      }
    } catch (err) {
      if (mounted.current) setError(err instanceof Error ? err.message : "Não foi possível encerrar a sessão.");
    } finally { if (mounted.current) setBusy(false); }
  }

  if (!allowed) return null;
  return <section className="detail-section" aria-busy={busy}>
    <h3>Sessões ativas</h3>
    <p>Acessos ainda válidos; isso não significa que a pessoa esteja online. Exibimos até 100 sessões mais recentes.</p>
    <Button variant="secondary" disabled={busy} onClick={() => void load()}>
      {busy ? "Aguarde…" : sessions === null ? "Ver sessões" : "Atualizar sessões"}
    </Button>
    {error && <p role="alert" className="text-danger">{error}</p>}
    {notice && <p role="status">{notice}</p>}
    {sessions?.length === 0 && <p>Nenhuma sessão ativa.</p>}
    {sessions?.map((session) => <div className="detail-section" key={session.public_id}>
      <strong>{session.current ? "Seu acesso atual" : "Acesso do usuário"}</strong>
      <p style={{ overflowWrap: "anywhere" }}>{session.user_agent || "Navegador não informado"}</p>
      <p>Última atividade: {new Date(session.last_seen_at).toLocaleString("pt-BR")}</p>
      <p>Expira em: {new Date(session.expires_at).toLocaleString("pt-BR")}</p>
      <Button variant="secondary" disabled={busy || session.current} onClick={() => void revoke(session)}>
        Encerrar sessão
      </Button>
    </div>)}
  </section>;
}

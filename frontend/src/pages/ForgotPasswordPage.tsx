import { ArrowLeft, MailCheck, ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { Link } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

export function ForgotPasswordPage() {
  const auth = useAuth();
  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Recuperar acesso · Nexyra CRM";
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);

    try {
      const response = await auth.requestPasswordRecovery(email.trim());
      setMessage(response.message);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível solicitar a recuperação de acesso.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="public-auth-page">
      <section className="public-auth-card">
        <Link className="public-auth-back" to="/login">
          <ArrowLeft size={16} />
          Voltar para o login
        </Link>

        <div className="public-auth-brand">
          <div className="login-brand-mark">N</div>
          <div>
            <strong>Nexyra</strong>
            <span>CRM</span>
          </div>
        </div>

        {message ? (
          <div className="recovery-success-state">
            <div className="recovery-success-state__icon"><MailCheck size={24} /></div>
            <span className="page-eyebrow">Solicitação registrada</span>
            <h1>Confira as instruções de recuperação</h1>
            <p>{message}</p>
            {import.meta.env.DEV && (
              <div className="recovery-dev-note">
                <ShieldCheck size={17} />
                <span>
                  No ambiente local, o link de redefinição aparece no terminal em que
                  o backend do Nexyra CRM está rodando.
                </span>
              </div>
            )}
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setMessage(null)}
            >
              Solicitar novamente
            </button>
          </div>
        ) : (
          <>
            <div className="public-auth-header">
              <span className="page-eyebrow">Recuperação de acesso</span>
              <h1>Esqueceu sua senha?</h1>
              <p>
                Informe o e-mail do seu usuário. Por segurança, a resposta será a
                mesma mesmo que o endereço não esteja cadastrado.
              </p>
            </div>

            {error && <div className="auth-error" role="alert">{error}</div>}

            <form className="login-form" onSubmit={handleSubmit}>
              <label className="form-field">
                <span>E-mail</span>
                <input
                  autoComplete="email"
                  autoFocus
                  onChange={(event) => setEmail(event.target.value)}
                  placeholder="voce@empresa.com"
                  required
                  type="email"
                  value={email}
                />
              </label>
              <button
                className="button button--primary login-submit"
                disabled={submitting}
                type="submit"
              >
                {submitting ? "Enviando..." : "Enviar instruções"}
              </button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}

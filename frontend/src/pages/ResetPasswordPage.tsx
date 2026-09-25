import { ArrowLeft, CheckCircle2, Eye, EyeOff, KeyRound } from "lucide-react";
import { type FormEvent, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

export function ResetPasswordPage() {
  const auth = useAuth();
  const [searchParams] = useSearchParams();
  const token = useMemo(() => searchParams.get("token")?.trim() ?? "", [searchParams]);
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Redefinir senha · Nexyra CRM";
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!token) {
      setError("O link de recuperação não contém um token válido.");
      return;
    }
    if (newPassword !== confirmation) {
      setError("A confirmação da nova senha não confere.");
      return;
    }

    setSubmitting(true);
    try {
      await auth.resetPassword(token, newPassword);
      setSuccess(true);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível redefinir a senha.",
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
          <div><strong>Nexyra</strong><span>CRM</span></div>
        </div>

        {success ? (
          <div className="recovery-success-state">
            <div className="recovery-success-state__icon"><CheckCircle2 size={24} /></div>
            <span className="page-eyebrow">Senha atualizada</span>
            <h1>Acesso recuperado</h1>
            <p>
              Sua senha foi redefinida e todas as sessões anteriores foram encerradas.
            </p>
            <Link className="button button--primary" to="/login">Entrar no CRM</Link>
          </div>
        ) : (
          <>
            <div className="public-auth-header">
              <span className="page-eyebrow">Nova credencial</span>
              <h1>Defina uma nova senha</h1>
              <p>O link é de uso único e expira automaticamente.</p>
            </div>

            {!token && (
              <div className="auth-error" role="alert">
                Link de recuperação inválido. Solicite um novo link na tela de login.
              </div>
            )}
            {error && <div className="auth-error" role="alert">{error}</div>}

            <form className="login-form" onSubmit={handleSubmit}>
              <label className="form-field">
                <span>Nova senha</span>
                <div className="password-field">
                  <input
                    autoComplete="new-password"
                    minLength={12}
                    onChange={(event) => setNewPassword(event.target.value)}
                    required
                    type={showPassword ? "text" : "password"}
                    value={newPassword}
                  />
                  <button
                    aria-label={showPassword ? "Ocultar senha" : "Mostrar senha"}
                    onClick={() => setShowPassword((current) => !current)}
                    type="button"
                  >
                    {showPassword ? <EyeOff size={17} /> : <Eye size={17} />}
                  </button>
                </div>
              </label>

              <label className="form-field">
                <span>Confirmar nova senha</span>
                <input
                  autoComplete="new-password"
                  minLength={12}
                  onChange={(event) => setConfirmation(event.target.value)}
                  required
                  type={showPassword ? "text" : "password"}
                  value={confirmation}
                />
              </label>

              <div className="password-policy-note">
                <KeyRound size={16} />
                <span>12+ caracteres com maiúscula, minúscula, número e símbolo.</span>
              </div>

              <button
                className="button button--primary login-submit"
                disabled={submitting || !token}
                type="submit"
              >
                {submitting ? "Redefinindo..." : "Redefinir senha"}
              </button>
            </form>
          </>
        )}
      </section>
    </main>
  );
}

import { Eye, EyeOff, KeyRound, ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";

import { useAuth } from "../contexts/AuthContext";

export function ForcePasswordChangePage() {
  const auth = useAuth();
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Trocar senha · Nexyra CRM";
  }, []);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (newPassword !== confirmation) {
      setError("A confirmação da nova senha não confere.");
      return;
    }

    setSubmitting(true);
    try {
      await auth.changePassword(currentPassword, newPassword);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível alterar a senha.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-page__visual" aria-hidden="true">
        <div className="login-visual__content">
          <div className="login-brand">
            <div className="login-brand-mark">N</div>
            <div><strong>Nexyra</strong><span>CRM</span></div>
          </div>
          <div className="login-visual__copy">
            <span className="login-visual__eyebrow">Proteção da conta</span>
            <h1>Antes de continuar, defina uma senha pessoal.</h1>
            <p>
              A senha inicial é temporária. Após a troca, todas as sessões são
              encerradas e você entra novamente com a nova credencial.
            </p>
          </div>
          <div className="login-security-note">
            <ShieldCheck size={18} />
            <span>Política de senha reforçada e sessões revogáveis.</span>
          </div>
        </div>
      </section>

      <section className="login-page__form-area">
        <div className="login-card">
          <div className="login-card__header">
            <div className="login-card__icon"><KeyRound size={21} /></div>
            <span className="page-eyebrow">Troca obrigatória</span>
            <h2>Crie sua nova senha</h2>
            <p>Use no mínimo 12 caracteres, com maiúscula, minúscula, número e símbolo.</p>
          </div>

          {error && <div className="auth-error" role="alert">{error}</div>}

          <form className="login-form" onSubmit={handleSubmit}>
            <label className="form-field">
              <span>Senha atual</span>
              <input
                autoComplete="current-password"
                required
                type={showPassword ? "text" : "password"}
                value={currentPassword}
                onChange={(event) => setCurrentPassword(event.target.value)}
              />
            </label>
            <label className="form-field">
              <span>Nova senha</span>
              <div className="password-field">
                <input
                  autoComplete="new-password"
                  minLength={12}
                  required
                  type={showPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
                <button
                  type="button"
                  aria-label={showPassword ? "Ocultar senhas" : "Mostrar senhas"}
                  onClick={() => setShowPassword((current) => !current)}
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
                required
                type={showPassword ? "text" : "password"}
                value={confirmation}
                onChange={(event) => setConfirmation(event.target.value)}
              />
            </label>

            <button className="button button--primary login-submit" disabled={submitting} type="submit">
              {submitting ? "Alterando..." : "Alterar senha"}
            </button>
          </form>
        </div>
      </section>
    </main>
  );
}

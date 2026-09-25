import { Eye, EyeOff, LockKeyhole, ShieldCheck } from "lucide-react";
import { type FormEvent, useEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { useAuth } from "../contexts/AuthContext";

type LoginLocationState = {
  from?: {
    pathname?: string;
    search?: string;
    hash?: string;
  };
};

export function LoginPage() {
  const auth = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    document.title = "Entrar · Nexyra CRM";
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    auth.clearNotice();
    setSubmitting(true);

    try {
      await auth.login(email.trim(), password);

      const state = location.state as LoginLocationState | null;
      const from = state?.from;
      const destination = from?.pathname
        ? `${from.pathname}${from.search ?? ""}${from.hash ?? ""}`
        : "/overview";
      navigate(destination, { replace: true });
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Não foi possível entrar no Nexyra CRM.",
      );
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <main className="login-page">
      <section className="login-page__visual" aria-hidden="true">
        <div className="login-visual__content">
          <div className="login-brand">
            <div className="login-brand-mark">N</div>
            <div>
              <strong>Nexyra</strong>
              <span>CRM</span>
            </div>
          </div>
          <div className="login-visual__copy">
            <span className="login-visual__eyebrow">Operação comercial centralizada</span>
            <h1>Seu CRM, sua equipe e suas oportunidades em um único ambiente.</h1>
            <p>
              Leads, pipeline, atividades, relatórios e auditoria com acesso
              individual e seguro.
            </p>
          </div>
          <div className="login-security-note">
            <ShieldCheck size={18} />
            <span>Sessões protegidas e acesso vinculado ao usuário.</span>
          </div>
        </div>
      </section>

      <section className="login-page__form-area">
        <div className="login-card">
          <div className="login-card__header">
            <div className="login-card__icon"><LockKeyhole size={21} /></div>
            <span className="page-eyebrow">Acesso seguro</span>
            <h2>Entre no Nexyra CRM</h2>
            <p>Use o e-mail e a senha configurados para o seu usuário.</p>
          </div>

          {auth.notice && <div className="auth-notice">{auth.notice}</div>}
          {error && <div className="auth-error" role="alert">{error}</div>}

          <form className="login-form" onSubmit={handleSubmit}>
            <label className="form-field">
              <span>E-mail</span>
              <input
                autoComplete="email"
                autoFocus
                name="email"
                onChange={(event) => setEmail(event.target.value)}
                placeholder="voce@empresa.com"
                required
                type="email"
                value={email}
              />
            </label>

            <label className="form-field">
              <span>Senha</span>
              <div className="password-field">
                <input
                  autoComplete="current-password"
                  name="password"
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Digite sua senha"
                  required
                  type={showPassword ? "text" : "password"}
                  value={password}
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

            <div className="login-form__recovery">
              <Link to="/forgot-password">Esqueci minha senha</Link>
            </div>

            <button
              className="button button--primary login-submit"
              disabled={submitting}
              type="submit"
            >
              {submitting ? "Entrando..." : "Entrar"}
            </button>
          </form>

          <div className="login-card__footer">
            <ShieldCheck size={15} />
            <span>O acesso é validado pela API oficial do Nexyra CRM.</span>
          </div>
        </div>
      </section>
    </main>
  );
}

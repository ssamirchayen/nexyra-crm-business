import { LoaderCircle } from "lucide-react";

export function AuthLoadingPage() {
  return (
    <main className="auth-loading-page" aria-live="polite">
      <div className="auth-loading-card">
        <div className="login-brand-mark">N</div>
        <LoaderCircle className="auth-spinner" size={22} />
        <strong>Validando sua sessão</strong>
        <span>Conectando com segurança ao Nexyra CRM...</span>
      </div>
    </main>
  );
}

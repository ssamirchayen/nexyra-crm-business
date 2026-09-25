import { Component, type ErrorInfo, type ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";

type Props = { children: ReactNode };
type State = { hasError: boolean; message: string | null };

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false, message: null };

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error.message || "Erro desconhecido" };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Nexyra CRM frontend error", error, info);
  }

  render() {
    if (this.state.hasError) {
      return (
        <main className="system-error-page">
          <div className="system-error-card">
            <div className="system-error-card__icon">
              <AlertTriangle size={24} />
            </div>
            <h1>O CRM encontrou um erro inesperado</h1>
            <p>
              Seus dados não foram apagados. Recarregue a interface para tentar
              novamente.
            </p>
            {this.state.message && (
              <details className="system-error-details">
                <summary>Detalhes técnicos</summary>
                <code>{this.state.message}</code>
              </details>
            )}
            <button
              className="button button--primary"
              type="button"
              onClick={() => window.location.reload()}
            >
              <RefreshCw size={16} />
              Recarregar CRM
            </button>
          </div>
        </main>
      );
    }

    return this.props.children;
  }
}

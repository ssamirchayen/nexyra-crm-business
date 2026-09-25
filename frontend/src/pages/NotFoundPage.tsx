import { ArrowLeft, FileQuestion } from "lucide-react";
import { Link } from "react-router-dom";

export function NotFoundPage() {
  return (
    <div className="not-found-page">
      <div className="not-found-page__icon"><FileQuestion size={24} /></div>
      <p className="page-eyebrow">Erro 404</p>
      <h1>Página não encontrada</h1>
      <p>O endereço informado não corresponde a nenhuma área do Nexyra CRM.</p>
      <Link className="button button--primary" to="/overview">
        <ArrowLeft size={16} />
        Voltar para a visão geral
      </Link>
    </div>
  );
}

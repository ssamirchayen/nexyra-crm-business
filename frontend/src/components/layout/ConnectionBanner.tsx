import { RefreshCw, WifiOff } from "lucide-react";

type ConnectionBannerProps = {
  onRetry: () => void;
};

export function ConnectionBanner({ onRetry }: ConnectionBannerProps) {
  return (
    <div className="connection-banner" role="status">
      <div>
        <WifiOff size={16} />
        <span>API do Nexyra CRM indisponível. A interface continua aberta, mas os dados podem não atualizar.</span>
      </div>
      <button type="button" onClick={onRetry}>
        <RefreshCw size={14} />
        Tentar novamente
      </button>
    </div>
  );
}

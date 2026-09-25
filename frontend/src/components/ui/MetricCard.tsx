import type { LucideIcon } from "lucide-react";

type MetricCardProps = {
  label: string;
  value: string;
  helper: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
};

export function MetricCard({
  label,
  value,
  helper,
  icon: Icon,
  trend = "neutral",
}: MetricCardProps) {
  return (
    <article className="metric-card">
      <div className="metric-card__top">
        <div className="metric-card__icon">
          <Icon size={18} strokeWidth={1.8} />
        </div>
        <span className={`metric-card__trend metric-card__trend--${trend}`}>
          {helper}
        </span>
      </div>
      <div className="metric-card__body">
        <span className="metric-card__label">{label}</span>
        <strong className="metric-card__value">{value}</strong>
      </div>
    </article>
  );
}

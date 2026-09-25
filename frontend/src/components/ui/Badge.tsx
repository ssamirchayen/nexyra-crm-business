import type { PropsWithChildren } from "react";

type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info";

export function Badge({
  tone = "neutral",
  children,
}: PropsWithChildren<{ tone?: BadgeTone }>) {
  return <span className={`badge badge--${tone}`}>{children}</span>;
}

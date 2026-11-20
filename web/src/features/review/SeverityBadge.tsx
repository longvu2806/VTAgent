import type { Severity } from "@/api/types";
import { SEVERITY } from "@/lib/labels";

const STYLE: Record<Severity, string> = {
  high: "bg-caution text-white",
  medium: "bg-caution-soft text-caution",
  low: "bg-muted text-muted-foreground",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-xs font-medium ${STYLE[severity]}`}>{SEVERITY[severity]}</span>
  );
}

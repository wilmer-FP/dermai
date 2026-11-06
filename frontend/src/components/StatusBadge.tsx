import { STATUS_LABELS } from "../services/format";
import type { AnalysisStatus } from "../types/api";

export function StatusBadge({ status }: { status: AnalysisStatus }) {
  return <span className={`badge badge--${status}`}>{STATUS_LABELS[status]}</span>;
}

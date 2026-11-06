import type { AnalysisStatus } from "../types/api";

export const STATUS_LABELS: Record<AnalysisStatus, string> = {
  pending: "Pendiente",
  processing: "En proceso",
  completed: "Completado",
  failed: "Fallido",
};

const dateFormatter = new Intl.DateTimeFormat("es", { dateStyle: "medium", timeStyle: "short" });

export function formatDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const date = new Date(iso);
  return Number.isNaN(date.getTime()) ? "—" : dateFormatter.format(date);
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** Proporción 0–1 como porcentaje; "—" si aún no hay valor. */
export function formatRatio(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${(value * 100).toFixed(1)} %`;
}

/** Número con decimales fijos; "—" si no hay valor. */
export function formatNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  return value.toFixed(digits);
}

export function formatDimensions(width: number | null, height: number | null): string {
  return width && height ? `${width} × ${height} px` : "—";
}

/** Primeros 8 caracteres de un UUID, para mostrar referencias cortas. */
export function shortId(id: string): string {
  return id.slice(0, 8);
}

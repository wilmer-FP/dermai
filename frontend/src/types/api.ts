// Tipos de la API REST de DermAI. Reflejan los esquemas Pydantic de backend/app/schemas/.
// Los UUID y las fechas llegan como cadenas (ISO 8601).

export type AnalysisStatus = "pending" | "processing" | "completed" | "failed";

export const ANALYSIS_STATUSES: readonly AnalysisStatus[] = [
  "pending",
  "processing",
  "completed",
  "failed",
];

export interface HealthResponse {
  status: "ok";
  app: string;
  version: string;
  environment: string;
  /** Despliegue público: cada visitante solo ve sus imágenes y se borran solas. */
  demo_mode?: boolean;
  demo_retention_hours?: number | null;
}

export interface ImageRead {
  id: string;
  original_filename: string;
  content_type: string;
  file_size_bytes: number;
  width: number | null;
  height: number | null;
  checksum_sha256: string;
  created_at: string;
}

export interface AnalysisRead {
  id: string;
  image_id: string;
  model_version_id: string | null;
  status: AnalysisStatus;
  necrotic_area_ratio: number | null;
  confidence: number | null;
  result: Record<string, unknown> | null;
  error_message: string | null;
  created_at: string;
  completed_at: string | null;
  /** Si hay imagen procesada en GET /analyses/{id}/processed-image. */
  has_processed_image: boolean;
  /** Aviso de uso no diagnóstico que el backend añade a cada análisis. */
  disclaimer: string;
}

export interface ModelVersionRead {
  id: string;
  name: string;
  version: string;
  architecture: string | null;
  description: string | null;
  metrics: Record<string, unknown> | null;
  is_active: boolean;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface PageParams {
  limit?: number;
  offset?: number;
}

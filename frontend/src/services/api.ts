// Cliente HTTP de la API REST de DermAI.
// En desarrollo, Vite reenvía /api al backend (ver vite.config.ts).

import type {
  AnalysisRead,
  AnalysisStatus,
  HealthResponse,
  ImageRead,
  ModelVersionRead,
  Page,
  PageParams,
} from "../types/api";
import { SESSION_HEADER, getSessionId } from "./session";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/+$/, "");

/** Error de la API con el código HTTP y un mensaje listo para mostrar. `status` es 0 si no hubo respuesta. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const NETWORK_ERROR = "No se pudo conectar con el servidor. Comprueba que el backend está en marcha.";

function fallbackMessage(status: number): string {
  if (status === 404) return "Recurso no encontrado.";
  if (status === 413) return "El archivo supera el tamaño máximo permitido.";
  if (status === 415) return "Formato de archivo no permitido.";
  if (status === 503) return "El servicio no está disponible en este momento.";
  if (status === 502 || status === 504) return NETWORK_ERROR;
  if (status >= 500) return `Error interno del servidor (código ${status}).`;
  return `La petición falló (código ${status}).`;
}

/** Extrae el mensaje de `{ "detail": ... }`; FastAPI usa una cadena o, en errores de validación, una lista. */
async function readErrorMessage(response: Response): Promise<string> {
  try {
    const body: unknown = await response.json();
    const detail = (body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    if (Array.isArray(detail)) {
      const messages = detail
        .map((item) => (item as { msg?: unknown } | null)?.msg)
        .filter((msg): msg is string => typeof msg === "string");
      if (messages.length) return messages.join(" · ");
    }
  } catch {
    // Cuerpo vacío o no JSON: se usa el mensaje genérico.
  }
  return fallbackMessage(response.status);
}

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const query = search.toString();
  return query ? `?${query}` : "";
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { Accept: "application/json", [SESSION_HEADER]: getSessionId(), ...init.headers },
    });
  } catch {
    throw new ApiError(0, NETWORK_ERROR);
  }
  if (!response.ok) throw new ApiError(response.status, await readErrorMessage(response));
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

// ---------- Estado ----------

export function getHealth(): Promise<HealthResponse> {
  return request("/health");
}

// ---------- Imágenes ----------

export function uploadImage(file: File): Promise<ImageRead> {
  const body = new FormData();
  body.append("file", file, file.name);
  return request("/images", { method: "POST", body });
}

export function listImages(params: PageParams = {}): Promise<Page<ImageRead>> {
  return request(`/images${buildQuery({ ...params })}`);
}

export function getImage(imageId: string): Promise<ImageRead> {
  return request(`/images/${encodeURIComponent(imageId)}`);
}

/** `<img src>` no envía cabeceras: en las URLs de archivos la sesión va como parámetro. */
function withSession(url: string): string {
  return `${url}?session=${encodeURIComponent(getSessionId())}`;
}

/** URL del archivo de la imagen, para usar directamente en `<img src>`. */
export function imageFileUrl(imageId: string): string {
  return withSession(`${API_BASE_URL}/images/${encodeURIComponent(imageId)}/file`);
}

export function deleteImage(imageId: string): Promise<void> {
  return request(`/images/${encodeURIComponent(imageId)}`, { method: "DELETE" });
}

// ---------- Análisis ----------

export function requestAnalysis(imageId: string, modelVersionId: string | null = null): Promise<AnalysisRead> {
  return request(`/images/${encodeURIComponent(imageId)}/analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_version_id: modelVersionId }),
  });
}

export function listImageAnalyses(imageId: string, params: PageParams = {}): Promise<Page<AnalysisRead>> {
  return request(`/images/${encodeURIComponent(imageId)}/analyses${buildQuery({ ...params })}`);
}

export interface AnalysisListParams extends PageParams {
  status?: AnalysisStatus;
}

export function listAnalyses(params: AnalysisListParams = {}): Promise<Page<AnalysisRead>> {
  return request(`/analyses${buildQuery({ ...params })}`);
}

export function getAnalysis(analysisId: string): Promise<AnalysisRead> {
  return request(`/analyses/${encodeURIComponent(analysisId)}`);
}

/** URL de la imagen procesada (región y tejidos marcados), para `<img src>`. */
export function processedImageUrl(analysisId: string): string {
  return withSession(`${API_BASE_URL}/analyses/${encodeURIComponent(analysisId)}/processed-image`);
}

// ---------- Versiones de modelo ----------

export function listModelVersions(activeOnly = false): Promise<ModelVersionRead[]> {
  return request(`/model-versions${buildQuery({ active_only: activeOnly || undefined })}`);
}

// Cliente de datos de DermAI. Dos modos, elegidos al compilar con VITE_ANALYSIS_MODE:
// - "api" (por defecto): API REST del backend. En desarrollo, Vite reenvía /api (ver vite.config.ts).
// - "browser": todo ocurre en el navegador (OpenCV.js + IndexedDB); las imágenes no salen del dispositivo.

import type {
  AnalysisRead,
  AnalysisStatus,
  HealthResponse,
  ImageRead,
  ModelVersionRead,
  Page,
  PageParams,
} from "../types/api";
import { ApiError } from "./errors";
import { SESSION_HEADER, getSessionId } from "./session";

export { ApiError };

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "/api/v1").replace(/\/+$/, "");
export const ANALYSIS_MODE: "api" | "browser" = import.meta.env.VITE_ANALYSIS_MODE === "browser" ? "browser" : "api";

export function isBrowserMode(): boolean {
  return ANALYSIS_MODE === "browser";
}

/** El servicio local (y OpenCV.js) solo se descarga en modo navegador. */
const local = () => import("./localBackend");

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

export async function getHealth(): Promise<HealthResponse> {
  if (isBrowserMode()) return (await local()).getHealth();
  return request("/health");
}

// ---------- Imágenes ----------

export async function uploadImage(file: File): Promise<ImageRead> {
  if (isBrowserMode()) return (await local()).uploadImage(file);
  const body = new FormData();
  body.append("file", file, file.name);
  return request("/images", { method: "POST", body });
}

export async function listImages(params: PageParams = {}): Promise<Page<ImageRead>> {
  if (isBrowserMode()) return (await local()).listImages(params);
  return request(`/images${buildQuery({ ...params })}`);
}

export async function getImage(imageId: string): Promise<ImageRead> {
  if (isBrowserMode()) return (await local()).getImage(imageId);
  return request(`/images/${encodeURIComponent(imageId)}`);
}

/** `<img src>` no envía cabeceras: en las URLs de archivos la sesión va como parámetro. */
function withSession(url: string): string {
  return `${url}?session=${encodeURIComponent(getSessionId())}`;
}

/** URL del archivo de la imagen (modo API), para usar en `<img src>`. En modo navegador, ver useImageSource. */
export function imageFileUrl(imageId: string): string {
  return withSession(`${API_BASE_URL}/images/${encodeURIComponent(imageId)}/file`);
}

export async function deleteImage(imageId: string): Promise<void> {
  if (isBrowserMode()) return (await local()).deleteImage(imageId);
  return request(`/images/${encodeURIComponent(imageId)}`, { method: "DELETE" });
}

/** Modo navegador: archivo original o imagen procesada guardados en IndexedDB. */
export async function loadImageBlob(kind: "original" | "processed", id: string): Promise<Blob | null> {
  return (await local()).loadImageBlob(kind, id);
}

// ---------- Análisis ----------

export async function requestAnalysis(imageId: string, modelVersionId: string | null = null): Promise<AnalysisRead> {
  if (isBrowserMode()) return (await local()).requestAnalysis(imageId, modelVersionId);
  return request(`/images/${encodeURIComponent(imageId)}/analyses`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ model_version_id: modelVersionId }),
  });
}

export async function listImageAnalyses(imageId: string, params: PageParams = {}): Promise<Page<AnalysisRead>> {
  if (isBrowserMode()) return (await local()).listImageAnalyses(imageId, params);
  return request(`/images/${encodeURIComponent(imageId)}/analyses${buildQuery({ ...params })}`);
}

export interface AnalysisListParams extends PageParams {
  status?: AnalysisStatus;
}

export async function listAnalyses(params: AnalysisListParams = {}): Promise<Page<AnalysisRead>> {
  if (isBrowserMode()) return (await local()).listAnalyses(params);
  return request(`/analyses${buildQuery({ ...params })}`);
}

export async function getAnalysis(analysisId: string): Promise<AnalysisRead> {
  if (isBrowserMode()) return (await local()).getAnalysis(analysisId);
  return request(`/analyses/${encodeURIComponent(analysisId)}`);
}

/** URL de la imagen procesada (modo API), para `<img src>`. En modo navegador, ver useImageSource. */
export function processedImageUrl(analysisId: string): string {
  return withSession(`${API_BASE_URL}/analyses/${encodeURIComponent(analysisId)}/processed-image`);
}

// ---------- Versiones de modelo ----------

export async function listModelVersions(activeOnly = false): Promise<ModelVersionRead[]> {
  if (isBrowserMode()) return (await local()).listModelVersions();
  return request(`/model-versions${buildQuery({ active_only: activeOnly || undefined })}`);
}

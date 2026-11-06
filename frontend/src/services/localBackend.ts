// Modo navegador: implementa las mismas operaciones que la API REST, pero con IndexedDB y la
// heurística de OpenCV.js. Nada se envía a ningún servidor.

import { DISCLAIMER_TEXT } from "../components/Disclaimer";
import type { RgbImage } from "../analysis/heuristic";
import type { AnalysisRead, HealthResponse, ImageRead, Page, PageParams } from "../types/api";
import type { AnalysisListParams } from "./api";
import { ApiError } from "./errors";
import { validateImageFile } from "./imageValidation";
import {
  allAnalyses,
  allImages,
  deleteImageCascade,
  getStoredAnalysis,
  getStoredImage,
  putAnalysis,
  putImage,
  type StoredAnalysis,
  type StoredImage,
} from "./localStore";

export const APP_VERSION = "0.1.0";
/** Las fotos muy grandes se reducen antes del análisis (el pipeline trabaja a 512 px). */
export const MAX_DECODE_SIDE = 2048;
const STAMP_TEXTS = [
  "DermAI · resultado experimental, no es un diagnóstico médico",
  "DermAI · experimental, no diagnóstico",
  "No diagnóstico",
];

interface AnalysisOutputLike {
  necroticAreaRatio: number;
  result: Record<string, unknown>;
  overlay: RgbImage;
}

/** Partes que dependen del navegador (canvas, OpenCV.js). Las pruebas las sustituyen. */
export const browserRuntime = {
  decode: decodeToRgb,
  analyze: analyzeWithOpenCv,
  renderProcessed: renderProcessedPng,
};

// ---------- Utilidades ----------

function newId(): string {
  return crypto.randomUUID();
}

function now(): string {
  return new Date().toISOString();
}

function paginate<T>(items: T[], params: PageParams = {}): Page<T> {
  const limit = params.limit ?? 20;
  const offset = params.offset ?? 0;
  return { items: items.slice(offset, offset + limit), total: items.length, limit, offset };
}

function publicImage({ blob: _blob, ...image }: StoredImage): ImageRead {
  return image;
}

function publicAnalysis({ processed: _processed, ...analysis }: StoredAnalysis): AnalysisRead {
  return analysis;
}

function readBytes(blob: Blob): Promise<ArrayBuffer> {
  if (typeof blob.arrayBuffer === "function") return blob.arrayBuffer();
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as ArrayBuffer);
    reader.onerror = () => reject(reader.error);
    reader.readAsArrayBuffer(blob);
  });
}

async function sha256(blob: Blob): Promise<string> {
  const digest = await crypto.subtle.digest("SHA-256", await readBytes(blob));
  return Array.from(new Uint8Array(digest), (b) => b.toString(16).padStart(2, "0")).join("");
}

function contentTypeOf(file: File): string {
  if (file.type === "image/png" || /\.png$/i.test(file.name)) return "image/png";
  return "image/jpeg";
}

// ---------- Operaciones en el navegador (canvas + OpenCV.js) ----------

function makeCanvas(width: number, height: number): HTMLCanvasElement | OffscreenCanvas {
  if (typeof OffscreenCanvas !== "undefined") return new OffscreenCanvas(width, height);
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  return canvas;
}

/** Decodifica la imagen (aplicando la orientación EXIF) a RGB, reduciéndola si es muy grande. */
export async function decodeToRgb(blob: Blob): Promise<RgbImage> {
  let bitmap: ImageBitmap;
  try {
    bitmap = await createImageBitmap(blob, { imageOrientation: "from-image" });
  } catch {
    throw new ApiError(422, "El archivo no es una imagen válida o está dañado.");
  }
  const scale = Math.min(1, MAX_DECODE_SIDE / Math.max(bitmap.width, bitmap.height));
  const width = Math.max(1, Math.round(bitmap.width * scale));
  const height = Math.max(1, Math.round(bitmap.height * scale));
  const canvas = makeCanvas(width, height);
  const context = canvas.getContext("2d") as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D;
  context.drawImage(bitmap, 0, 0, width, height);
  bitmap.close();
  const rgba = context.getImageData(0, 0, width, height).data;
  const rgb = new Uint8Array(width * height * 3);
  for (let i = 0, j = 0; i < rgba.length; i += 4, j += 3) {
    rgb[j] = rgba[i];
    rgb[j + 1] = rgba[i + 1];
    rgb[j + 2] = rgba[i + 2];
  }
  return { data: rgb, width, height };
}

async function analyzeWithOpenCv(image: RgbImage): Promise<AnalysisOutputLike> {
  const [{ loadOpenCv }, { analyzeHeuristic }] = await Promise.all([
    import("../analysis/opencv"),
    import("../analysis/heuristic"),
  ]);
  const { cv } = await loadOpenCv();
  return analyzeHeuristic(cv, image);
}

/** Imagen procesada en PNG, con el aviso de uso no diagnóstico en una franja inferior. */
export async function renderProcessedPng(overlay: RgbImage): Promise<Blob> {
  const { width, height, data } = overlay;
  const canvas = makeCanvas(width, height);
  const context = canvas.getContext("2d") as CanvasRenderingContext2D | OffscreenCanvasRenderingContext2D;
  const rgba = new Uint8ClampedArray(width * height * 4);
  for (let i = 0, j = 0; j < data.length; i += 4, j += 3) {
    rgba[i] = data[j];
    rgba[i + 1] = data[j + 1];
    rgba[i + 2] = data[j + 2];
    rgba[i + 3] = 255;
  }
  context.putImageData(new ImageData(rgba, width, height), 0, 0);

  const band = Math.max(14, Math.round(height * 0.06));
  context.fillStyle = "rgba(0, 0, 0, 0.7)";
  context.fillRect(0, height - band, width, band);
  const fontSize = Math.max(9, Math.round(band * 0.6));
  context.font = `${fontSize}px system-ui, sans-serif`;
  context.fillStyle = "#ffffff";
  context.textBaseline = "middle";
  const text = STAMP_TEXTS.find((t) => context.measureText(t).width <= width - 12) ?? STAMP_TEXTS[STAMP_TEXTS.length - 1];
  context.fillText(text, 6, height - band / 2);

  if ("convertToBlob" in canvas) return canvas.convertToBlob({ type: "image/png" });
  return new Promise((resolve, reject) =>
    canvas.toBlob((blob) => (blob ? resolve(blob) : reject(new Error("No se pudo generar la imagen."))), "image/png"),
  );
}

// ---------- API equivalente ----------

export async function getHealth(): Promise<HealthResponse> {
  return {
    status: "ok",
    app: "DermAI",
    version: APP_VERSION,
    environment: "browser",
    demo_mode: false,
    demo_retention_hours: null,
    analysis_mode: "browser",
  };
}

export async function uploadImage(file: File): Promise<ImageRead> {
  const problem = validateImageFile(file);
  if (problem) throw new ApiError(422, problem);
  const decoded = await browserRuntime.decode(file);
  const image: StoredImage = {
    id: newId(),
    original_filename: file.name.replace(/\\/g, "/").split("/").pop()?.slice(0, 255) || "imagen",
    content_type: contentTypeOf(file),
    file_size_bytes: file.size,
    width: decoded.width,
    height: decoded.height,
    checksum_sha256: await sha256(file),
    created_at: now(),
    blob: file,
  };
  await putImage(image);
  return publicImage(image);
}

async function requireImage(imageId: string): Promise<StoredImage> {
  const image = await getStoredImage(imageId);
  if (!image) throw new ApiError(404, "Imagen no encontrada.");
  return image;
}

export async function listImages(params: PageParams = {}): Promise<Page<ImageRead>> {
  return paginate((await allImages()).map(publicImage), params);
}

export async function getImage(imageId: string): Promise<ImageRead> {
  return publicImage(await requireImage(imageId));
}

export async function deleteImage(imageId: string): Promise<void> {
  await requireImage(imageId);
  await deleteImageCascade(imageId);
}

export async function loadImageBlob(kind: "original" | "processed", id: string): Promise<Blob | null> {
  if (kind === "original") return (await getStoredImage(id))?.blob ?? null;
  return (await getStoredAnalysis(id))?.processed ?? null;
}

export async function requestAnalysis(imageId: string, modelVersionId: string | null = null): Promise<AnalysisRead> {
  const image = await requireImage(imageId);
  const record: StoredAnalysis = {
    id: newId(),
    image_id: imageId,
    model_version_id: modelVersionId,
    status: "failed",
    necrotic_area_ratio: null,
    confidence: null,
    result: null,
    error_message: null,
    created_at: now(),
    completed_at: null,
    has_processed_image: false,
    disclaimer: DISCLAIMER_TEXT,
    processed: null,
  };

  if (modelVersionId) {
    record.error_message = "El modelo experimental no está disponible en el análisis en el navegador.";
  } else {
    try {
      const output = await browserRuntime.analyze(await browserRuntime.decode(image.blob));
      record.processed = await browserRuntime.renderProcessed(output.overlay);
      record.status = "completed";
      record.necrotic_area_ratio = output.necroticAreaRatio;
      record.result = output.result;
      record.has_processed_image = true;
    } catch (error) {
      const detail = error instanceof Error && error.message ? ` ${error.message}` : "";
      record.error_message = `No se pudo procesar la imagen.${detail}`;
    }
  }
  record.completed_at = now();
  await putAnalysis(record);
  return publicAnalysis(record);
}

export async function listAnalyses(params: AnalysisListParams = {}): Promise<Page<AnalysisRead>> {
  const items = (await allAnalyses()).filter((a) => !params.status || a.status === params.status);
  return paginate(items.map(publicAnalysis), params);
}

export async function listImageAnalyses(imageId: string, params: PageParams = {}): Promise<Page<AnalysisRead>> {
  await requireImage(imageId);
  const items = (await allAnalyses()).filter((a) => a.image_id === imageId);
  return paginate(items.map(publicAnalysis), params);
}

export async function getAnalysis(analysisId: string): Promise<AnalysisRead> {
  const analysis = await getStoredAnalysis(analysisId);
  if (!analysis) throw new ApiError(404, "Análisis no encontrado.");
  return publicAnalysis(analysis);
}

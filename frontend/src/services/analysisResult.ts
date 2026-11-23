// Lectura tipada del campo `result` que generan la heurística (ai/preprocessing) y los modelos (ai/models).

export type TissueKey = "necrotic" | "slough" | "granulation" | "other";

export type TissueComposition = Record<TissueKey, number>;

export interface LegendItem {
  label: string;
  color: string;
  kind: "outline" | "fill";
}

export interface AnalysisResultData {
  method: { name: string; version: string; description?: string; type?: "model" | "heuristic" };
  tissue_composition: TissueComposition;
  class_composition?: Record<string, number>;
  confidence_definition?: string;
  model?: { architecture?: string; training_images?: number; device?: string };
  segmentation?: { roi_area_ratio?: number; fallback_full_image?: boolean; border_contact?: number };
  color?: { delta_e_to_skin_mean?: number; lesion_lab_mean?: number[]; skin_reference_lab?: number[] } | null;
  texture?: { contrast?: number; homogeneity?: number; energy?: number; correlation?: number; entropy?: number } | null;
  edges?: { edge_density?: number; gradient_mean?: number; border_gradient_mean?: number | null } | null;
  shape?: {
    area_ratio?: number;
    circularity?: number;
    solidity?: number;
    eccentricity?: number;
    aspect_ratio?: number;
  } | null;
  quality?: { sharpness?: number; glare_ratio?: number; lightness_mean?: number };
  warnings?: string[];
  legend?: LegendItem[];
}

/**
 * Grupos de tejido comunes a la heurística y al modelo.
 * La heurística mide color; el modelo predice clases de tejido aprendidas de máscaras anotadas.
 * Los colores coinciden con los de la imagen procesada.
 */
export const TISSUE_CLASSES: readonly { key: TissueKey; label: string; hint: string; color: string }[] = [
  { key: "necrotic", label: "Negro / marrón oscuro", hint: "compatible con tejido necrótico", color: "#c026d3" },
  { key: "slough", label: "Amarillo", hint: "compatible con esfacelo", color: "#eab308" },
  { key: "granulation", label: "Rojo", hint: "compatible con granulación o inflamación", color: "#dc2626" },
  { key: "other", label: "Otros tonos", hint: "", color: "#94a3b8" },
];

/** Etiquetas cuando el resultado viene de un modelo (clases de tejido, no colores). */
export const MODEL_TISSUE_LABELS: Record<TissueKey, { label: string; hint: string }> = {
  necrotic: { label: "Necrosis", hint: "predicción del modelo" },
  slough: { label: "Esfacelo", hint: "predicción del modelo" },
  granulation: { label: "Granulación", hint: "predicción del modelo" },
  other: { label: "Otros tejidos", hint: "maceración, tendón o hueso" },
};

export function isModelResult(result: AnalysisResultData): boolean {
  return result.method.type === "model";
}

/** Devuelve el resultado tipado si tiene la forma esperada, o `null`. */
export function readAnalysisResult(result: Record<string, unknown> | null): AnalysisResultData | null {
  if (!result) return null;
  const method = result.method as { name?: unknown } | undefined;
  const composition = result.tissue_composition as Record<string, unknown> | undefined;
  if (typeof method?.name !== "string" || typeof composition !== "object" || composition === null) return null;
  const complete = TISSUE_CLASSES.every(({ key }) => typeof composition[key] === "number");
  return complete ? (result as unknown as AnalysisResultData) : null;
}

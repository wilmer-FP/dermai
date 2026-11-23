import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router";
import { routes } from "../App";
import type { AnalysisRead, ImageRead, ModelVersionRead, Page } from "../types/api";

/** Renderiza la aplicación completa en la ruta indicada, con un router en memoria. */
export function renderAt(path: string, options: { applyAccept?: boolean } = {}) {
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const user = userEvent.setup({ applyAccept: options.applyAccept ?? true });
  const view = render(<RouterProvider router={router} />);
  return { ...view, router, user };
}

export function makeImage(overrides: Partial<ImageRead> = {}): ImageRead {
  return {
    id: "11111111-1111-4111-8111-111111111111",
    original_filename: "lesion.jpg",
    content_type: "image/jpeg",
    file_size_bytes: 2048,
    width: 640,
    height: 480,
    checksum_sha256: "a".repeat(64),
    created_at: "2026-11-05T10:00:00Z",
    ...overrides,
  };
}

export function makeAnalysis(overrides: Partial<AnalysisRead> = {}): AnalysisRead {
  return {
    id: "22222222-2222-4222-8222-222222222222",
    image_id: "11111111-1111-4111-8111-111111111111",
    model_version_id: null,
    status: "pending",
    necrotic_area_ratio: null,
    confidence: null,
    result: null,
    error_message: null,
    created_at: "2026-11-05T10:00:01Z",
    completed_at: null,
    has_processed_image: false,
    disclaimer: "Prototipo experimental con fines educativos. No es una herramienta de diagnóstico médico.",
    ...overrides,
  };
}

/** `result` con la forma que genera el pipeline heurístico de ai/preprocessing. */
export function makeHeuristicResult(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    method: { name: "dermai-opencv-heuristic", version: "0.1.0", description: "Método heurístico de prueba." },
    tissue_composition: { necrotic: 0.237, slough: 0.1, granulation: 0.5, other: 0.163 },
    segmentation: { roi_area_ratio: 0.3, fallback_full_image: false, border_contact: 0 },
    color: { delta_e_to_skin_mean: 31.2, lesion_lab_mean: [45.1, 30.2, 12.3] },
    texture: { contrast: 1.5, homogeneity: 0.7, entropy: 5.1 },
    edges: { edge_density: 0.04, border_gradient_mean: 80.5 },
    shape: { area_ratio: 0.3, circularity: 0.82, solidity: 0.97, eccentricity: 0.4 },
    quality: { sharpness: 140, glare_ratio: 0.01 },
    warnings: [],
    ...overrides,
  };
}

export function makeModelVersion(overrides: Partial<ModelVersionRead> = {}): ModelVersionRead {
  return {
    id: "44444444-4444-4444-8444-444444444444",
    name: "unet-resnet18-woundtissue",
    version: "0.1.0",
    architecture: "unet-resnet18",
    description: "Modelo de prueba.",
    metrics: {
      training_images: 13,
      evaluation: "validación cruzada de 5 particiones",
      cv_fold_dice_mean: 0.35,
      cv_fold_dice_std: 0.1,
      cv_mean_dice_foreground: 0.41,
      heuristic_mean_dice_foreground: 0.22,
      cv_necrotic_dice: 0.3,
      heuristic_necrotic_dice: 0.1,
      cv_necrotic_ratio_mae: 0.05,
      heuristic_necrotic_ratio_mae: 0.12,
      dataset: "WoundTissue (muestra pública, CC BY-NC-SA 4.0)",
    },
    is_active: true,
    created_at: "2026-11-05T09:00:00Z",
    ...overrides,
  };
}

export function makePage<T>(items: T[], overrides: Partial<Page<T>> = {}): Page<T> {
  return { items, total: items.length, limit: 10, offset: 0, ...overrides };
}

export function makeFile(name = "lesion.png", type = "image/png", size = 1024): File {
  return new File([new Uint8Array(size)], name, { type });
}

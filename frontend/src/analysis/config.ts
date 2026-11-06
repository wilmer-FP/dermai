// Parámetros de la heurística: mismos valores que ai/preprocessing/config.py.

export const METHOD_NAME = "dermai-opencv-heuristic";
export const METHOD_VERSION = "0.1.0";
export const METHOD_DESCRIPTION =
  "Segmentación por diferencia de color con la piel circundante y clasificación de " +
  "tejido por umbrales en CIELAB. Método heurístico sin validación clínica.";

export const TISSUE_THRESHOLDS = {
  necrotic_max_lightness: 40.0,
  necrotic_min_darkening: 25.0,
  necrotic_max_chroma: 35.0,
  slough_min_lightness: 50.0,
  slough_hue_range: [50.0, 115.0] as [number, number],
  slough_min_b: 18.0,
  slough_min_b_over_skin: 8.0,
  granulation_hue_range: [-30.0, 45.0] as [number, number],
  granulation_min_a: 15.0,
  granulation_min_a_over_skin: 8.0,
};

export const PIPELINE_CONFIG = {
  target_size: 512,
  shades_of_gray_power: 6.0,
  color_constancy_strength: 0.5,
  bilateral_diameter: 7,
  bilateral_sigma_color: 40.0,
  bilateral_sigma_space: 7.0,
  border_fraction: 0.08,
  min_lesion_delta_e: 8.0,
  min_roi_ratio: 0.005,
  max_roi_ratio: 0.95,
  glare_min_value: 235,
  glare_max_saturation: 30,
  glcm_levels: 32,
  tissue: TISSUE_THRESHOLDS,
};

export type PipelineConfig = typeof PIPELINE_CONFIG;

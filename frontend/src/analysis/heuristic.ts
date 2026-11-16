// Heurística de OpenCV en el navegador: port de ai/preprocessing (Python) a TypeScript + OpenCV.js.
// Replica los mismos pasos y parámetros; las pruebas comparan sus resultados con los de Python.
//
// Método heurístico y experimental: no es un diagnóstico médico.

import {
  METHOD_DESCRIPTION,
  METHOD_NAME,
  METHOD_VERSION,
  PIPELINE_CONFIG,
  type PipelineConfig,
} from "./config";
import { OPENCV_VERSION, type Cv } from "./opencv";

// Códigos de clase (iguales que ai/preprocessing/tissue.py)
export const EXCLUDED = 0;
export const NECROTIC = 1;
export const SLOUGH = 2;
export const GRANULATION = 3;
export const OTHER = 4;
const TISSUE_NAMES: Record<number, string> = { 1: "necrotic", 2: "slough", 3: "granulation", 4: "other" };

const ROI_COLOR = [80, 220, 80]; // RGB, verde
const OVERLAY: { code: number; color: [number, number, number]; alpha: number }[] = [
  { code: NECROTIC, color: [255, 0, 255], alpha: 0.55 }, // magenta
  { code: SLOUGH, color: [255, 215, 0], alpha: 0.45 }, // amarillo
];

export const HEURISTIC_LEGEND = [
  { label: "Región analizada", color: "#50dc50", kind: "outline" },
  { label: "Negro / marrón oscuro", color: "#ff00ff", kind: "fill" },
  { label: "Amarillo", color: "#ffd700", kind: "fill" },
];

/** Imagen RGB entrelazada (alto × ancho × 3). */
export interface RgbImage {
  data: Uint8Array;
  width: number;
  height: number;
}

export interface HeuristicOutput {
  necroticAreaRatio: number;
  result: Record<string, unknown>;
  overlay: RgbImage;
  roiMask: Uint8Array;
  labels: Uint8Array;
}

// ---------- Utilidades numéricas (mismo comportamiento que Python/NumPy) ----------

/** round() de Python: redondeo al par en los empates. */
export function pyRound(value: number): number {
  const floor = Math.floor(value);
  const diff = value - floor;
  if (diff === 0.5) return floor % 2 === 0 ? floor : floor + 1;
  return Math.round(value);
}

export function roundTo(value: number, digits = 4): number {
  const factor = 10 ** digits;
  return Math.round(value * factor) / factor;
}

/** Redondea recursivamente los números a 4 decimales, como _round() en Python. */
export function roundDeep(value: unknown): unknown {
  if (typeof value === "number") return Number.isInteger(value) ? value : roundTo(value);
  if (Array.isArray(value)) return value.map(roundDeep);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).map(([k, v]) => [k, roundDeep(v)]));
  }
  return value;
}

export function mean(values: ArrayLike<number>): number {
  let sum = 0;
  for (let i = 0; i < values.length; i++) sum += values[i];
  return values.length ? sum / values.length : 0;
}

export function std(values: ArrayLike<number>, average = mean(values)): number {
  let sum = 0;
  for (let i = 0; i < values.length; i++) sum += (values[i] - average) ** 2;
  return values.length ? Math.sqrt(sum / values.length) : 0;
}

/** Mediana de NumPy (media de los dos centrales si el número es par). */
export function median(values: Float64Array | number[]): number {
  const sorted = Float64Array.from(values).sort();
  const n = sorted.length;
  if (!n) return 0;
  const mid = n >> 1;
  return n % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
}

/** np.percentile con interpolación lineal. */
function percentile(sorted: Float64Array, q: number): number {
  const position = ((sorted.length - 1) * q) / 100;
  const low = Math.floor(position);
  const high = Math.ceil(position);
  return sorted[low] + (sorted[high] - sorted[low]) * (position - low);
}

function oddSize(value: number, minimum: number): number {
  const size = Math.max(minimum, pyRound(value));
  return size % 2 === 1 ? size : size + 1;
}

// ---------- Gestión de memoria de OpenCV.js ----------

export class MatScope {
  private mats: { delete(): void }[] = [];
  add<T extends { delete(): void }>(mat: T): T {
    this.mats.push(mat);
    return mat;
  }
  dispose(): void {
    for (const mat of this.mats.reverse()) mat.delete();
    this.mats = [];
  }
}

function maskToMat(cv: Cv, scope: MatScope, mask: Uint8Array, width: number, height: number) {
  return scope.add(cv.matFromArray(height, width, cv.CV_8UC1, mask));
}

function morph(cv: Cv, scope: MatScope, mask: Uint8Array, width: number, height: number, op: number, size: number) {
  const src = maskToMat(cv, scope, mask, width, height);
  const dst = scope.add(new cv.Mat());
  const kernel = scope.add(cv.getStructuringElement(cv.MORPH_ELLIPSE, new cv.Size(size, size)));
  cv.morphologyEx(src, dst, op, kernel);
  return Uint8Array.from(dst.data as Uint8Array);
}

// ---------- Preprocesamiento ----------

function resizeLongestSide(cv: Cv, scope: MatScope, src: Cv, target: number) {
  const scale = target / Math.max(src.rows, src.cols);
  if (scale === 1) return scope.add(src.clone());
  const size = new cv.Size(Math.max(1, pyRound(src.cols * scale)), Math.max(1, pyRound(src.rows * scale)));
  const dst = scope.add(new cv.Mat());
  cv.resize(src, dst, size, 0, 0, scale < 1 ? cv.INTER_AREA : cv.INTER_CUBIC);
  return dst;
}

function detectGlare(cv: Cv, scope: MatScope, rgb: Cv, config: PipelineConfig): Uint8Array {
  const hsv = scope.add(new cv.Mat());
  cv.cvtColor(rgb, hsv, cv.COLOR_RGB2HSV);
  const data = hsv.data as Uint8Array;
  const glare = new Uint8Array(rgb.rows * rgb.cols);
  for (let i = 0; i < glare.length; i++) {
    glare[i] = data[i * 3 + 2] >= config.glare_min_value && data[i * 3 + 1] <= config.glare_max_saturation ? 1 : 0;
  }
  return glare;
}

/** Constancia de color "Shades of Gray" (Finlayson y Trezzi, 2004), aplicada de forma parcial. */
export function shadesOfGray(rgb: Uint8Array, valid: Uint8Array | null, power: number, strength: number): Uint8Array {
  const pixels = rgb.length / 3;
  const useMask = valid !== null && valid.some((v) => v === 1);
  const sums = [0, 0, 0];
  let count = 0;
  for (let i = 0; i < pixels; i++) {
    if (useMask && !valid![i]) continue;
    for (let c = 0; c < 3; c++) sums[c] += rgb[i * 3 + c] ** power;
    count++;
  }
  const norm = sums.map((s) => (s / count) ** (1 / power));
  if (!norm.every((n) => Number.isFinite(n) && n > 0)) return Uint8Array.from(rgb);
  const length = Math.hypot(...norm);
  const exponent = Math.min(1, Math.max(0, strength));
  const gains = norm.map((n) => (1 / ((n / length) * Math.sqrt(3))) ** exponent);
  const out = new Uint8Array(rgb.length);
  for (let i = 0; i < rgb.length; i++) {
    out[i] = Math.floor(Math.min(255, Math.max(0, rgb[i] * gains[i % 3])));
  }
  return out;
}

interface Preprocessed {
  resized: Cv; // RGB uint8
  width: number;
  height: number;
  lab: Float32Array; // L*, a*, b* entrelazados
  gray: Uint8Array;
  grayMat: Cv;
  glare: Uint8Array;
}

export function preprocess(cv: Cv, scope: MatScope, input: RgbImage, config: PipelineConfig): Preprocessed {
  const src = scope.add(cv.matFromArray(input.height, input.width, cv.CV_8UC3, input.data));
  const resized = resizeLongestSide(cv, scope, src, config.target_size);
  const width = resized.cols;
  const height = resized.rows;
  const glare = detectGlare(cv, scope, resized, config);
  const valid = glare.map((g) => (g ? 0 : 1));

  const correctedData = shadesOfGray(
    resized.data as Uint8Array,
    valid,
    config.shades_of_gray_power,
    config.color_constancy_strength,
  );
  const corrected = scope.add(cv.matFromArray(height, width, cv.CV_8UC3, correctedData));
  const denoised = scope.add(new cv.Mat());
  cv.bilateralFilter(
    corrected,
    denoised,
    config.bilateral_diameter,
    config.bilateral_sigma_color,
    config.bilateral_sigma_space,
  );

  const floatImage = scope.add(new cv.Mat());
  denoised.convertTo(floatImage, cv.CV_32FC3, 1 / 255);
  const labMat = scope.add(new cv.Mat());
  cv.cvtColor(floatImage, labMat, cv.COLOR_RGB2Lab);

  const grayMat = scope.add(new cv.Mat());
  cv.cvtColor(corrected, grayMat, cv.COLOR_RGB2GRAY);

  return {
    resized,
    width,
    height,
    lab: Float32Array.from(labMat.data32F as Float32Array),
    gray: Uint8Array.from(grayMat.data as Uint8Array),
    grayMat,
    glare,
  };
}

// ---------- Segmentación ----------

function borderMask(width: number, height: number, fraction: number): Uint8Array {
  const margin = Math.max(1, pyRound(Math.min(height, width) * fraction));
  const mask = new Uint8Array(width * height);
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (y < margin || y >= height - margin || x < margin || x >= width - margin) mask[y * width + x] = 1;
    }
  }
  return mask;
}

/** Rellena los huecos interiores (conectividad 4, como cv2.floodFill). */
export function fillHoles(mask: Uint8Array, width: number, height: number): Uint8Array {
  const outside = new Uint8Array(width * height);
  const queue: number[] = [];
  const visit = (index: number) => {
    if (!mask[index] && !outside[index]) {
      outside[index] = 1;
      queue.push(index);
    }
  };
  for (let x = 0; x < width; x++) {
    visit(x);
    visit((height - 1) * width + x);
  }
  for (let y = 0; y < height; y++) {
    visit(y * width);
    visit(y * width + width - 1);
  }
  while (queue.length) {
    const index = queue.pop()!;
    const x = index % width;
    const y = (index - x) / width;
    if (x > 0) visit(index - 1);
    if (x < width - 1) visit(index + 1);
    if (y > 0) visit(index - width);
    if (y < height - 1) visit(index + width);
  }
  const filled = new Uint8Array(width * height);
  for (let i = 0; i < filled.length; i++) filled[i] = mask[i] || !outside[i] ? 1 : 0;
  return filled;
}

interface Segmentation {
  mask: Uint8Array;
  skin: [number, number, number];
  threshold: number | null;
  fallback: boolean;
  borderContact: number;
}

function segmentLesion(cv: Cv, scope: MatScope, pre: Preprocessed, valid: Uint8Array, config: PipelineConfig): Segmentation {
  const { width, height, lab } = pre;
  const n = width * height;
  const border = borderMask(width, height, config.border_fraction);

  const channels: number[][] = [[], [], []];
  const collect = (requireValid: boolean) => {
    for (let i = 0; i < n; i++) {
      if (border[i] && (!requireValid || valid[i])) for (let c = 0; c < 3; c++) channels[c].push(lab[i * 3 + c]);
    }
  };
  collect(true);
  if (!channels[0].length) collect(false);
  const skin = channels.map((values) => median(values)) as [number, number, number];

  const fallback = (): Segmentation => ({ mask: new Uint8Array(n).fill(1), skin, threshold: null, fallback: true, borderContact: 1 });

  const distance = new Float32Array(n);
  for (let i = 0; i < n; i++) {
    const dl = lab[i * 3] - skin[0];
    const da = lab[i * 3 + 1] - skin[1];
    const db = lab[i * 3 + 2] - skin[2];
    distance[i] = Math.sqrt((0.5 * dl) ** 2 + da ** 2 + db ** 2);
  }
  const distanceMat = scope.add(cv.matFromArray(height, width, cv.CV_32F, distance));
  const blurred = scope.add(new cv.Mat());
  const sigma = Math.max(1.0, 0.01 * Math.max(height, width));
  cv.GaussianBlur(distanceMat, blurred, new cv.Size(0, 0), sigma, sigma);
  const smooth = blurred.data32F as Float32Array;

  let maxDistance = 0;
  for (let i = 0; i < n; i++) maxDistance = Math.max(maxDistance, smooth[i]);
  if (maxDistance < config.min_lesion_delta_e) return fallback();

  const scaled = new Uint8Array(n);
  for (let i = 0; i < n; i++) scaled[i] = Math.floor(Math.min(255, Math.max(0, (smooth[i] / maxDistance) * 255)));
  const scaledMat = maskToMat(cv, scope, scaled, width, height);
  const otsuOut = scope.add(new cv.Mat());
  const otsu: number = cv.threshold(scaledMat, otsuOut, 0, 255, cv.THRESH_BINARY + cv.THRESH_OTSU);
  const threshold = Math.max((otsu / 255) * maxDistance, config.min_lesion_delta_e);

  let mask: Uint8Array = new Uint8Array(n);
  for (let i = 0; i < n; i++) mask[i] = smooth[i] > threshold && valid[i] ? 1 : 0;
  const longest = Math.max(height, width);
  mask = morph(cv, scope, mask, width, height, cv.MORPH_OPEN, oddSize(0.01 * longest, 3));
  mask = morph(cv, scope, mask, width, height, cv.MORPH_CLOSE, oddSize(0.03 * longest, 5));

  const labelsMat = scope.add(new cv.Mat());
  const stats = scope.add(new cv.Mat());
  const centroids = scope.add(new cv.Mat());
  const count: number = cv.connectedComponentsWithStats(
    maskToMat(cv, scope, mask, width, height),
    labelsMat,
    stats,
    centroids,
    8,
    cv.CV_32S,
  );
  if (count <= 1) return fallback();

  const statsData = stats.data32S as Int32Array;
  const centroidData = centroids.data64F as Float64Array;
  const cx = width / 2;
  const cy = height / 2;
  let best = 0;
  let bestScore = -1;
  for (let label = 1; label < count; label++) {
    const offset = Math.hypot((centroidData[label * 2] - cx) / cx, (centroidData[label * 2 + 1] - cy) / cy);
    const centrality = 1 - 0.5 * Math.min(1, offset / Math.SQRT2);
    const score = statsData[label * 5 + cv.CC_STAT_AREA] * centrality;
    if (score > bestScore) {
      best = label;
      bestScore = score;
    }
  }

  const labels = labelsMat.data32S as Int32Array;
  const component = new Uint8Array(n);
  for (let i = 0; i < n; i++) component[i] = labels[i] === best ? 1 : 0;
  const roi = fillHoles(component, width, height);

  let roiCount = 0;
  let contact = 0;
  let borderCount = 0;
  for (let i = 0; i < n; i++) {
    roiCount += roi[i];
    borderCount += border[i];
    if (roi[i] && border[i]) contact++;
  }
  const ratio = roiCount / n;
  if (ratio < config.min_roi_ratio || ratio > config.max_roi_ratio) return fallback();
  return { mask: roi, skin, threshold, fallback: false, borderContact: contact / borderCount };
}

// ---------- Clasificación por color ----------

function classifyTissue(
  cv: Cv,
  scope: MatScope,
  pre: Preprocessed,
  region: Uint8Array,
  skin: [number, number, number],
  config: PipelineConfig,
) {
  const t = config.tissue;
  const { width, height, lab } = pre;
  const n = width * height;
  const darkLimit = Math.min(t.necrotic_max_lightness, skin[0] - t.necrotic_min_darkening);
  const hue = new Float32Array(n);

  let necrotic: Uint8Array = new Uint8Array(n);
  for (let i = 0; i < n; i++) {
    const l = lab[i * 3];
    const a = lab[i * 3 + 1];
    const b = lab[i * 3 + 2];
    hue[i] = (Math.atan2(b, a) * 180) / Math.PI;
    necrotic[i] = region[i] && l < darkLimit && Math.hypot(a, b) < t.necrotic_max_chroma ? 1 : 0;
  }
  necrotic = morph(cv, scope, necrotic, width, height, cv.MORPH_OPEN, 5);

  const labels = new Uint8Array(n);
  const sloughMinB = Math.max(t.slough_min_b, skin[2] + t.slough_min_b_over_skin);
  const granulationMinA = Math.max(t.granulation_min_a, skin[1] + t.granulation_min_a_over_skin);
  let total = 0;
  const counts = [0, 0, 0, 0, 0];
  for (let i = 0; i < n; i++) {
    if (!region[i]) continue;
    total++;
    const l = lab[i * 3];
    const a = lab[i * 3 + 1];
    const b = lab[i * 3 + 2];
    let code = OTHER;
    if (necrotic[i]) code = NECROTIC;
    else if (l >= t.slough_min_lightness && hue[i] >= t.slough_hue_range[0] && hue[i] <= t.slough_hue_range[1] && b >= sloughMinB) {
      code = SLOUGH;
    } else if (hue[i] >= t.granulation_hue_range[0] && hue[i] <= t.granulation_hue_range[1] && a >= granulationMinA) {
      code = GRANULATION;
    }
    labels[i] = code;
    counts[code]++;
  }
  const ratios: Record<string, number> = {};
  for (const [code, name] of Object.entries(TISSUE_NAMES)) ratios[name] = total ? counts[Number(code)] / total : 0;
  return { labels, ratios };
}

// ---------- Características ----------

export function colorFeatures(lab: Float32Array, region: Uint8Array, skin: [number, number, number]) {
  const values: number[][] = [[], [], []];
  const chroma: number[] = [];
  const deltaE: number[] = [];
  for (let i = 0; i < region.length; i++) {
    if (!region[i]) continue;
    const l = lab[i * 3];
    const a = lab[i * 3 + 1];
    const b = lab[i * 3 + 2];
    values[0].push(l);
    values[1].push(a);
    values[2].push(b);
    chroma.push(Math.hypot(a, b));
    deltaE.push(Math.hypot(l - skin[0], a - skin[1], b - skin[2]));
  }
  return {
    lesion_lab_mean: values.map((v) => mean(v)),
    lesion_lab_std: values.map((v) => std(v)),
    lesion_chroma_mean: mean(chroma),
    skin_reference_lab: [...skin],
    delta_e_to_skin_mean: mean(deltaE),
  };
}

const GLCM_OFFSETS: [number, number][] = [
  [0, 1],
  [1, 1],
  [1, 0],
  [1, -1],
];

export function glcmFeatures(gray: Uint8Array, region: Uint8Array, width: number, height: number, levels = 32) {
  const names = ["contrast", "homogeneity", "energy", "correlation", "entropy"] as const;
  const zeros = Object.fromEntries(names.map((name) => [name, 0])) as Record<(typeof names)[number], number>;
  const values: number[] = [];
  for (let i = 0; i < gray.length; i++) if (region[i]) values.push(gray[i]);
  if (values.length < 16) return zeros;

  const sorted = Float64Array.from(values).sort();
  const low = percentile(sorted, 1);
  let high = percentile(sorted, 99);
  if (high <= low) high = low + 1;
  const quantized = new Int32Array(gray.length);
  for (let i = 0; i < gray.length; i++) {
    quantized[i] = Math.min(levels - 1, Math.max(0, Math.trunc(((gray[i] - low) / (high - low)) * levels)));
  }

  const accumulated = { ...zeros };
  let used = 0;
  for (const [dy, dx] of GLCM_OFFSETS) {
    const counts = new Float64Array(levels * levels);
    let pairs = 0;
    for (let y = 0; y + dy < height; y++) {
      for (let x = Math.max(0, -dx); x < width && x + dx < width; x++) {
        const a = y * width + x;
        const b = (y + dy) * width + x + dx;
        if (!region[a] || !region[b]) continue;
        counts[quantized[a] * levels + quantized[b]]++;
        pairs++;
      }
    }
    if (!pairs) continue;
    const matrix = new Float64Array(levels * levels);
    let sum = 0;
    for (let i = 0; i < levels; i++) {
      for (let j = 0; j < levels; j++) {
        const v = counts[i * levels + j] + counts[j * levels + i];
        matrix[i * levels + j] = v;
        sum += v;
      }
    }
    let mu = 0;
    for (let i = 0; i < levels; i++) for (let j = 0; j < levels; j++) mu += i * (matrix[i * levels + j] /= sum);
    let variance = 0;
    let contrast = 0;
    let homogeneity = 0;
    let energy = 0;
    let correlation = 0;
    let entropy = 0;
    for (let i = 0; i < levels; i++) {
      for (let j = 0; j < levels; j++) {
        const p = matrix[i * levels + j];
        variance += p * (i - mu) ** 2;
        contrast += p * (i - j) ** 2;
        homogeneity += p / (1 + Math.abs(i - j));
        energy += p * p;
        correlation += (i - mu) * (j - mu) * p;
        if (p > 0) entropy -= p * Math.log2(p);
      }
    }
    accumulated.contrast += contrast;
    accumulated.homogeneity += homogeneity;
    accumulated.energy += Math.sqrt(energy);
    accumulated.correlation += variance > 1e-12 ? correlation / variance : 1;
    accumulated.entropy += entropy;
    used++;
  }
  return Object.fromEntries(names.map((name) => [name, used ? accumulated[name] / used : 0])) as typeof zeros;
}

export function laplacianValues(cv: Cv, scope: MatScope, grayMat: Cv): Float64Array {
  const lap = scope.add(new cv.Mat());
  cv.Laplacian(grayMat, lap, cv.CV_64F);
  return Float64Array.from(lap.data64F as Float64Array);
}

export function selectValues(values: ArrayLike<number>, mask: Uint8Array): number[] {
  const out: number[] = [];
  for (let i = 0; i < mask.length; i++) if (mask[i]) out.push(values[i]);
  return out;
}

export function edgeFeatures(cv: Cv, scope: MatScope, pre: Preprocessed, region: Uint8Array, roiIsLesion: boolean) {
  const { width, height } = pre;
  const blurred = scope.add(new cv.Mat());
  cv.GaussianBlur(pre.grayMat, blurred, new cv.Size(0, 0), 1.0, 1.0);
  const blurredData = blurred.data as Uint8Array;
  const regionValues = selectValues(blurredData, region);
  const med = regionValues.length ? median(regionValues) : 0;
  const lower = Math.trunc(Math.max(0, 0.66 * med));
  let upper = Math.trunc(Math.min(255, 1.33 * med));
  if (upper <= lower) upper = Math.min(255, lower + 1);
  const edges = scope.add(new cv.Mat());
  cv.Canny(blurred, edges, lower, upper);

  const gx = scope.add(new cv.Mat());
  const gy = scope.add(new cv.Mat());
  cv.Sobel(blurred, gx, cv.CV_32F, 1, 0, 3);
  cv.Sobel(blurred, gy, cv.CV_32F, 0, 1, 3);
  const gxData = gx.data32F as Float32Array;
  const gyData = gy.data32F as Float32Array;
  const magnitude = new Float32Array(width * height);
  for (let i = 0; i < magnitude.length; i++) magnitude[i] = Math.hypot(gxData[i], gyData[i]);

  const edgeData = edges.data as Uint8Array;
  let area = 0;
  let edgeCount = 0;
  for (let i = 0; i < region.length; i++) {
    if (!region[i]) continue;
    area++;
    if (edgeData[i]) edgeCount++;
  }

  let borderGradient: number | null = null;
  if (roiIsLesion && area) {
    const eroded = scope.add(new cv.Mat());
    const kernel = scope.add(cv.Mat.ones(3, 3, cv.CV_8U));
    cv.erode(maskToMat(cv, scope, region, width, height), eroded, kernel);
    const erodedData = eroded.data as Uint8Array;
    const boundary = region.map((r, i) => (r && !erodedData[i] ? 1 : 0));
    const values = selectValues(magnitude, boundary);
    borderGradient = values.length ? mean(values) : 0;
  }

  return {
    edge_density: area ? edgeCount / area : 0,
    gradient_mean: area ? mean(selectValues(magnitude, region)) : 0,
    border_gradient_mean: borderGradient,
  };
}

function largestContour(cv: Cv, scope: MatScope, mask: Uint8Array, width: number, height: number) {
  const contours = scope.add(new cv.MatVector());
  const hierarchy = scope.add(new cv.Mat());
  cv.findContours(maskToMat(cv, scope, mask, width, height), contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE);
  let best: Cv = null;
  let bestArea = -1;
  for (let i = 0; i < contours.size(); i++) {
    const contour = scope.add(contours.get(i));
    const area = cv.contourArea(contour);
    if (area > bestArea) {
      best = contour;
      bestArea = area;
    }
  }
  return { contours, best };
}

export function shapeFeatures(cv: Cv, scope: MatScope, roi: Uint8Array, width: number, height: number) {
  const { best: contour } = largestContour(cv, scope, roi, width, height);
  const area: number = cv.contourArea(contour);
  const perimeter: number = cv.arcLength(contour, true);
  const hull = scope.add(new cv.Mat());
  cv.convexHull(contour, hull, false, true);
  const hullArea: number = cv.contourArea(hull);

  const moments = cv.moments(maskToMat(cv, scope, roi, width, height), true);
  let eccentricity = 0;
  if (moments.m00 > 0) {
    const mu20 = moments.mu20 / moments.m00;
    const mu02 = moments.mu02 / moments.m00;
    const mu11 = moments.mu11 / moments.m00;
    const spread = Math.sqrt(4 * mu11 ** 2 + (mu20 - mu02) ** 2);
    const major = (mu20 + mu02 + spread) / 2;
    const minor = (mu20 + mu02 - spread) / 2;
    eccentricity = major > 0 ? Math.sqrt(Math.max(0, 1 - minor / major)) : 0;
  }
  const rect = cv.minAreaRect(contour);
  const short = Math.min(rect.size.width, rect.size.height);
  const long = Math.max(rect.size.width, rect.size.height);

  return {
    area_ratio: mean(roi),
    perimeter_px: perimeter,
    circularity: perimeter > 0 ? Math.min(1, (4 * Math.PI * area) / perimeter ** 2) : 0,
    solidity: hullArea > 0 ? area / hullArea : 0,
    eccentricity,
    aspect_ratio: short > 0 ? long / short : 0,
  };
}

export function variance(values: ArrayLike<number>): number {
  return std(values) ** 2;
}

// ---------- Avisos ----------

export function qualityWarnings(originalWidth: number, originalHeight: number, quality: Record<string, number>): string[] {
  const messages: string[] = [];
  if (Math.min(originalWidth, originalHeight) < 200) {
    messages.push("Resolución baja (menos de 200 px); los resultados son menos fiables.");
  }
  if (quality.sharpness < 20) messages.push("La imagen parece desenfocada.");
  if (quality.lightness_mean < 25) messages.push("La imagen es muy oscura.");
  else if (quality.lightness_mean > 90) messages.push("La imagen parece sobreexpuesta.");
  if (quality.glare_ratio > 0.05) messages.push("Hay reflejos de luz; esos píxeles se excluyeron del análisis.");
  return messages;
}

// ---------- Visualización ----------

function renderOverlay(cv: Cv, scope: MatScope, pre: Preprocessed, roi: Uint8Array, labels: Uint8Array, drawRoi: boolean): RgbImage {
  const { width, height } = pre;
  const base = pre.resized.data as Uint8Array;
  const out = new Uint8Array(base.length);
  for (let i = 0; i < width * height; i++) {
    const style = OVERLAY.find((o) => o.code === labels[i]);
    for (let c = 0; c < 3; c++) {
      const value = base[i * 3 + c];
      out[i * 3 + c] = style ? Math.trunc(Math.fround(Math.fround(value * (1 - style.alpha)) + Math.fround(style.color[c] * style.alpha))) : value;
    }
  }
  if (drawRoi) {
    const canvas = scope.add(cv.matFromArray(height, width, cv.CV_8UC3, out));
    const { contours } = largestContour(cv, scope, roi, width, height);
    cv.drawContours(canvas, contours, -1, new cv.Scalar(ROI_COLOR[0], ROI_COLOR[1], ROI_COLOR[2], 255), 2, cv.LINE_AA);
    return { data: Uint8Array.from(canvas.data as Uint8Array), width, height };
  }
  return { data: out, width, height };
}

// ---------- Pipeline completo ----------

/** Analiza una imagen RGB y devuelve el mismo formato de resultado que ai.preprocessing.analyze_image. */
export function analyzeHeuristic(cv: Cv, image: RgbImage, config: PipelineConfig = PIPELINE_CONFIG): HeuristicOutput {
  const scope = new MatScope();
  try {
    const pre = preprocess(cv, scope, image, config);
    const { width, height } = pre;
    const valid = pre.glare.map((g) => (g ? 0 : 1));
    const seg = segmentLesion(cv, scope, pre, valid, config);
    let region = seg.mask.map((m, i) => (m && valid[i] ? 1 : 0));
    if (!region.some((r) => r === 1)) region = seg.mask;

    const tissue = classifyTissue(cv, scope, pre, region, seg.skin, config);
    const lap = laplacianValues(cv, scope, pre.grayMat);
    const lightness = new Float32Array(width * height);
    for (let i = 0; i < lightness.length; i++) lightness[i] = pre.lab[i * 3];
    const quality = {
      lightness_mean: mean(lightness),
      lightness_std: std(lightness),
      sharpness: variance(lap),
      glare_ratio: mean(pre.glare),
    };

    const warnings: string[] = [];
    if (seg.fallback) warnings.push("No se distinguió una lesión del fondo; se analizó la imagen completa.");
    else if (seg.borderContact > 0.25) {
      warnings.push("La lesión llega a los bordes de la imagen; la referencia de piel sana puede no ser fiable.");
    }
    warnings.push(...qualityWarnings(image.width, image.height, quality));

    const result = {
      method: { name: METHOD_NAME, version: METHOD_VERSION, description: METHOD_DESCRIPTION },
      preprocessing: {
        original_size: [image.width, image.height],
        processed_size: [width, height],
        color_constancy: `shades_of_gray(p=${config.shades_of_gray_power}, strength=${config.color_constancy_strength})`,
        denoising: "bilateral",
        runtime: `navegador (OpenCV.js ${OPENCV_VERSION})`,
      },
      segmentation: {
        roi_area_ratio: mean(seg.mask),
        fallback_full_image: seg.fallback,
        border_contact: seg.borderContact,
        threshold_delta_e: seg.threshold,
      },
      tissue_composition: tissue.ratios,
      color: colorFeatures(pre.lab, region, seg.skin),
      texture: {
        ...glcmFeatures(pre.gray, region, width, height, config.glcm_levels),
        laplacian_variance: variance(selectValues(lap, region)),
      },
      edges: edgeFeatures(cv, scope, pre, region, !seg.fallback),
      shape: seg.fallback ? null : shapeFeatures(cv, scope, seg.mask, width, height),
      quality,
      warnings,
      legend: HEURISTIC_LEGEND,
      config,
    };

    return {
      necroticAreaRatio: roundTo(tissue.ratios.necrotic),
      result: roundDeep(result) as Record<string, unknown>,
      overlay: renderOverlay(cv, scope, pre, seg.mask, tissue.labels, !seg.fallback),
      roiMask: seg.mask,
      labels: tissue.labels,
    };
  } finally {
    scope.dispose();
  }
}

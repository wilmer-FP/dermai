// Port of ai/models/inference.py. ONNX returns logits; interpolation follows softmax.
import * as ort from "onnxruntime-web/wasm";
import wasmUrl from "onnxruntime-web/ort-wasm-simd-threaded.wasm?url";
import mjsUrl from "onnxruntime-web/ort-wasm-simd-threaded.mjs?url";
import manifest from "../../public/models/dermai/manifest.json";
import { PIPELINE_CONFIG } from "./config";
import { loadOpenCv, type Cv } from "./opencv";
import { MatScope, preprocess, pyRound, mean, std, median, variance, roundDeep, roundTo,
  colorFeatures, glcmFeatures, laplacianValues, selectValues, edgeFeatures, shapeFeatures,
  qualityWarnings, type RgbImage } from "./heuristic";

export { manifest };
export const CONFIDENCE_DEFINITION = "Media, sobre los píxeles de herida, de la probabilidad que el modelo asigna a la clase predicha. No está calibrada: no es la probabilidad de que el resultado sea correcto.";
let sessionPromise: Promise<ort.InferenceSession> | null = null;

async function getSession() {
  sessionPromise ??= (async () => {
    ort.env.wasm.numThreads = 1; // GitHub Pages has no COOP/COEP headers.
    ort.env.wasm.wasmPaths = { wasm: wasmUrl, mjs: mjsUrl };
    const response = await fetch(`${import.meta.env.BASE_URL}models/dermai/${manifest.file}`);
    if (!response.ok) throw new Error(`No se pudo descargar el modelo (HTTP ${response.status}).`);
    const bytes = await response.arrayBuffer();
    const hash = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)), b => b.toString(16).padStart(2, "0")).join("");
    if (bytes.byteLength !== manifest.bytes || hash !== manifest.sha256) throw new Error("El modelo descargado no coincide con su firma SHA-256.");
    return ort.InferenceSession.create(bytes, { executionProviders: ["wasm"], graphOptimizationLevel: "all" });
  })().catch(error => { sessionPromise = null; throw error; });
  return sessionPromise;
}

/** Exposed for parity tests; production executes in a dedicated worker. */
export async function analyzeModel(image: RgbImage, suppliedSession?: ort.InferenceSession, suppliedCv?: Cv) {
  const started = performance.now();
  const session = suppliedSession ?? await getSession();
  const cv = suppliedCv ?? (await loadOpenCv()).cv;
  const loadedMs = performance.now() - started;
  const scope = new MatScope();
  let input: ort.Tensor | undefined;
  let outputs: ort.InferenceSession.ReturnType | undefined;
  try {
    const pre = preprocess(cv, scope, image, PIPELINE_CONFIG);
    const { width, height } = pre;
    const scale = manifest.input_size / Math.max(width, height);
    const w = Math.max(1, pyRound(width * scale)), h = Math.max(1, pyRound(height * scale));
    const resized = scope.add(new cv.Mat());
    cv.resize(pre.resized, resized, new cv.Size(w, h), 0, 0, cv.INTER_LINEAR);
    const n = w * h, data = new Float32Array(3 * n);
    const means = new Float32Array([0.485, 0.456, 0.406]);
    const deviations = new Float32Array([0.229, 0.224, 0.225]);
    for (let c = 0; c < 3; c++) for (let i = 0; i < n; i++) {
      data[c * n + i] = Math.fround(Math.fround(Math.fround(resized.data[i * 3 + c] / 255) - means[c]) / deviations[c]);
    }
    input = new ort.Tensor("float32", data, [1, 3, h, w]);
    const inferenceStart = performance.now();
    outputs = await session.run({ image: input });
    const inferenceMs = performance.now() - inferenceStart;
    const logits = outputs.logits.data as Float32Array;
    if (logits.length !== 7 * n || logits.some(v => !Number.isFinite(v))) throw new Error("Salida inválida del modelo.");
    const probabilities = new Float32Array(logits.length);
    for (let i = 0; i < n; i++) {
      let max = -Infinity, sum = 0;
      for (let c = 0; c < 7; c++) max = Math.max(max, logits[c * n + i]);
      for (let c = 0; c < 7; c++) { probabilities[c * n + i] = Math.exp(logits[c * n + i] - max); sum += probabilities[c * n + i]; }
      for (let c = 0; c < 7; c++) probabilities[c * n + i] /= sum;
    }
    const pixels = width * height, labels = new Uint8Array(pixels), top = new Float32Array(pixels);
    for (let c = 0; c < 7; c++) {
      const src = new cv.Mat(h, w, cv.CV_32FC1), dst = new cv.Mat();
      try {
        src.data32F.set(probabilities.subarray(c * n, (c + 1) * n));
        cv.resize(src, dst, new cv.Size(width, height), 0, 0, cv.INTER_LINEAR);
        for (let i = 0; i < pixels; i++) if (dst.data32F[i] > top[i]) { top[i] = dst.data32F[i]; labels[i] = c; }
      } finally { src.delete(); dst.delete(); }
    }
    const wound = labels.map(c => c ? 1 : 0), woundRatio = mean(wound);
    const woundPixels = wound.reduce((a, b) => a + b, 0), hasWound = woundRatio >= 0.002;
    const counts = new Uint32Array(7);
    for (const c of labels) counts[c]++;
    const composition: Record<string, number> = { necrotic: 0, slough: 0, granulation: 0, other: 0 };
    const classes: Record<string, number> = {};
    for (let c = 1; c < 7; c++) {
      const details = manifest.class_details[c];
      classes[details.key] = woundPixels ? counts[c] / woundPixels : 0;
      composition[details.group] += classes[details.key];
    }
    const confidence = hasWound ? mean(selectValues(top, wound)) : mean(top);
    const lap = laplacianValues(cv, scope, pre.grayMat);
    const lightness = new Float32Array(pixels);
    for (let i = 0; i < pixels; i++) lightness[i] = pre.lab[i * 3];
    const quality = { lightness_mean: mean(lightness), lightness_std: std(lightness), sharpness: variance(lap), glare_ratio: mean(pre.glare) };
    let region = wound.map((v, i) => hasWound && v && !pre.glare[i] ? 1 : 0);
    if (hasWound && !region.some(Boolean)) region = wound;
    const skinMask = wound.map((v, i) => !v && !pre.glare[i] ? 1 : 0);
    const skin: [number, number, number] = [0, 0, 0];
    for (let c = 0; c < 3; c++) {
      const values: number[] = [];
      const any = skinMask.some(Boolean);
      for (let i = 0; i < pixels; i++) if (!any || skinMask[i]) values.push(pre.lab[i * 3 + c]);
      skin[c] = median(values);
    }
    const warnings = qualityWarnings(image.width, image.height, quality);
    if (!hasWound) warnings.unshift("El modelo no detectó tejido de herida en la imagen.");
    warnings.push(`Modelo de prueba de concepto entrenado con solo ${manifest.training_images} imágenes; sus resultados no son fiables.`);
    const overlayMat = scope.add(pre.resized.clone());
    for (let i = 0; i < pixels; i++) if (labels[i]) {
      for (let c = 0; c < 3; c++) overlayMat.data[i * 3 + c] = Math.floor(overlayMat.data[i * 3 + c] * 0.5 + manifest.class_details[labels[i]].color[c] * 0.5);
    }
    const mask = scope.add(cv.matFromArray(height, width, cv.CV_8UC1, wound));
    const contours = scope.add(new cv.MatVector()), hierarchy = scope.add(new cv.Mat());
    cv.findContours(mask, contours, hierarchy, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE);
    cv.drawContours(overlayMat, contours, -1, new cv.Scalar(80, 220, 80, 255), 2, cv.LINE_AA);
    const result = {
      method: { name: manifest.name, version: manifest.version, type: "model", description: manifest.description },
      model: { architecture: manifest.architecture, classes: manifest.classes, input_size: manifest.input_size,
        training_images: manifest.training_images, device: "navegador · ONNX Runtime Web / WASM", sha256: manifest.sha256 },
      confidence_definition: CONFIDENCE_DEFINITION,
      segmentation: { roi_area_ratio: woundRatio, fallback_full_image: false },
      tissue_composition: composition, class_composition: classes,
      color: hasWound ? colorFeatures(pre.lab, region, skin) : null,
      texture: hasWound ? { ...glcmFeatures(pre.gray, region, width, height), laplacian_variance: variance(selectValues(lap, region)) } : null,
      edges: hasWound ? edgeFeatures(cv, scope, pre, region, true) : null,
      shape: hasWound ? shapeFeatures(cv, scope, wound, width, height) : null,
      quality, warnings,
      legend: [{ label: "Herida detectada", color: "#50dc50", kind: "outline" }, ...manifest.class_details.slice(1).map(c => ({
        label: c.label, color: `#${c.color.map(v => v.toString(16).padStart(2, "0")).join("")}`, kind: "fill" }))],
      performance: { load_ms: loadedMs, inference_ms: inferenceMs, total_ms: performance.now() - started,
        model_bytes: manifest.bytes },
    };
    return { necroticAreaRatio: roundTo(composition.necrotic), confidence: roundTo(confidence),
      result: roundDeep(result) as Record<string, unknown>, labels, roiMask: wound,
      overlay: { data: Uint8Array.from(overlayMat.data), width, height } };
  } finally {
    input?.dispose();
    if (outputs) for (const tensor of Object.values(outputs)) tensor.dispose();
    scope.dispose();
  }
}

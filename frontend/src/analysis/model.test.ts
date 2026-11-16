// @vitest-environment node
import { readFileSync, writeFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import * as ort from "onnxruntime-web";
import { analyzeModel } from "./model";
import { loadOpenCv, type Cv } from "./opencv";

vi.mock("./opencv-module", async () => {
  const { createRequire } = await import("node:module");
  const cv = createRequire(import.meta.url)("@techstark/opencv-js");
  return { getOpenCvModule: () => cv };
});

let session: ort.InferenceSession, cv: Cv;
const measurements: Record<string, unknown>[] = [];
const baseline = process.memoryUsage();
beforeAll(async () => {
  ort.env.wasm.numThreads = 1;
  session = await ort.InferenceSession.create(new Uint8Array(readFileSync(new URL("../../public/models/dermai/model.onnx", import.meta.url))), { executionProviders: ["wasm"] });
  ({ cv } = await loadOpenCv());
}, 60_000);
afterAll(async () => {
  if (process.env.DERMAI_BENCHMARK_REPORT) writeFileSync(process.env.DERMAI_BENCHMARK_REPORT,
    JSON.stringify({ runtime: "ONNX Runtime Web WASM in Node (not browser process memory)",
      baseline, measurements }, null, 2));
  await session?.release();
});

for (const name of ["wound", "dark_skin", "red_lesion", "uniform"]) {
  it(`WASM + OpenCV.js reproduces PyTorch preprocessing and postprocessing: ${name}`, async () => {
    const dir = new URL("./__fixtures__/", import.meta.url);
    const rgb = new Uint8Array(gunzipSync(readFileSync(new URL(`${name}.rgb.gz`, dir))));
    const labels = gunzipSync(readFileSync(new URL(`${name}.model.labels.gz`, dir)));
    const ref = JSON.parse(readFileSync(new URL(`${name}.model.json`, dir), "utf-8"));
    const output = await analyzeModel({ data: rgb, width: 320, height: 240 }, session, cv);
    expect(output.labels.length).toBe(labels.length);
    let same = 0;
    for (let i = 0; i < labels.length; i++) if (labels[i] === output.labels[i]) same++;
    expect(same / labels.length).toBeGreaterThanOrEqual(0.999);
    expect(output.confidence).toBeCloseTo(ref.confidence, 3);
    expect(output.necroticAreaRatio).toBeCloseTo(ref.necrotic_area_ratio, 3);
    const result = output.result as typeof ref.result;
    for (const [key, value] of Object.entries(ref.result.class_composition)) {
      expect(result.class_composition[key]).toBeCloseTo(value as number, 3);
    }
    expect(result.method.type).toBe("model");
    expect(result.warnings).toEqual(ref.result.warnings);
    expect(result.segmentation.fallback_full_image).toBe(false);
    measurements.push({ name, label_agreement: same / labels.length, ...result.performance, memory: process.memoryUsage() });
  }, 60_000);
}

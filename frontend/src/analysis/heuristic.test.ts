// @vitest-environment node
// Paridad con Python: las referencias las genera scripts/generate-browser-fixtures.py con ai/preprocessing.
import { readFileSync } from "node:fs";
import { gunzipSync } from "node:zlib";
import { analyzeHeuristic, fillHoles, glcmFeatures, pyRound, shadesOfGray } from "./heuristic";
import { loadOpenCv, type Cv } from "./opencv";

// El ejecutor de módulos de Vitest espera ("await") los imports y el objeto de OpenCV.js tiene un
// método `then`; en las pruebas se carga con require() de Node, igual que lo haría un script.
vi.mock("./opencv-module", async () => {
  const { createRequire } = await import("node:module");
  const cv = createRequire(import.meta.url)("@techstark/opencv-js");
  return { getOpenCvModule: () => cv };
});

interface Expected {
  width: number;
  height: number;
  labels_shape: [number, number];
  necrotic_area_ratio: number;
  result: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
}

const FIXTURES = new URL("./__fixtures__/", import.meta.url);
const expected: Record<string, Expected> = JSON.parse(readFileSync(new URL("expected.json", FIXTURES), "utf-8"));
const fixture = (name: string, kind: "rgb" | "labels") =>
  new Uint8Array(gunzipSync(readFileSync(new URL(`${name}.${kind}.gz`, FIXTURES))));

let cv: Cv;
beforeAll(async () => {
  ({ cv } = await loadOpenCv());
}, 60_000);

describe.each(Object.keys(expected))("paridad con Python: %s", (name) => {
  const reference = expected[name];
  const run = () =>
    analyzeHeuristic(cv, { data: fixture(name, "rgb"), width: reference.width, height: reference.height });

  it("clasifica los píxeles igual que Python (≥ 99 % de coincidencia)", () => {
    const output = run();
    const pythonLabels = fixture(name, "labels");
    expect(output.labels.length).toBe(pythonLabels.length);
    let equal = 0;
    for (let i = 0; i < pythonLabels.length; i++) if (output.labels[i] === pythonLabels[i]) equal++;
    expect(equal / pythonLabels.length).toBeGreaterThanOrEqual(0.99);
  });

  it("obtiene la misma composición, segmentación y avisos", () => {
    const { result, necroticAreaRatio } = run();
    const py = reference.result;
    expect(necroticAreaRatio).toBeCloseTo(reference.necrotic_area_ratio, 2);
    for (const [key, value] of Object.entries(py.tissue_composition as Record<string, number>)) {
      expect((result.tissue_composition as Record<string, number>)[key], key).toBeCloseTo(value, 2);
    }
    const seg = result.segmentation as Record<string, number | boolean | null>;
    expect(seg.fallback_full_image).toBe(py.segmentation.fallback_full_image);
    expect(seg.roi_area_ratio as number).toBeCloseTo(py.segmentation.roi_area_ratio, 2);
    expect(result.warnings).toEqual(py.warnings);
    expect(result.preprocessing).toMatchObject({
      original_size: py.preprocessing.original_size,
      processed_size: py.preprocessing.processed_size,
    });
  });

  it("calcula características parecidas a las de Python", () => {
    const { result } = run();
    const py = reference.result;
    const close = (actual: number, target: number, relative = 0.05, absolute = 0.02) =>
      expect(Math.abs(actual - target)).toBeLessThanOrEqual(Math.max(absolute, Math.abs(target) * relative));

    const color = result.color as Record<string, number | number[]>;
    (color.lesion_lab_mean as number[]).forEach((v, i) => close(v, py.color.lesion_lab_mean[i], 0.03, 0.5));
    close(color.delta_e_to_skin_mean as number, py.color.delta_e_to_skin_mean, 0.03, 0.5);

    const texture = result.texture as Record<string, number>;
    for (const key of ["contrast", "homogeneity", "energy", "entropy"]) close(texture[key], py.texture[key], 0.08);

    const quality = result.quality as Record<string, number>;
    close(quality.lightness_mean, py.quality.lightness_mean, 0.02, 0.5);
    close(quality.glare_ratio, py.quality.glare_ratio, 0.05, 0.002);

    if (py.shape) {
      const shape = result.shape as Record<string, number>;
      for (const key of ["area_ratio", "circularity", "solidity", "eccentricity", "aspect_ratio"]) {
        close(shape[key], py.shape[key], 0.03);
      }
    } else {
      expect(result.shape).toBeNull();
    }
  });
});

describe("resultado del análisis en el navegador", () => {
  it("tiene las mismas secciones que el de Python y es serializable", () => {
    const reference = expected.wound;
    const { result, overlay } = analyzeHeuristic(cv, {
      data: fixture("wound", "rgb"),
      width: reference.width,
      height: reference.height,
    });
    const keys = Object.keys(JSON.parse(JSON.stringify(result))).sort();
    expect(keys).toEqual([...Object.keys(reference.result), "config"].sort());
    expect((result.method as { name: string }).name).toBe("dermai-opencv-heuristic");
    expect((result.preprocessing as { runtime: string }).runtime).toMatch(/OpenCV\.js/);
    expect(overlay.width).toBe(reference.labels_shape[1]);
    expect(overlay.data.length).toBe(overlay.width * overlay.height * 3);
  });

  it("marca el tejido necrótico en magenta en la imagen procesada", () => {
    const reference = expected.wound;
    const output = analyzeHeuristic(cv, { data: fixture("wound", "rgb"), width: reference.width, height: reference.height });
    const { width, height, data } = output.overlay;
    const center = (Math.floor(height / 2) * width + Math.floor(width / 2)) * 3;
    expect(output.labels[center / 3]).toBe(1);
    expect(data[center]).toBeGreaterThan(120); // R
    expect(data[center + 1]).toBeLessThan(60); // G
    expect(data[center + 2]).toBeGreaterThan(120); // B
  });
});

describe("utilidades", () => {
  it("redondea como Python (al par en los empates)", () => {
    expect([0.5, 1.5, 2.5, 2.4, 2.6, 15.36].map(pyRound)).toEqual([0, 2, 2, 2, 3, 15]);
  });

  it("rellena huecos interiores sin tocar el exterior", () => {
    const mask = new Uint8Array(25);
    for (const i of [6, 7, 8, 11, 13, 16, 17, 18]) mask[i] = 1; // anillo 3×3 con hueco en el 12
    const filled = fillHoles(mask, 5, 5);
    expect(filled[12]).toBe(1);
    expect(filled[0]).toBe(0);
  });

  it("corrige una dominante de color y no cambia nada con fuerza 0", () => {
    const rgb = new Uint8Array(300);
    for (let i = 0; i < 100; i++) rgb.set([96, 128, 166], i * 3); // gris con dominante azul
    const corrected = shadesOfGray(rgb, null, 6, 1);
    expect(Math.max(...corrected.slice(0, 3)) - Math.min(...corrected.slice(0, 3))).toBeLessThan(3);
    expect(shadesOfGray(rgb, null, 6, 0)).toEqual(rgb);
  });

  it("calcula la GLCM de regiones uniformes y de tablero", () => {
    const region = new Uint8Array(32 * 32).fill(1);
    const flat = glcmFeatures(new Uint8Array(32 * 32).fill(100), region, 32, 32);
    expect(flat.contrast).toBe(0);
    expect(flat.energy).toBeCloseTo(1);
    const checker = Uint8Array.from({ length: 32 * 32 }, (_, i) => (((i % 32) + Math.floor(i / 32)) % 2) * 255);
    expect(glcmFeatures(checker, region, 32, 32).contrast).toBeGreaterThan(100);
  });
});

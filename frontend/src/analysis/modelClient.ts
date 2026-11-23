import type { RgbImage } from "./heuristic";
import type { analyzeModel } from "./model";

export function analyzeInWorker(image: RgbImage): Promise<Awaited<ReturnType<typeof analyzeModel>>> {
  // Release all WASM memory after each analysis, including on failure or timeout.
  return new Promise((resolve, reject) => {
    const worker = new Worker(new URL("./model.worker.ts", import.meta.url), { type: "module" });
    const finish = () => { clearTimeout(timeout); worker.terminate(); };
    const timeout = setTimeout(() => { finish(); reject(new Error("El modelo superó 3 minutos. Intenta de nuevo en un dispositivo con más memoria.")); }, 180_000);
    worker.onerror = event => { finish(); reject(new Error(event.message || "No se pudo ejecutar el modelo en este navegador.")); };
    worker.onmessage = event => { finish(); if (event.data.error) reject(new Error(event.data.error)); else resolve(event.data.output); };
    worker.postMessage(image, [image.data.buffer]);
  });
}

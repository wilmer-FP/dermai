import { analyzeModel } from "./model";
import type { RgbImage } from "./heuristic";
self.onmessage = async (event: MessageEvent<RgbImage>) => {
  try { self.postMessage({ output: await analyzeModel(event.data) }); }
  catch (error) { self.postMessage({ error: error instanceof Error ? error.message : String(error) }); }
};

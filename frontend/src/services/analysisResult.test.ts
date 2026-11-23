import { makeHeuristicResult } from "../test/utils";
import { isModelResult, readAnalysisResult } from "./analysisResult";

describe("readAnalysisResult", () => {
  it("reconoce el resultado de la heurística y el de un modelo", () => {
    const heuristic = makeHeuristicResult();
    const model = makeHeuristicResult({ method: { name: "unet", version: "0.1.0", type: "model" } });

    expect(readAnalysisResult(heuristic)).toBe(heuristic);
    expect(isModelResult(readAnalysisResult(heuristic)!)).toBe(false);
    expect(isModelResult(readAnalysisResult(model)!)).toBe(true);
  });

  it("devuelve null para resultados vacíos o con otra forma", () => {
    expect(readAnalysisResult(null)).toBeNull();
    expect(readAnalysisResult({ regions: 2 })).toBeNull();
    expect(readAnalysisResult(makeHeuristicResult({ tissue_composition: { necrotic: 0.1 } }))).toBeNull();
  });
});

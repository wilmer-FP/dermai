// Import estático de OpenCV.js, aislado en su propio módulo para cargarlo de forma perezosa.
// El objeto de OpenCV.js tiene un método `then`: si se devolviera desde un import() dinámico o un
// `await`, JavaScript intentaría tratarlo como una promesa y fallaría. Por eso se expone con una función.
import cvModule from "@techstark/opencv-js";

export function getOpenCvModule(): unknown {
  return cvModule;
}

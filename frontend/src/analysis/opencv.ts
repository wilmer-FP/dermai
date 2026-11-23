// Carga perezosa de OpenCV.js (≈13 MB): solo se descarga la primera vez que se analiza una imagen.

// OpenCV.js no tiene tipos completos para todas las funciones que se usan; se trata como dinámico
// y su uso queda encapsulado en src/analysis/.
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export type Cv = any;

export const OPENCV_VERSION = "5.0.0";
const LOAD_TIMEOUT_MS = 60_000;

let loading: Promise<{ cv: Cv }> | null = null;

function isRealPromise(value: unknown): value is Promise<unknown> {
  return Object.prototype.toString.call(value) === "[object Promise]";
}

/** Espera a que el runtime de WebAssembly esté listo (callback o, de respaldo, sondeo). */
function waitForRuntime(cv: Cv): Promise<void> {
  return new Promise<void>((resolve, reject) => {
    const started = Date.now();
    let done = false;
    const finish = () => {
      if (!done) {
        done = true;
        resolve();
      }
    };
    const previous = cv.onRuntimeInitialized;
    cv.onRuntimeInitialized = () => {
      previous?.();
      finish();
    };
    const poll = () => {
      if (done) return;
      if (cv.Mat) return finish();
      if (Date.now() - started > LOAD_TIMEOUT_MS) {
        done = true;
        reject(new Error("No se pudo cargar OpenCV.js."));
        return;
      }
      setTimeout(poll, 50);
    };
    poll();
  });
}

/**
 * Devuelve OpenCV.js listo para usar. Se envuelve en un objeto porque el módulo tiene un método
 * `then` y no puede devolverse directamente desde una promesa.
 */
export function loadOpenCv(): Promise<{ cv: Cv }> {
  loading ??= (async () => {
    const { getOpenCvModule } = await import("./opencv-module");
    let cv: Cv = getOpenCvModule();
    if (isRealPromise(cv)) cv = await cv; // algunas versiones exportan una promesa del módulo
    if (!cv.Mat) await waitForRuntime(cv);
    return { cv };
  })();
  loading.catch(() => {
    loading = null; // permite reintentar si falló la descarga
  });
  return loading;
}

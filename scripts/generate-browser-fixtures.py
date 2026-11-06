"""Genera las imágenes de referencia para comprobar que el análisis en el navegador (TypeScript +
OpenCV.js) reproduce el pipeline de Python (ai/preprocessing).

Uso (desde la raíz del proyecto):
    .\\backend\\.venv\\Scripts\\python scripts\\generate-browser-fixtures.py

Escribe en frontend/src/analysis/__fixtures__/:
- <nombre>.rgb.gz: píxeles RGB sin cabecera (alto × ancho × 3, uint8), comprimidos.
- <nombre>.labels.gz: mapa de clases de la heurística (uint8) al tamaño procesado.
- expected.json: tamaños y resultados de Python para cada imagen.
"""

import gzip
import json
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ai.preprocessing import analyze_image  # noqa: E402

OUT = ROOT / "frontend" / "src" / "analysis" / "__fixtures__"
SIZE = (240, 320)  # alto, ancho
CENTER = (160, 120)


def noisy(image: np.ndarray, sigma: float, seed: int) -> np.ndarray:
    noise = np.random.default_rng(seed).normal(0, sigma, image.shape)
    return np.clip(image + noise, 0, 255).astype(np.uint8)


def wound() -> np.ndarray:
    image = np.full((*SIZE, 3), (150, 170, 215), np.uint8)  # BGR: piel clara
    cv2.ellipse(image, CENTER, (100, 70), 0, 0, 360, (70, 70, 190), -1)
    cv2.ellipse(image, CENTER, (65, 45), 0, 0, 360, (90, 200, 225), -1)
    cv2.ellipse(image, CENTER, (35, 25), 0, 0, 360, (25, 30, 35), -1)
    return noisy(image, 6, 0)


def dark_skin() -> np.ndarray:
    image = np.full((*SIZE, 3), (55, 75, 110), np.uint8)
    cv2.ellipse(image, CENTER, (100, 70), 0, 0, 360, (45, 55, 75), -1)
    return noisy(image, 6, 1)


def red_lesion_hair_glare() -> np.ndarray:
    image = np.full((*SIZE, 3), (150, 170, 215), np.uint8)
    cv2.ellipse(image, CENTER, (110, 75), 20, 0, 360, (70, 70, 190), -1)
    for x in range(70, 260, 25):
        cv2.line(image, (x, 30), (x + 30, 210), (20, 20, 20), 1)
    for center in [(140, 110), (175, 130)]:
        cv2.circle(image, center, 6, (255, 255, 255), -1)
    return noisy(image, 5, 2)


def uniform() -> np.ndarray:
    return noisy(np.full((*SIZE, 3), (150, 170, 215), np.uint8), 2, 3)


CASES = {"wound": wound, "dark_skin": dark_skin, "red_lesion": red_lesion_hair_glare, "uniform": uniform}


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    expected = {}
    for name, make in CASES.items():
        bgr = make()
        output = analyze_image(bgr)
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        (OUT / f"{name}.rgb.gz").write_bytes(gzip.compress(rgb.tobytes(), mtime=0))
        (OUT / f"{name}.labels.gz").write_bytes(gzip.compress(output.tissue_labels.tobytes(), mtime=0))
        expected[name] = {
            "width": int(bgr.shape[1]),
            "height": int(bgr.shape[0]),
            "labels_shape": list(output.tissue_labels.shape),
            "necrotic_area_ratio": output.necrotic_area_ratio,
            "result": {k: v for k, v in output.result.items() if k != "config"},
        }
        print(f"{name}: necrótico {output.necrotic_area_ratio} · {output.result['tissue_composition']}")
    (OUT / "expected.json").write_text(json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    main()

import { useState } from "react";
import type { LegendItem } from "../services/analysisResult";
import { useImageSource } from "../hooks/useImageSource";

interface AnalysisImageProps {
  imageId: string;
  analysisId: string;
  filename: string;
  hasProcessedImage: boolean;
  /** Leyenda que envía el backend con el resultado; si falta se usa la de la heurística. */
  legend?: LegendItem[];
}

type View = "processed" | "original";

const DEFAULT_LEGEND: LegendItem[] = [
  { label: "Región analizada", color: "#50dc50", kind: "outline" },
  { label: "Negro / marrón oscuro", color: "#ff00ff", kind: "fill" },
  { label: "Amarillo", color: "#ffd700", kind: "fill" },
];

/** Imagen del análisis con selector entre la original y la procesada (con leyenda). */
export function AnalysisImage({ imageId, analysisId, filename, hasProcessedImage, legend }: AnalysisImageProps) {
  const [view, setView] = useState<View>(hasProcessedImage ? "processed" : "original");
  const showProcessed = hasProcessedImage && view === "processed";
  const items = legend && legend.length > 0 ? legend : DEFAULT_LEGEND;
  const originalSrc = useImageSource("original", imageId);
  const processedSrc = useImageSource("processed", analysisId);
  const src = showProcessed ? processedSrc : originalSrc;

  return (
    <figure className="card figure">
      {hasProcessedImage && (
        <div className="segmented" role="group" aria-label="Vista de la imagen">
          <button type="button" aria-pressed={showProcessed} onClick={() => setView("processed")}>
            Procesada
          </button>
          <button type="button" aria-pressed={!showProcessed} onClick={() => setView("original")}>
            Original
          </button>
        </div>
      )}
      {src ? (
        <img src={src} alt={showProcessed ? `Imagen procesada: ${filename}` : `Imagen analizada: ${filename}`} />
      ) : (
        <div className="figure__placeholder" role="status">
          Cargando imagen…
        </div>
      )}
      <figcaption>
        <span className="figure__name" title={filename}>
          {filename}
        </span>
        {showProcessed && (
          <ul className="legend" aria-label="Leyenda de la imagen procesada">
            {items.map((item) => (
              <li key={item.label}>
                <span
                  className={`swatch${item.kind === "outline" ? " swatch--outline" : ""}`}
                  style={item.kind === "outline" ? { borderColor: item.color } : { background: item.color }}
                  aria-hidden="true"
                />{" "}
                {item.label}
              </li>
            ))}
          </ul>
        )}
      </figcaption>
    </figure>
  );
}

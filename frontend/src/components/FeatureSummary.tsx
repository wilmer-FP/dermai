import type { AnalysisResultData as HeuristicResult } from "../services/analysisResult";
import { formatNumber, formatRatio } from "../services/format";

interface FeatureGroup {
  title: string;
  rows: [label: string, value: string][];
}

function groups(result: HeuristicResult): FeatureGroup[] {
  const { shape, texture, edges, color, quality } = result;
  const lab = color?.lesion_lab_mean;
  const list: FeatureGroup[] = [];

  if (shape) {
    list.push({
      title: "Forma",
      rows: [
        ["Área de la región sobre la imagen", formatRatio(shape.area_ratio)],
        ["Circularidad (1 = círculo)", formatNumber(shape.circularity)],
        ["Solidez (1 = sin entrantes)", formatNumber(shape.solidity)],
        ["Excentricidad (0 = redonda)", formatNumber(shape.eccentricity)],
      ],
    });
  }
  list.push(
    {
      title: "Color",
      rows: [
        ["Diferencia media con la piel (ΔE)", formatNumber(color?.delta_e_to_skin_mean, 1)],
        ["L* a* b* medio de la región", lab ? lab.map((v) => formatNumber(v, 1)).join(" · ") : "—"],
      ],
    },
    {
      title: "Textura (GLCM)",
      rows: [
        ["Contraste", formatNumber(texture?.contrast)],
        ["Homogeneidad", formatNumber(texture?.homogeneity)],
        ["Entropía", formatNumber(texture?.entropy)],
      ],
    },
    {
      title: "Bordes",
      rows: [
        ["Densidad de bordes", formatRatio(edges?.edge_density)],
        ["Nitidez del contorno (gradiente)", formatNumber(edges?.border_gradient_mean, 1)],
      ],
    },
    {
      title: "Calidad de la imagen",
      rows: [
        ["Nitidez (varianza del laplaciano)", formatNumber(quality?.sharpness, 0)],
        ["Reflejos excluidos", formatRatio(quality?.glare_ratio)],
      ],
    },
  );
  return list;
}

/** Características visuales extraídas, agrupadas y en lenguaje llano. */
export function FeatureSummary({ result }: { result: HeuristicResult }) {
  return (
    <div className="features">
      {groups(result).map((group) => (
        <section key={group.title}>
          <h3>{group.title}</h3>
          <dl className="data-list data-list--compact">
            {group.rows.map(([label, value]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{value}</dd>
              </div>
            ))}
          </dl>
        </section>
      ))}
    </div>
  );
}

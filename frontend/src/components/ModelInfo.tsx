import { Link } from "react-router";
import { formatNumber } from "../services/format";
import type { ModelVersionRead } from "../types/api";

function metric(metrics: Record<string, unknown> | null, key: string): number | null {
  const value = metrics?.[key];
  return typeof value === "number" ? value : null;
}

/** Descripción y métricas de validación de la versión de modelo usada en un análisis. */
export function ModelInfo({ model }: { model: ModelVersionRead }) {
  const { metrics } = model;
  const trainingImages = metric(metrics, "training_images");
  const evaluation = typeof metrics?.evaluation === "string" ? metrics.evaluation : "validación cruzada";
  const foldMean = metric(metrics, "cv_fold_dice_mean");
  const foldStd = metric(metrics, "cv_fold_dice_std");
  const rows: [string, string, string][] = [
    [
      "Dice sin fondo, media por partición",
      foldMean === null ? "—" : `${formatNumber(foldMean)}${foldStd === null ? "" : ` ± ${formatNumber(foldStd)}`}`,
      "—",
    ],
    [
      "Dice sin fondo, agregado",
      formatNumber(metric(metrics, "cv_mean_dice_foreground")),
      formatNumber(metric(metrics, "heuristic_mean_dice_foreground")),
    ],
    ["Dice de necrosis", formatNumber(metric(metrics, "cv_necrotic_dice")), formatNumber(metric(metrics, "heuristic_necrotic_dice"))],
    [
      "Error medio en la proporción necrótica",
      formatNumber(metric(metrics, "cv_necrotic_ratio_mae"), 3),
      formatNumber(metric(metrics, "heuristic_necrotic_ratio_mae"), 3),
    ],
  ];

  return (
    <section className="card" aria-labelledby="model-title">
      <h2 id="model-title">Sobre el modelo</h2>
      <p>
        <code>
          {model.name} v{model.version}
        </code>
        {model.architecture && <span className="muted small"> · {model.architecture}</span>}
      </p>
      {model.description && <p className="muted small model-description">{model.description}</p>}
      {typeof metrics?.dataset === "string" && (
        <p className="small model-description">
          Datos de entrenamiento: {metrics.dataset}. <Link to="/about#creditos">Créditos y licencias</Link>
        </p>
      )}
      {trainingImages !== null && trainingImages < 100 && (
        <div className="alert alert--warning">
          <p className="alert__title">Prueba de concepto</p>
          <p>
            Entrenado con solo {trainingImages} imágenes. Sus métricas tienen mucha variabilidad y no son
            representativas: no uses sus resultados para sacar conclusiones.
          </p>
        </div>
      )}
      <table className="metrics-table">
        <caption className="muted small">Métricas de {evaluation} (1 = perfecto, salvo el error: 0 = perfecto)</caption>
        <thead>
          <tr>
            <th scope="col">Métrica</th>
            <th scope="col">Modelo</th>
            <th scope="col">Heurística</th>
          </tr>
        </thead>
        <tbody>
          {rows.map(([label, modelValue, heuristicValue]) => (
            <tr key={label}>
              <th scope="row">{label}</th>
              <td>{modelValue}</td>
              <td>{heuristicValue}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

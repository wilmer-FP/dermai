import {
  MODEL_TISSUE_LABELS,
  TISSUE_CLASSES,
  type TissueComposition as Composition,
} from "../services/analysisResult";
import { formatRatio } from "../services/format";

interface TissueCompositionProps {
  composition: Composition;
  /** Si viene de un modelo, las clases se nombran como tejidos en lugar de colores. */
  fromModel?: boolean;
}

/** Barra apilada y leyenda con la proporción de cada grupo dentro de la región analizada. */
export function TissueComposition({ composition, fromModel = false }: TissueCompositionProps) {
  const classes = TISSUE_CLASSES.map((tissue) =>
    fromModel ? { ...tissue, ...MODEL_TISSUE_LABELS[tissue.key] } : tissue,
  );
  return (
    <div className="tissue">
      <div className="tissue__bar" role="img" aria-label="Composición de la región analizada">
        {classes.map(({ key, color }) =>
          composition[key] > 0 ? (
            <span key={key} style={{ width: `${composition[key] * 100}%`, background: color }} />
          ) : null,
        )}
      </div>
      <ul className="tissue__legend" aria-label="Composición por color">
        {classes.map(({ key, label, hint, color }) => (
          <li key={key}>
            <span className="swatch" style={{ background: color }} aria-hidden="true" />
            <span className="tissue__label">
              {label}
              {hint && <span className="muted small"> · {hint}</span>}
            </span>
            <strong>{formatRatio(composition[key])}</strong>
          </li>
        ))}
      </ul>
    </div>
  );
}

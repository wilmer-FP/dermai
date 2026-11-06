/** Mismo texto que DISCLAIMER en backend/app/core/constants.py. */
export const DISCLAIMER_TEXT =
  "Prototipo experimental con fines educativos. No es una herramienta de diagnóstico médico.";

interface DisclaimerProps {
  /** Texto alternativo, por ejemplo el `disclaimer` que devuelve la API. */
  text?: string;
  variant?: "banner" | "inline";
}

export function Disclaimer({ text = DISCLAIMER_TEXT, variant = "banner" }: DisclaimerProps) {
  return (
    <aside className={`disclaimer disclaimer--${variant}`} role="note" aria-label="Aviso de uso no diagnóstico">
      <span className="disclaimer__icon" aria-hidden="true">
        !
      </span>
      <p>
        <strong>{text}</strong>{" "}
        {variant === "banner" && "Los resultados no deben usarse para tomar decisiones clínicas."}
      </p>
    </aside>
  );
}

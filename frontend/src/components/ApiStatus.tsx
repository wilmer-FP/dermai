import type { ApiHealthState, ApiHealthStatus } from "../hooks/useApiHealth";

const LABELS: Record<Exclude<ApiHealthStatus, "online">, string> = {
  checking: "Comprobando API…",
  waking: "API no disponible · reintentando…",
  offline: "API no disponible",
};

/** Indicador discreto de conexión con el backend (GET /health). */
export function ApiStatus({ state }: { state: ApiHealthState }) {
  const { status } = state;
  const online =
    state.health?.analysis_mode === "browser"
      ? "Análisis local · ONNX / OpenCV.js"
      : `API conectada · v${state.health?.version ?? "?"}`;
  const label = status === "online" ? online : LABELS[status];
  const tone = status === "online" ? "online" : status === "checking" ? "checking" : "offline";

  return (
    <span className={`api-status api-status--${tone}`} role="status">
      <span className="api-status__dot" aria-hidden="true" />
      {label}
    </span>
  );
}

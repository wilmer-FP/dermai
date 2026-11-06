import { Link, useSearchParams } from "react-router";
import { EmptyState, ErrorMessage, Loading } from "../components/Feedback";
import { Pagination } from "../components/Pagination";
import { StatusBadge } from "../components/StatusBadge";
import { useAsync } from "../hooks/useAsync";
import { useImageSource } from "../hooks/useImageSource";
import { listAnalyses } from "../services/api";
import { STATUS_LABELS, formatDate, formatRatio, shortId } from "../services/format";
import { ANALYSIS_STATUSES, type AnalysisStatus } from "../types/api";

export const HISTORY_PAGE_SIZE = 10;

function Thumbnail({ imageId }: { imageId: string }) {
  const src = useImageSource("original", imageId);
  return src ? (
    <img src={src} alt="" className="history-item__thumb" loading="lazy" />
  ) : (
    <span className="history-item__thumb" aria-hidden="true" />
  );
}

function parseStatus(value: string | null): AnalysisStatus | undefined {
  return ANALYSIS_STATUSES.find((status) => status === value);
}

export function HistoryPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const status = parseStatus(searchParams.get("status"));
  const offset = Math.max(0, Math.floor(Number(searchParams.get("offset"))) || 0);

  const { data, error, loading, reload } = useAsync(
    () => listAnalyses({ limit: HISTORY_PAGE_SIZE, offset, status }),
    [status, offset],
  );

  function updateParams(next: { status?: AnalysisStatus; offset?: number }) {
    const params: Record<string, string> = {};
    if (next.status) params.status = next.status;
    if (next.offset) params.offset = String(next.offset);
    setSearchParams(params);
  }

  return (
    <>
      <title>Historial · DermAI</title>
      <div className="page-header page-header--row">
        <div>
          <h1>Historial de análisis</h1>
          <p className="muted">Los más recientes primero.</p>
        </div>
        <label className="select-field">
          <span>Estado</span>
          <select
            value={status ?? ""}
            onChange={(event) => updateParams({ status: parseStatus(event.target.value) })}
          >
            <option value="">Todos</option>
            {ANALYSIS_STATUSES.map((value) => (
              <option key={value} value={value}>
                {STATUS_LABELS[value]}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && !data && <Loading label="Cargando historial…" />}
      {error !== undefined && <ErrorMessage error={error} title="No se pudo cargar el historial" onRetry={reload} />}

      {data && data.items.length === 0 && (
        <EmptyState>
          {offset > 0 ? (
            <>
              <p>No hay análisis en esta página.</p>
              <button type="button" className="button button--secondary" onClick={() => updateParams({ status })}>
                Ir a la primera página
              </button>
            </>
          ) : status ? (
            <p>No hay análisis con estado «{STATUS_LABELS[status]}».</p>
          ) : (
            <>
              <p>Todavía no hay análisis.</p>
              <Link to="/" className="button button--primary">
                Analizar una imagen
              </Link>
            </>
          )}
        </EmptyState>
      )}

      {data && data.items.length > 0 && (
        <>
          <ul className={`history-list${loading ? " is-refreshing" : ""}`} aria-label="Análisis" aria-busy={loading}>
            {data.items.map((analysis) => (
              <li key={analysis.id}>
                <Link to={`/analyses/${analysis.id}`} className="history-item">
                  <Thumbnail imageId={analysis.image_id} />
                  <div className="history-item__body">
                    <p className="history-item__title">
                      Análisis <code>{shortId(analysis.id)}</code>
                    </p>
                    <p className="muted small">{formatDate(analysis.created_at)}</p>
                  </div>
                  <div className="history-item__meta">
                    <StatusBadge status={analysis.status} />
                    <span className="muted small" title="Proporción de área con rasgos compatibles con tejido necrótico">
                      Área: {formatRatio(analysis.necrotic_area_ratio)}
                    </span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
          <Pagination
            total={data.total}
            limit={data.limit}
            offset={data.offset}
            onChange={(nextOffset) => updateParams({ status, offset: nextOffset })}
          />
        </>
      )}
    </>
  );
}

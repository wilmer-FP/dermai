import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { AnalysisImage } from "../components/AnalysisImage";
import { Disclaimer } from "../components/Disclaimer";
import { FeatureSummary } from "../components/FeatureSummary";
import { EmptyState, ErrorMessage, Loading } from "../components/Feedback";
import { ModelInfo } from "../components/ModelInfo";
import { StatusBadge } from "../components/StatusBadge";
import { TissueComposition } from "../components/TissueComposition";
import { useAsync } from "../hooks/useAsync";
import { isModelResult, readAnalysisResult } from "../services/analysisResult";
import { ApiError, deleteImage, getAnalysis, getImage, listModelVersions, requestAnalysis } from "../services/api";
import { formatBytes, formatDate, formatDimensions, formatRatio, shortId } from "../services/format";
import type { ModelVersionRead } from "../types/api";

async function loadAnalysisWithImage(analysisId: string) {
  const analysis = await getAnalysis(analysisId);
  const image = await getImage(analysis.image_id);
  return { analysis, image };
}

async function findModelVersion(id: string | null | undefined): Promise<ModelVersionRead | null> {
  if (!id) return null;
  const models = await listModelVersions();
  return models.find((model) => model.id === id) ?? null;
}

export function AnalysisPage() {
  const { analysisId = "" } = useParams();
  const navigate = useNavigate();
  const { data, error, loading, reload } = useAsync(() => loadAnalysisWithImage(analysisId), [analysisId]);
  const modelVersionId = data?.analysis.model_version_id;
  const modelState = useAsync(() => findModelVersion(modelVersionId), [modelVersionId]);
  const [action, setAction] = useState<"idle" | "deleting" | "reanalyzing">("idle");
  const [actionError, setActionError] = useState<{ title: string; error: unknown } | null>(null);

  if (loading && !data) return <Loading label="Cargando análisis…" />;

  if (error !== undefined && !data) {
    if (error instanceof ApiError && (error.status === 404 || error.status === 422)) {
      return (
        <EmptyState>
          <title>Análisis no encontrado · DermAI</title>
          <h1>Análisis no encontrado</h1>
          <p>Puede que se haya eliminado junto con su imagen.</p>
          <Link to="/history" className="button button--secondary">
            Ir al historial
          </Link>
        </EmptyState>
      );
    }
    return <ErrorMessage error={error} title="No se pudo cargar el análisis" onRetry={reload} />;
  }

  if (!data) return null;
  const { analysis, image } = data;
  const result = readAnalysisResult(analysis.result);
  const fromModel = result ? isModelResult(result) : analysis.model_version_id !== null;
  const busy = action !== "idle";

  async function handleDelete() {
    const confirmed = window.confirm(
      "¿Eliminar la imagen y todos sus análisis? Esta acción no se puede deshacer.",
    );
    if (!confirmed) return;
    setAction("deleting");
    setActionError(null);
    try {
      await deleteImage(image.id);
      navigate("/history", { replace: true });
    } catch (err) {
      setActionError({ title: "No se pudo eliminar la imagen", error: err });
      setAction("idle");
    }
  }

  async function handleReanalyze() {
    setAction("reanalyzing");
    setActionError(null);
    try {
      // Se repite con el mismo método: la misma versión de modelo o la heurística.
      const next = await requestAnalysis(image.id, analysis.model_version_id);
      setAction("idle");
      navigate(`/analyses/${next.id}`);
    } catch (err) {
      setActionError({ title: "No se pudo solicitar un nuevo análisis", error: err });
      setAction("idle");
    }
  }

  return (
    <>
      <title>{`Análisis ${shortId(analysis.id)} · DermAI`}</title>
      <div className="page-header page-header--row">
        <div>
          <h1>Resultado del análisis</h1>
          <p className="muted">
            Referencia <code>{shortId(analysis.id)}</code> · solicitado el {formatDate(analysis.created_at)}
          </p>
        </div>
        <StatusBadge status={analysis.status} />
      </div>

      <div className="analysis-layout">
        <AnalysisImage
          key={analysis.id}
          imageId={image.id}
          analysisId={analysis.id}
          filename={image.original_filename}
          hasProcessedImage={analysis.has_processed_image}
          legend={result?.legend}
        />

        <div className="stack">
          <section className="card" aria-labelledby="result-title">
            <h2 id="result-title">Resultado experimental</h2>

            {analysis.status === "pending" && (
              <div className="alert alert--info">
                <p className="alert__title">Análisis sin procesar</p>
                <p>
                  Este análisis se registró antes de que existiera el procesamiento de imágenes. Usa «Analizar de
                  nuevo» para procesarla.
                </p>
              </div>
            )}

            {analysis.status === "processing" && (
              <div className="alert alert--info">
                <p className="alert__title">Análisis en proceso</p>
                <p>Pulsa «Actualizar» en unos segundos para ver el resultado.</p>
              </div>
            )}

            {analysis.status === "failed" && (
              <div className="alert alert--error">
                <p className="alert__title">El análisis falló</p>
                <p>{analysis.error_message ?? "Sin detalles del error."}</p>
              </div>
            )}

            {result?.warnings && result.warnings.length > 0 && (
              <div className="alert alert--warning">
                <p className="alert__title">Avisos sobre el resultado</p>
                <ul>
                  {result.warnings.map((warning) => (
                    <li key={warning}>{warning}</li>
                  ))}
                </ul>
              </div>
            )}

            <dl className="data-list">
              <div>
                <dt>
                  {fromModel
                    ? "Proporción de la herida que el modelo clasifica como necrosis"
                    : "Proporción de la lesión con color compatible con tejido necrótico"}
                </dt>
                <dd className="data-list__highlight">{formatRatio(analysis.necrotic_area_ratio)}</dd>
              </div>
              <div>
                <dt>Confianza del modelo</dt>
                <dd>
                  {analysis.confidence !== null
                    ? `${formatRatio(analysis.confidence)} (no calibrada)`
                    : result
                      ? "No aplica (método heurístico)"
                      : "—"}
                </dd>
              </div>
              <div>
                <dt>Método</dt>
                <dd>
                  {result ? (
                    <code>
                      {result.method.name} v{result.method.version}
                    </code>
                  ) : analysis.model_version_id ? (
                    <code>modelo {shortId(analysis.model_version_id)}</code>
                  ) : (
                    "—"
                  )}
                </dd>
              </div>
              <div>
                <dt>Fecha de finalización</dt>
                <dd>{formatDate(analysis.completed_at)}</dd>
              </div>
            </dl>

            {result?.confidence_definition && (
              <p className="muted small method-note">
                <strong>Confianza:</strong> {result.confidence_definition}
              </p>
            )}

            {result && (
              <>
                <h3 className="section-title">
                  {fromModel ? "Composición de la herida según el modelo" : "Composición por color de la región"}
                </h3>
                <TissueComposition composition={result.tissue_composition} fromModel={fromModel} />
                <p className="muted small method-note">
                  {result.method.description ||
                    "Clasificación heurística por color. No identifica tejidos ni sustituye la valoración clínica."}
                </p>
              </>
            )}

            <Disclaimer text={analysis.disclaimer} variant="inline" />
          </section>

          {modelState.data && <ModelInfo model={modelState.data} />}

          {result && (
            <section className="card" aria-labelledby="features-title">
              <h2 id="features-title">Características extraídas</h2>
              <FeatureSummary result={result} />
            </section>
          )}

          {analysis.result && (
            <details className="card raw-result">
              <summary>Datos completos del resultado (JSON)</summary>
              <pre>{JSON.stringify(analysis.result, null, 2)}</pre>
            </details>
          )}

          <section className="card" aria-labelledby="image-title">
            <h2 id="image-title">Datos de la imagen</h2>
            <dl className="data-list">
              <div>
                <dt>Formato</dt>
                <dd>{image.content_type}</dd>
              </div>
              <div>
                <dt>Dimensiones</dt>
                <dd>{formatDimensions(image.width, image.height)}</dd>
              </div>
              <div>
                <dt>Tamaño</dt>
                <dd>{formatBytes(image.file_size_bytes)}</dd>
              </div>
              <div>
                <dt>Subida</dt>
                <dd>{formatDate(image.created_at)}</dd>
              </div>
              <div>
                <dt>SHA-256</dt>
                <dd>
                  <code className="hash" title={image.checksum_sha256}>
                    {image.checksum_sha256}
                  </code>
                </dd>
              </div>
            </dl>
          </section>

          {actionError && <ErrorMessage error={actionError.error} title={actionError.title} />}

          <div className="actions">
            <Link to="/history" className="button button--secondary">
              Volver al historial
            </Link>
            <button type="button" className="button button--secondary" onClick={reload} disabled={loading || busy}>
              {loading ? "Actualizando…" : "Actualizar"}
            </button>
            <button type="button" className="button button--secondary" onClick={handleReanalyze} disabled={busy}>
              {action === "reanalyzing" ? "Analizando…" : "Analizar de nuevo"}
            </button>
            <button type="button" className="button button--danger" onClick={handleDelete} disabled={busy}>
              {action === "deleting" ? "Eliminando…" : "Eliminar imagen"}
            </button>
          </div>
        </div>
      </div>
    </>
  );
}

import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { ErrorMessage } from "../components/Feedback";
import { ImageDropzone } from "../components/ImageDropzone";
import { useAsync } from "../hooks/useAsync";
import { useObjectUrl } from "../hooks/useObjectUrl";
import { listModelVersions, requestAnalysis, uploadImage } from "../services/api";
import { formatBytes, formatNumber } from "../services/format";
import { validateImageFile } from "../services/imageValidation";
import type { ImageRead, ModelVersionRead } from "../types/api";

const HEURISTIC = "heuristic";

/** Métodos disponibles: la heurística siempre; los modelos activos si la API los ofrece. */
function MethodPicker({
  models,
  value,
  onChange,
  disabled,
}: {
  models: ModelVersionRead[];
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}) {
  return (
    <fieldset className="method-picker" disabled={disabled}>
      <legend>Método de análisis</legend>
      <label className="radio">
        <input type="radio" name="method" value={HEURISTIC} checked={value === HEURISTIC} onChange={() => onChange(HEURISTIC)} />
        <span>
          <strong>Heurística de OpenCV</strong>
          <span className="muted small">Clasificación por color, sin modelo entrenado.</span>
        </span>
      </label>
      {models.map((model) => {
        // Media por partición (más honesta que el valor agregado); si falta, el agregado.
        const dice = model.metrics?.cv_fold_dice_mean ?? model.metrics?.cv_mean_dice_foreground;
        const images = model.metrics?.training_images;
        return (
          <label className="radio" key={model.id}>
            <input type="radio" name="method" value={model.id} checked={value === model.id} onChange={() => onChange(model.id)} />
            <span>
              <strong>
                Modelo experimental {model.name} v{model.version}
              </strong>
              <span className="muted small">
                Segmentación de tejidos con PyTorch
                {typeof images === "number" && ` · entrenado con ${images} imágenes`}
                {typeof dice === "number" && ` · Dice medio ${formatNumber(dice)}`}
              </span>
            </span>
          </label>
        );
      })}
    </fieldset>
  );
}

type Phase = "idle" | "uploading" | "requesting";

const PHASE_LABELS: Record<Phase, string> = {
  idle: "Subir y solicitar análisis",
  uploading: "Subiendo imagen…",
  requesting: "Analizando imagen…",
};

export function UploadPage() {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [consent, setConsent] = useState(false);
  const [phase, setPhase] = useState<Phase>("idle");
  const [submitError, setSubmitError] = useState<unknown>(null);
  // Si la subida funcionó pero el análisis no, el reintento no vuelve a subir la imagen.
  const [uploadedImage, setUploadedImage] = useState<ImageRead | null>(null);
  const previewUrl = useObjectUrl(file);
  const busy = phase !== "idle";
  const [method, setMethod] = useState(HEURISTIC);
  // Si la lista de modelos falla, se ofrece solo la heurística.
  const activeModels = useAsync(() => listModelVersions(true), []).data ?? [];

  function handleSelect(selected: File) {
    const error = validateImageFile(selected);
    setValidationError(error);
    setFile(error ? null : selected);
    setUploadedImage(null);
    setSubmitError(null);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file || !consent || busy) return;
    setSubmitError(null);

    let image = uploadedImage;
    try {
      if (!image) {
        setPhase("uploading");
        image = await uploadImage(file);
        setUploadedImage(image);
      }
      setPhase("requesting");
      const analysis = await requestAnalysis(image.id, method === HEURISTIC ? null : method);
      navigate(`/analyses/${analysis.id}`);
    } catch (error) {
      setSubmitError(error);
      setPhase("idle");
    }
  }

  return (
    <>
      <title>Analizar una imagen · DermAI</title>
      <div className="page-header">
        <h1>Analizar una imagen</h1>
        <p className="lead">
          Sube una fotografía de una lesión cutánea para registrarla y solicitar un análisis experimental de sus
          características visuales.
        </p>
      </div>

      <div className="upload-layout">
        <form className="card upload-form" onSubmit={handleSubmit} noValidate>
          {file && previewUrl ? (
            <div className="preview">
              <img src={previewUrl} alt="Vista previa de la imagen seleccionada" className="preview__image" />
              <div className="preview__info">
                <p className="preview__name" title={file.name}>
                  {file.name}
                </p>
                <p className="muted">{formatBytes(file.size)}</p>
                <button
                  type="button"
                  className="button button--secondary button--small"
                  onClick={() => {
                    setFile(null);
                    setUploadedImage(null);
                    setSubmitError(null);
                  }}
                  disabled={busy}
                >
                  Cambiar imagen
                </button>
              </div>
            </div>
          ) : (
            <ImageDropzone onSelect={handleSelect} disabled={busy} />
          )}

          {validationError && (
            <p className="field-error" role="alert">
              {validationError}
            </p>
          )}

          {activeModels.length > 0 && (
            <MethodPicker models={activeModels} value={method} onChange={setMethod} disabled={busy} />
          )}

          <label className="checkbox">
            <input
              type="checkbox"
              checked={consent}
              onChange={(event) => setConsent(event.target.checked)}
              disabled={busy}
            />
            <span>
              Confirmo que la imagen no contiene datos que identifiquen a una persona (rostro, nombre, tatuajes, documentos)
              y que tengo derecho a usarla con fines educativos.
            </span>
          </label>
          <p className="muted small">
            Al subirla se eliminan sus metadatos (EXIF, ubicación GPS, cámara y fecha).
          </p>

          {submitError !== null && (
            <ErrorMessage
              error={submitError}
              title={
                uploadedImage
                  ? "La imagen se subió, pero no se pudo registrar el análisis"
                  : "No se pudo subir la imagen"
              }
            />
          )}

          <button type="submit" className="button button--primary" disabled={!file || !consent || busy}>
            {busy && <span className="spinner spinner--light" aria-hidden="true" />}
            {PHASE_LABELS[phase]}
          </button>
        </form>

        <aside className="card how-it-works" aria-labelledby="how-it-works-title">
          <h2 id="how-it-works-title">Cómo funciona</h2>
          <ol className="steps">
            <li>
              <strong>Validación.</strong> El servidor comprueba que el archivo sea realmente una imagen JPG o PNG.
            </li>
            <li>
              <strong>Registro.</strong> La imagen se guarda sin datos personales y se crea una solicitud de análisis.
            </li>
            <li>
              <strong>Procesamiento.</strong> OpenCV normaliza el tamaño y el color, separa la lesión de la piel
              circundante y extrae características de color, textura, bordes y forma.
            </li>
            <li>
              <strong>Resultado experimental.</strong> La heurística estima qué parte de la lesión tiene color
              compatible con tejido necrótico. Si hay un modelo experimental activo, también puedes usarlo para
              segmentar los tejidos de la herida.
            </li>
          </ol>
          <p className="muted small">
            Los resultados describen características visuales de la imagen. No son un diagnóstico.
          </p>
        </aside>
      </div>
    </>
  );
}

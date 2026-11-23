import { useId, useState, type ChangeEvent, type DragEvent } from "react";
import { ACCEPT_ATTRIBUTE, MAX_UPLOAD_SIZE_MB } from "../services/imageValidation";

interface ImageDropzoneProps {
  onSelect: (file: File) => void;
  disabled?: boolean;
}

/** Zona para elegir o arrastrar una imagen. Es un `<label>`, así que el teclado y los lectores de pantalla llegan al `<input>`. */
export function ImageDropzone({ onSelect, disabled = false }: ImageDropzoneProps) {
  const inputId = useId();
  const [dragging, setDragging] = useState(false);

  function handleChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (file) onSelect(file);
    event.target.value = ""; // permite volver a elegir el mismo archivo
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    if (disabled) return;
    const file = event.dataTransfer.files[0];
    if (file) onSelect(file);
  }

  return (
    <label
      htmlFor={inputId}
      className={`dropzone${dragging ? " dropzone--active" : ""}${disabled ? " dropzone--disabled" : ""}`}
      onDragOver={(event) => {
        event.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <input
        id={inputId}
        type="file"
        accept={ACCEPT_ATTRIBUTE}
        className="visually-hidden"
        onChange={handleChange}
        disabled={disabled}
        aria-describedby={`${inputId}-hint`}
      />
      <span className="dropzone__icon" aria-hidden="true">
        ⇪
      </span>
      <span className="dropzone__title">Selecciona una imagen o arrástrala aquí</span>
      <span className="dropzone__hint" id={`${inputId}-hint`}>
        JPG o PNG, hasta {MAX_UPLOAD_SIZE_MB} MB
      </span>
    </label>
  );
}

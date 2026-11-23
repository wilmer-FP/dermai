import type { ReactNode } from "react";
import { ApiError } from "../services/api";

/** Mensaje legible para cualquier error capturado. */
export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error && error.message) return error.message;
  return "Ha ocurrido un error inesperado.";
}

interface ErrorMessageProps {
  error: unknown;
  title?: string;
  onRetry?: () => void;
}

export function ErrorMessage({ error, title = "No se pudo completar la operación", onRetry }: ErrorMessageProps) {
  return (
    <div className="alert alert--error" role="alert">
      <p className="alert__title">{title}</p>
      <p>{errorMessage(error)}</p>
      {onRetry && (
        <button type="button" className="button button--secondary button--small" onClick={onRetry}>
          Reintentar
        </button>
      )}
    </div>
  );
}

export function Loading({ label = "Cargando…" }: { label?: string }) {
  return (
    <p className="loading" role="status">
      <span className="spinner" aria-hidden="true" />
      {label}
    </p>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <div className="empty-state">{children}</div>;
}

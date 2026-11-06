/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Base de la API. Por defecto "/api/v1" (el servidor de Vite la reenvía al backend). */
  readonly VITE_API_BASE_URL?: string;
  /** Tamaño máximo de subida en MB; debe coincidir con MAX_UPLOAD_SIZE_MB del backend. */
  readonly VITE_MAX_UPLOAD_SIZE_MB?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

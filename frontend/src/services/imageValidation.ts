// Validación básica en el cliente, para dar respuesta inmediata.
// El backend sigue siendo la autoridad: comprueba el contenido real con Pillow.

export const ALLOWED_EXTENSIONS = ["jpg", "jpeg", "png"] as const;
export const ALLOWED_MIME_TYPES = ["image/jpeg", "image/png"] as const;
/** Valor del atributo `accept` del selector de archivos. */
export const ACCEPT_ATTRIBUTE = [...ALLOWED_MIME_TYPES, ...ALLOWED_EXTENSIONS.map((ext) => `.${ext}`)].join(",");

const configuredMaxMb = Number(import.meta.env.VITE_MAX_UPLOAD_SIZE_MB);
/** Debe coincidir con MAX_UPLOAD_SIZE_MB del backend (10 MB por defecto). */
export const MAX_UPLOAD_SIZE_MB = Number.isFinite(configuredMaxMb) && configuredMaxMb > 0 ? configuredMaxMb : 10;

function extensionOf(filename: string): string {
  const dot = filename.lastIndexOf(".");
  return dot === -1 ? "" : filename.slice(dot + 1).toLowerCase();
}

/** Devuelve un mensaje de error o `null` si el archivo puede enviarse. */
export function validateImageFile(file: File, maxSizeMb: number = MAX_UPLOAD_SIZE_MB): string | null {
  if (file.size === 0) return "El archivo está vacío.";

  const extension = extensionOf(file.name);
  const typeAllowed = !file.type || (ALLOWED_MIME_TYPES as readonly string[]).includes(file.type);
  if (!(ALLOWED_EXTENSIONS as readonly string[]).includes(extension) || !typeAllowed) {
    return "Formato no permitido. Usa una imagen JPG o PNG.";
  }

  if (file.size > maxSizeMb * 1024 * 1024) {
    const sizeMb = (file.size / (1024 * 1024)).toFixed(1);
    return `El archivo pesa ${sizeMb} MB; el máximo es ${maxSizeMb} MB.`;
  }
  return null;
}

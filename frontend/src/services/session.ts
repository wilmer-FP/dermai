// Identificador anónimo de sesión para el modo demo: el backend solo devuelve a cada
// navegador sus propias imágenes. No contiene datos personales; se guarda en localStorage.

export const SESSION_HEADER = "X-DermAI-Session";
const STORAGE_KEY = "dermai.session";
const VALID_SESSION = /^[A-Za-z0-9-]{16,64}$/;

let current: string | null = null;

function randomId(): string {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") return crypto.randomUUID();
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

/** Devuelve el identificador de este navegador, creándolo la primera vez. */
export function getSessionId(): string {
  if (current) return current;
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && VALID_SESSION.test(stored)) {
      current = stored;
      return current;
    }
  } catch {
    // Almacenamiento bloqueado (p. ej. navegación privada): la sesión dura lo que la pestaña.
  }
  current = randomId();
  try {
    localStorage.setItem(STORAGE_KEY, current);
  } catch {
    // Igual que arriba: se usa solo en memoria.
  }
  return current;
}

/** Solo para pruebas: olvida la sesión en memoria. */
export function resetSessionCache(): void {
  current = null;
}

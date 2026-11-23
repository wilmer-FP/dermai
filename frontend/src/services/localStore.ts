// Almacenamiento local del modo navegador (IndexedDB): las imágenes y los análisis se guardan solo
// en este navegador y nunca se envían a un servidor.

import type { AnalysisRead, ImageRead } from "../types/api";

const DB_NAME = "dermai";
const DB_VERSION = 1;
const IMAGES = "images";
const ANALYSES = "analyses";

export interface StoredImage extends ImageRead {
  blob: Blob;
}

export interface StoredAnalysis extends AnalysisRead {
  processed: Blob | null;
}

let opening: Promise<IDBDatabase> | null = null;

function request<T>(req: IDBRequest<T>): Promise<T> {
  return new Promise((resolve, reject) => {
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

function done(tx: IDBTransaction): Promise<void> {
  return new Promise((resolve, reject) => {
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
    tx.onabort = () => reject(tx.error ?? new Error("Transacción cancelada"));
  });
}

export function openDatabase(): Promise<IDBDatabase> {
  opening ??= new Promise<IDBDatabase>((resolve, reject) => {
    if (typeof indexedDB === "undefined") {
      reject(new Error("Este navegador no permite guardar datos locales (IndexedDB)."));
      return;
    }
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(IMAGES)) {
        db.createObjectStore(IMAGES, { keyPath: "id" }).createIndex("created_at", "created_at");
      }
      if (!db.objectStoreNames.contains(ANALYSES)) {
        const store = db.createObjectStore(ANALYSES, { keyPath: "id" });
        store.createIndex("created_at", "created_at");
        store.createIndex("image_id", "image_id");
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
  opening.catch(() => {
    opening = null;
  });
  return opening;
}

/** Solo para pruebas: cierra y olvida la conexión. */
export async function resetDatabaseConnection(): Promise<void> {
  if (opening) (await opening.catch(() => null))?.close();
  opening = null;
}

export async function putImage(image: StoredImage): Promise<void> {
  const db = await openDatabase();
  const tx = db.transaction(IMAGES, "readwrite");
  tx.objectStore(IMAGES).put(image);
  await done(tx);
}

export async function putAnalysis(analysis: StoredAnalysis): Promise<void> {
  const db = await openDatabase();
  const tx = db.transaction(ANALYSES, "readwrite");
  tx.objectStore(ANALYSES).put(analysis);
  await done(tx);
}

export async function getStoredImage(id: string): Promise<StoredImage | undefined> {
  const db = await openDatabase();
  return request(db.transaction(IMAGES).objectStore(IMAGES).get(id));
}

export async function getStoredAnalysis(id: string): Promise<StoredAnalysis | undefined> {
  const db = await openDatabase();
  return request(db.transaction(ANALYSES).objectStore(ANALYSES).get(id));
}

/** Todos los registros, del más reciente al más antiguo. */
export async function allImages(): Promise<StoredImage[]> {
  const db = await openDatabase();
  const items: StoredImage[] = await request(db.transaction(IMAGES).objectStore(IMAGES).getAll());
  return items.sort(byNewest);
}

export async function allAnalyses(): Promise<StoredAnalysis[]> {
  const db = await openDatabase();
  const items: StoredAnalysis[] = await request(db.transaction(ANALYSES).objectStore(ANALYSES).getAll());
  return items.sort(byNewest);
}

/** Borra la imagen y todos sus análisis en una sola transacción. */
export async function deleteImageCascade(imageId: string): Promise<void> {
  const db = await openDatabase();
  const tx = db.transaction([IMAGES, ANALYSES], "readwrite");
  tx.objectStore(IMAGES).delete(imageId);
  const analyses = tx.objectStore(ANALYSES);
  const keys = await request(analyses.index("image_id").getAllKeys(imageId));
  for (const key of keys) analyses.delete(key);
  await done(tx);
}

function byNewest(a: { created_at: string; id: string }, b: { created_at: string; id: string }): number {
  return b.created_at.localeCompare(a.created_at) || a.id.localeCompare(b.id);
}

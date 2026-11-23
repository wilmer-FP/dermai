import { useEffect, useState } from "react";
import { imageFileUrl, isBrowserMode, loadImageBlob, processedImageUrl } from "../services/api";

export type ImageKind = "original" | "processed";

function apiUrl(kind: ImageKind, id: string): string {
  return kind === "original" ? imageFileUrl(id) : processedImageUrl(id);
}

/**
 * URL para `<img src>`. En modo API es la del backend; en modo navegador se crea una URL `blob:`
 * con el archivo guardado en IndexedDB (y se libera al desmontar).
 */
export function useImageSource(kind: ImageKind, id: string): string | undefined {
  const browser = isBrowserMode();
  const [url, setUrl] = useState<string | undefined>(() => (browser ? undefined : apiUrl(kind, id)));

  useEffect(() => {
    if (!browser) {
      setUrl(apiUrl(kind, id));
      return;
    }
    let active = true;
    let objectUrl: string | undefined;
    setUrl(undefined);
    loadImageBlob(kind, id).then(
      (blob) => {
        if (!active || !blob) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      },
      () => undefined,
    );
    return () => {
      active = false;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [browser, kind, id]);

  return url;
}

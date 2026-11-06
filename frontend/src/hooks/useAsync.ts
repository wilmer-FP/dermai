import { useCallback, useEffect, useState, type DependencyList } from "react";

export interface AsyncState<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  /** Vuelve a ejecutar la petición. */
  reload: () => void;
}

/**
 * Ejecuta una función asíncrona al montar y cada vez que cambian `deps`.
 * Ignora respuestas que llegan después de un cambio de dependencias o del desmontaje.
 */
export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList): AsyncState<T> {
  const [data, setData] = useState<T>();
  const [error, setError] = useState<unknown>();
  const [loading, setLoading] = useState(true);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError(undefined);
    fn().then(
      (value) => {
        if (!active) return;
        setData(value);
        setLoading(false);
      },
      (reason: unknown) => {
        if (!active) return;
        setData(undefined);
        setError(reason);
        setLoading(false);
      },
    );
    return () => {
      active = false;
    };
    // `fn` se recrea en cada render; las dependencias reales las indica quien llama.
  }, [...deps, attempt]);

  const reload = useCallback(() => setAttempt((n) => n + 1), []);
  return { data, error, loading, reload };
}

import { useEffect, useState } from "react";
import { getHealth } from "../services/api";
import type { HealthResponse } from "../types/api";

export type ApiHealthStatus = "checking" | "online" | "waking" | "offline";

export interface ApiHealthState {
  status: ApiHealthStatus;
  health?: HealthResponse;
}

/**
 * Comprueba GET /health y, si falla, reintenta durante un tiempo.
 * En la demo gratuita el servidor duerme sin uso y tarda 1–2 minutos en despertar.
 */
export function useApiHealth(maxAttempts = 36, intervalMs = 5000): ApiHealthState {
  const [state, setState] = useState<ApiHealthState>({ status: "checking" });

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;

    async function attempt(number: number) {
      try {
        const health = await getHealth();
        if (active) setState({ status: "online", health });
      } catch {
        if (!active) return;
        if (number >= maxAttempts) {
          setState({ status: "offline" });
          return;
        }
        setState({ status: "waking" });
        timer = setTimeout(() => void attempt(number + 1), intervalMs);
      }
    }

    void attempt(1);
    return () => {
      active = false;
      if (timer) clearTimeout(timer);
    };
  }, [maxAttempts, intervalMs]);

  return state;
}

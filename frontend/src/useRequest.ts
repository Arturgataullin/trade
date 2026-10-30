import { useEffect, useReducer, useState } from "react";

// Load on opening, changed parameters, or an explicit refresh; no timer.
export function useRequest<T>(
  load: (signal: AbortSignal) => Promise<T>,
  refreshVersion = 0,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [revision, refresh] = useReducer((value: number) => value + 1, 0);

  useEffect(() => {
    const controller = new AbortController();
    async function request() {
      try {
        const value = await load(controller.signal);
        if (controller.signal.aborted) return;
        setData(value);
        setError("");
        setUpdatedAt(new Date());
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Не удалось обновить данные");
      }
    }
    void request();
    return () => {
      controller.abort();
    };
  }, [load, refreshVersion, revision]);

  return { data, error, updatedAt, refresh };
}

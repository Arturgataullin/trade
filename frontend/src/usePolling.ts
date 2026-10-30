import { useEffect, useReducer, useState } from "react";

const always = () => true;

// A new request starts only after the previous one has finished.
export function usePolling<T>(
  load: (signal: AbortSignal) => Promise<T>,
  poll = true,
  shouldContinue: (value: T) => boolean = always,
) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);
  const [revision, refresh] = useReducer((value: number) => value + 1, 0);

  useEffect(() => {
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    async function tick() {
      let again = poll;
      try {
        const value = await load(controller.signal);
        if (controller.signal.aborted) return;
        setData(value);
        setError("");
        setUpdatedAt(new Date());
        again = poll && shouldContinue(value);
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : "Не удалось обновить данные");
      }
      if (again && !controller.signal.aborted) timer = setTimeout(tick, 1000);
    }
    void tick();
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [load, poll, shouldContinue, revision]);

  return { data, error, updatedAt, refresh };
}

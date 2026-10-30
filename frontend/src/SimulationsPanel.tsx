import { useCallback, useEffect, useState } from "react";

import { apiRequest, type Instrument, type Simulation, type SimulationRun } from "./api";
import { SimulationForm } from "./SimulationForm";
import { SimulationMonitor } from "./SimulationMonitor";
import { newerRun, runStatusLabel } from "./simulationDisplay";


export function SimulationsPanel({ token, instruments }: { token: string; instruments: Instrument[] }) {
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [editing, setEditing] = useState<Simulation | null | "new">(null);
  const [monitoring, setMonitoring] = useState<{ simulation: Simulation; run: SimulationRun } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [pollError, setPollError] = useState("");
  const [runs, setRuns] = useState<Record<number, SimulationRun | null>>({});
  const [pending, setPending] = useState(false);

  const updateRun = useCallback((run: SimulationRun) => {
    setRuns((current) => ({
      ...current, [run.simulation_id]: newerRun(current[run.simulation_id], run),
    }));
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const data = await apiRequest<Simulation[]>("/api/simulations", { signal: controller.signal }, token);
        const latestRuns = await Promise.all(data.map((simulation) =>
          apiRequest<SimulationRun | null>(`/api/simulations/${simulation.id}/run`, { signal: controller.signal }, token),
        ));
        if (controller.signal.aborted) return;
        setSimulations(data);
        setRuns(Object.fromEntries(data.map((simulation, index) => [simulation.id, latestRuns[index]])));
      } catch (cause) {
        if (!controller.signal.aborted) setError(message(cause));
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [token]);

  const runningIds = Object.values(runs).filter((run) => run?.status === "running")
    .map((run) => run!.simulation_id).sort((a, b) => a - b).join(",");
  const hidden = Boolean(editing || monitoring);
  useEffect(() => {
    if (!runningIds || hidden) return;
    const controller = new AbortController();
    let timer: ReturnType<typeof setTimeout>;
    async function tick() {
      try {
        const updates = await Promise.all(runningIds.split(",").map((id) =>
          apiRequest<SimulationRun | null>(`/api/simulations/${id}/run`, { signal: controller.signal }, token),
        ));
        if (controller.signal.aborted) return;
        updates.forEach((run) => { if (run) updateRun(run); });
        setPollError("");
      } catch (cause) {
        if (controller.signal.aborted) return;
        setPollError(message(cause));
      }
      if (!controller.signal.aborted) timer = setTimeout(tick, 1000);
    }
    void tick();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [runningIds, hidden, token, updateRun]);

  async function openSimulation(id: number) {
    setError("");
    setPending(true);
    try {
      setEditing(await apiRequest<Simulation>(`/api/simulations/${id}`, {}, token));
    } catch (cause) { setError(message(cause)); }
    finally { setPending(false); }
  }

  async function startRun(simulation: Simulation) {
    setPending(true);
    setError("");
    try {
      const run = await apiRequest<SimulationRun>(`/api/simulations/${simulation.id}/start`, { method: "POST" }, token);
      updateRun(run);
      setMonitoring({ simulation, run });
    } catch (cause) { setError(message(cause)); }
    finally { setPending(false); }
  }

  async function stopRun(simulationId: number) {
    setPending(true);
    setError("");
    try {
      updateRun(await apiRequest<SimulationRun>(`/api/simulations/${simulationId}/stop`, { method: "POST" }, token));
    } catch (cause) { setError(message(cause)); }
    finally { setPending(false); }
  }

  if (monitoring) return (
    <SimulationMonitor key={monitoring.run.id} token={token} instruments={instruments}
      simulation={monitoring.simulation} run={monitoring.run}
      onBack={() => setMonitoring(null)} onRunChanged={updateRun} />
  );

  if (editing) return (
    <SimulationForm instruments={instruments} token={token}
      simulation={editing === "new" ? null : editing}
      onCancel={() => setEditing(null)}
      onSaved={(saved) => {
        setSimulations((current) => current.some((item) => item.id === saved.id)
          ? current.map((item) => item.id === saved.id ? saved : item) : [saved, ...current]);
        setEditing(null);
      }} />
  );

  const canCreate = instruments.some((i) => i.is_active && i.base_asset.is_active && i.quote_asset.is_active);
  return (
    <section className="panel simulations-panel">
      <div className="panel-heading">
        <div><span className="eyebrow">Конфигурации</span><h2>Мои эксперименты</h2></div>
        <button className="primary-button" disabled={!canCreate || loading || pending}
          onClick={() => setEditing("new")} type="button">Создать эксперимент</button>
      </div>
      {error && <div className="form-error" role="alert">{error}</div>}
      {pollError && <div className="form-error" role="alert">Автообновление: {pollError}</div>}
      {!canCreate && <p className="notice">Для создания эксперимента нужен активный торговый инструмент.</p>}
      {loading ? <p className="muted">Загрузка экспериментов…</p> : simulations.length === 0 ? (
        <div className="empty-state"><strong>Сохранённых экспериментов пока нет</strong><span>Создайте конфигурацию рынка и стратегий.</span></div>
      ) : (
        <div className="simulation-grid">{simulations.map((simulation) => {
          const run = runs[simulation.id];
          return (
            <article className="simulation-card" key={simulation.id}>
              <div><span className="user-meta">Эксперимент #{simulation.id}</span><h3>{simulation.name}</h3></div>
              <div className="simulation-meta"><span>{simulation.duration_steps} шагов</span><span>seed {simulation.seed}</span>
                <span>{simulation.background_profiles.reduce((sum, p) => sum + p.agent_count, 0)} фоновых участников</span></div>
              <div className="chip-list compact">{simulation.instrument_configs.map((config) => (
                <span className="plain-chip" key={config.instrument_id}>{config.instrument?.base_asset.symbol}/{config.instrument?.quote_asset.symbol}</span>
              ))}</div>
              {run && <div className="run-summary"><span className={`run-status ${run.status}`}>{runStatusLabel(run.status)}</span>
                <span className="user-meta">Запуск #{run.id} · шаг {run.current_step}/{run.total_steps}</span>
                <progress aria-label="Прогресс запуска" value={run.current_step} max={run.total_steps} />
                {run.error_message && <span className="negative">{run.error_message}</span>}
              </div>}
              <div className="card-actions">
                <button className="secondary-button" disabled={pending || run?.status === "running"}
                  onClick={() => openSimulation(simulation.id)} type="button">Изменить</button>
                {run && <button className="secondary-button" disabled={pending}
                  onClick={() => setMonitoring({ simulation, run })} type="button">Мониторинг и результаты</button>}
                {run?.status === "running" ? (
                  <button className="danger-link" disabled={pending} onClick={() => stopRun(simulation.id)} type="button">Остановить</button>
                ) : <button className="primary-button" disabled={pending} onClick={() => startRun(simulation)} type="button">{run ? "Запустить заново" : "Запустить"}</button>}
              </div>
            </article>
          );
        })}</div>
      )}
    </section>
  );
}

function message(cause: unknown): string {
  return cause instanceof Error ? cause.message : "Не удалось выполнить запрос";
}

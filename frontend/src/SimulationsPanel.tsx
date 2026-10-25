import { useEffect, useState } from "react";

import {
  apiRequest,
  type Instrument,
  type Simulation,
  type SimulationRun,
} from "./api";
import { SimulationForm } from "./SimulationForm";


export function SimulationsPanel({
  token,
  instruments,
}: {
  token: string;
  instruments: Instrument[];
}) {
  const [simulations, setSimulations] = useState<Simulation[]>([]);
  const [editing, setEditing] = useState<Simulation | null | "new">(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [runs, setRuns] = useState<Record<number, SimulationRun | null>>({});
  const [runPendingId, setRunPendingId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    apiRequest<Simulation[]>("/api/simulations", {}, token)
      .then(async (data) => {
        if (!active) return;
        setSimulations(data);
        const latestRuns = await Promise.all(
          data.map((simulation) =>
            apiRequest<SimulationRun | null>(
              `/api/simulations/${simulation.id}/run`,
              {},
              token,
            ),
          ),
        );
        if (active) {
          setRuns(
            Object.fromEntries(
              data.map((simulation, index) => [simulation.id, latestRuns[index]]),
            ),
          );
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Не удалось загрузить эксперименты",
          );
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [token]);

  async function openSimulation(id: number) {
    setError("");
    try {
      const simulation = await apiRequest<Simulation>(
        `/api/simulations/${id}`,
        {},
        token,
      );
      setEditing(simulation);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось открыть эксперимент",
      );
    }
  }

  async function startRun(simulationId: number) {
    setRunPendingId(simulationId);
    setError("");
    try {
      const run = await apiRequest<SimulationRun>(
        `/api/simulations/${simulationId}/start`,
        { method: "POST" },
        token,
      );
      setRuns((current) => ({ ...current, [simulationId]: run }));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось запустить эксперимент",
      );
    } finally {
      setRunPendingId(null);
    }
  }

  async function stopRun(simulationId: number) {
    setRunPendingId(simulationId);
    setError("");
    try {
      const run = await apiRequest<SimulationRun>(
        `/api/simulations/${simulationId}/stop`,
        { method: "POST" },
        token,
      );
      setRuns((current) => ({ ...current, [simulationId]: run }));
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось остановить эксперимент",
      );
    } finally {
      setRunPendingId(null);
    }
  }

  if (editing) {
    return (
      <SimulationForm
        instruments={instruments}
        onCancel={() => setEditing(null)}
        onSaved={(saved) => {
          setSimulations((current) => {
            const exists = current.some((item) => item.id === saved.id);
            return exists
              ? current.map((item) => (item.id === saved.id ? saved : item))
              : [saved, ...current];
          });
          setEditing(null);
        }}
        simulation={editing === "new" ? null : editing}
        token={token}
      />
    );
  }

  const activeInstruments = instruments.filter(
    (item) => item.is_active && item.base_asset.is_active && item.quote_asset.is_active,
  );

  return (
    <section className="panel simulations-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Конфигурации</span>
          <h2>Мои эксперименты</h2>
        </div>
        <button
          className="primary-button"
          disabled={activeInstruments.length === 0}
          onClick={() => setEditing("new")}
          type="button"
        >
          Создать эксперимент
        </button>
      </div>

      {error && <div className="form-error">{error}</div>}
      {activeInstruments.length === 0 && (
        <div className="notice">
          Для создания эксперимента администратор должен добавить активный торговый инструмент.
        </div>
      )}

      {loading ? (
        <p className="muted">Загрузка экспериментов…</p>
      ) : simulations.length === 0 ? (
        <div className="empty-state">
          <strong>Сохранённых экспериментов пока нет</strong>
          <span>Создайте первую конфигурацию рынка и стратегий.</span>
        </div>
      ) : (
        <div className="simulation-grid">
          {simulations.map((simulation) => {
            const run = runs[simulation.id];
            return (
            <article className="simulation-card" key={simulation.id}>
              <div>
                <span className="user-meta">Эксперимент #{simulation.id}</span>
                <h3>{simulation.name}</h3>
              </div>
              <div className="simulation-meta">
                <span>{simulation.duration_steps} шагов</span>
                <span>seed {simulation.seed}</span>
                <span>
                  {simulation.background_profiles.reduce(
                    (sum, profile) => sum + profile.agent_count,
                    0,
                  )} участников
                </span>
              </div>
              <div className="chip-list compact">
                {simulation.instrument_configs.map((config) => (
                  <span className="plain-chip" key={config.instrument_id}>
                    {config.instrument?.base_asset.symbol}/
                    {config.instrument?.quote_asset.symbol}
                  </span>
                ))}
              </div>
              {run && (
                <span className="user-meta">
                  Запуск #{run.id}: {runStatusLabel(run.status)}, шаг {run.current_step}/
                  {run.total_steps}
                </span>
              )}
              <div className="card-actions">
                <button
                  className="secondary-button"
                  disabled={run?.status === "running"}
                  onClick={() => openSimulation(simulation.id)}
                  type="button"
                >
                  Открыть и изменить
                </button>
                {run?.status === "running" ? (
                  <button
                    className="danger-link"
                    disabled={runPendingId === simulation.id}
                    onClick={() => stopRun(simulation.id)}
                    type="button"
                  >
                    Остановить
                  </button>
                ) : (
                  <button
                    className="primary-button"
                    disabled={runPendingId === simulation.id}
                    onClick={() => startRun(simulation.id)}
                    type="button"
                  >
                    Запустить
                  </button>
                )}
              </div>
            </article>
            );
          })}
        </div>
      )}
    </section>
  );
}


function runStatusLabel(status: SimulationRun["status"]): string {
  return {
    running: "выполняется",
    stopped: "остановлен",
    completed: "завершён",
    failed: "ошибка",
  }[status];
}

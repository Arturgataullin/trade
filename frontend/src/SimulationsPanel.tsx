import { useEffect, useState } from "react";

import { apiRequest, type Instrument, type Simulation } from "./api";
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

  useEffect(() => {
    let active = true;
    apiRequest<Simulation[]>("/api/simulations", {}, token)
      .then((data) => {
        if (active) setSimulations(data);
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
          {simulations.map((simulation) => (
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
              <button
                className="secondary-button"
                onClick={() => openSimulation(simulation.id)}
                type="button"
              >
                Открыть и изменить
              </button>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

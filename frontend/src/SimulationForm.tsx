import { useEffect, useMemo, useState } from "react";
import type { FormEvent } from "react";

import {
  apiRequest,
  type BackgroundStrategyProfile,
  type Instrument,
  type Simulation,
  type SimulationInstrument,
  type SimulationPayload,
  type StrategyParameters,
  type StrategyType,
} from "./api";


type SimulationFormProps = {
  token: string;
  instruments: Instrument[];
  simulation: Simulation | null;
  onCancel: () => void;
  onSaved: (simulation: Simulation) => void;
};


export function SimulationForm({
  token,
  instruments,
  simulation,
  onCancel,
  onSaved,
}: SimulationFormProps) {
  const activeInstruments = useMemo(
    () =>
      instruments.filter(
        (item) =>
          item.is_active && item.base_asset.is_active && item.quote_asset.is_active,
      ),
    [instruments],
  );
  const [draft, setDraft] = useState<SimulationPayload>(() =>
    makeDraft(activeInstruments, simulation),
  );
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  useEffect(() => {
    if (activeInstruments.length === 0) return;

    // The catalog may finish loading after an existing experiment is opened.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setDraft((current) => {
      const instrumentConfigs = reconcileInstrumentConfigs(
        current.instrument_configs,
        activeInstruments,
      );

      if (instrumentConfigs === current.instrument_configs) return current;

      return {
        ...current,
        instrument_configs: instrumentConfigs,
      };
    });
  }, [activeInstruments]);

  function updateInstrument(
    index: number,
    patch: Partial<SimulationInstrument>,
  ) {
    setDraft((current) => ({
      ...current,
      instrument_configs: current.instrument_configs.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...patch } : item,
      ),
    }));
  }

  function addInstrument() {
    const selectedIds = new Set(
      draft.instrument_configs.map((item) => item.instrument_id),
    );
    const firstInstrument = instruments.find(
      (item) => item.id === draft.instrument_configs[0]?.instrument_id,
    );
    const available = activeInstruments.find(
      (item) =>
        !selectedIds.has(item.id) &&
        (!firstInstrument || item.quote_asset_id === firstInstrument.quote_asset_id),
    );
    if (!available) {
      setError("Нет второго активного инструмента с тем же котируемым активом");
      return;
    }
    setError("");
    setDraft((current) => ({
      ...current,
      instrument_configs: [
        ...current.instrument_configs,
        emptyInstrument(available),
      ],
    }));
  }

  function updateProfile(
    index: number,
    profile: BackgroundStrategyProfile,
  ) {
    setDraft((current) => ({
      ...current,
      background_profiles: current.background_profiles.map((item, itemIndex) =>
        itemIndex === index ? profile : item,
      ),
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPending(true);
    setError("");
    try {
      const saved = await apiRequest<Simulation>(
        simulation ? `/api/simulations/${simulation.id}` : "/api/simulations",
        {
          method: simulation ? "PUT" : "POST",
          body: JSON.stringify(cleanPayload(draft)),
        },
        token,
      );
      onSaved(saved);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось сохранить эксперимент",
      );
    } finally {
      setPending(false);
    }
  }

  const quoteSymbol = quoteAssetSymbol(draft, instruments);

  return (
    <form className="simulation-form" onSubmit={submit}>
      <div className="editor-heading">
        <div>
          <span className="eyebrow">Конфигурация</span>
          <h1>{simulation ? "Изменить эксперимент" : "Новый эксперимент"}</h1>
        </div>
        <button className="secondary-button" onClick={onCancel} type="button">
          К списку
        </button>
      </div>

      {error && <div className="form-error">{error}</div>}

      <section className="panel form-section">
        <div className="section-title">
          <span>01</span>
          <div>
            <h2>Параметры рынка</h2>
            <p>Основные условия и начальное состояние фоновых участников.</p>
          </div>
        </div>

        <div className="form-grid three-columns">
          <label className="wide-field">
            Название эксперимента
            <input
              maxLength={200}
              onChange={(event) =>
                setDraft((current) => ({ ...current, name: event.target.value }))
              }
              required
              value={draft.name}
            />
          </label>
          <NumberField
            label="Продолжительность, шагов"
            min={1}
            onChange={(value) =>
              setDraft((current) => ({ ...current, duration_steps: value }))
            }
            step={1}
            value={draft.duration_steps}
          />
          <NumberField
            label="Seed"
            onChange={(value) =>
              setDraft((current) => ({ ...current, seed: value }))
            }
            step={1}
            value={draft.seed}
          />
          <NumberField
            label={`Баланс фонового участника, ${quoteSymbol}`}
            min={0}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                background_initial_quote_balance: value,
              }))
            }
            value={draft.background_initial_quote_balance}
          />
          <NumberField
            label="Минимальный объём заявки"
            min={0.00000001}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                background_min_order_volume: value,
              }))
            }
            value={draft.background_min_order_volume}
          />
          <NumberField
            label="Максимальный объём заявки"
            min={0.00000001}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                background_max_order_volume: value,
              }))
            }
            value={draft.background_max_order_volume}
          />
        </div>

        <div className="subsection-heading">
          <h3>Инструменты</h3>
          <button
            className="text-button"
            disabled={draft.instrument_configs.length >= 2}
            onClick={addInstrument}
            type="button"
          >
            + Добавить второй
          </button>
        </div>

        <div className="config-list">
          {draft.instrument_configs.map((config, index) => {
            const selected = instruments.find(
              (item) => item.id === config.instrument_id,
            );
            const otherSelected = draft.instrument_configs
              .filter((_, itemIndex) => itemIndex !== index)
              .map((item) =>
                instruments.find(
                  (instrument) => instrument.id === item.instrument_id,
                ),
              )
              .find((instrument) => instrument !== undefined);
            const availableForSelect = activeInstruments.filter(
              (instrument) =>
                !otherSelected ||
                instrument.quote_asset_id === otherSelected.quote_asset_id,
            );
            return (
              <div className="config-card" key={`${config.instrument_id}-${index}`}>
                <div className="config-card-heading">
                  <strong>Инструмент {index + 1}</strong>
                  {draft.instrument_configs.length > 1 && (
                    <button
                      className="danger-link"
                      onClick={() =>
                        setDraft((current) => ({
                          ...current,
                          instrument_configs: current.instrument_configs.filter(
                            (_, itemIndex) => itemIndex !== index,
                          ),
                        }))
                      }
                      type="button"
                    >
                      Удалить
                    </button>
                  )}
                </div>
                <div className="form-grid three-columns">
                  <label>
                    Торговая пара
                    <select
                      onChange={(event) =>
                        updateInstrument(index, {
                          instrument_id: Number(event.target.value),
                        })
                      }
                      required
                      value={config.instrument_id}
                    >
                      {availableForSelect.map((instrument) => (
                        <option
                          disabled={draft.instrument_configs.some(
                            (item, itemIndex) =>
                              itemIndex !== index &&
                              item.instrument_id === instrument.id,
                          )}
                          key={instrument.id}
                          value={instrument.id}
                        >
                          {instrument.base_asset.symbol}/{instrument.quote_asset.symbol}
                        </option>
                      ))}
                    </select>
                  </label>
                  <NumberField
                    label="Начальная цена"
                    min={0.00000001}
                    onChange={(value) =>
                      updateInstrument(index, { initial_price: value })
                    }
                    value={config.initial_price}
                  />
                  <NumberField
                    label={`Актив у фонового участника, ${selected?.base_asset.symbol ?? "ед."}`}
                    min={0}
                    onChange={(value) =>
                      updateInstrument(index, {
                        background_initial_base_balance: value,
                      })
                    }
                    value={config.background_initial_base_balance}
                  />
                </div>
              </div>
            );
          })}
        </div>
        <p className="panel-note">
          При выборе двух инструментов у них должен быть общий котируемый актив,
          например BTC/USD и ETH/USD.
        </p>
      </section>

      <section className="panel form-section">
        <div className="section-title">
          <span>02</span>
          <div>
            <h2>Фоновые профили</h2>
            <p>Количество участников и правила принятия решений.</p>
          </div>
        </div>

        <div className="config-list">
          {draft.background_profiles.map((profile, index) => (
            <div className="config-card" key={index}>
              <div className="config-card-heading">
                <strong>Профиль {index + 1}</strong>
                {draft.background_profiles.length > 1 && (
                  <button
                    className="danger-link"
                    onClick={() =>
                      setDraft((current) => ({
                        ...current,
                        background_profiles: current.background_profiles.filter(
                          (_, itemIndex) => itemIndex !== index,
                        ),
                      }))
                    }
                    type="button"
                  >
                    Удалить
                  </button>
                )}
              </div>
              <div className="form-grid strategy-grid">
                <NumberField
                  label="Количество участников"
                  min={1}
                  onChange={(value) =>
                    updateProfile(index, { ...profile, agent_count: value })
                  }
                  step={1}
                  value={profile.agent_count}
                />
                <StrategyFields
                  onChange={(value) =>
                    updateProfile(index, { ...value, agent_count: profile.agent_count })
                  }
                  value={profile}
                />
              </div>
            </div>
          ))}
        </div>
        <button
          className="secondary-button add-row-button"
          onClick={() =>
            setDraft((current) => ({
              ...current,
              background_profiles: [
                ...current.background_profiles,
                { ...randomStrategy(), agent_count: 10 },
              ],
            }))
          }
          type="button"
        >
          + Добавить профиль
        </button>
      </section>

      <section className="panel form-section">
        <div className="section-title">
          <span>03</span>
          <div>
            <h2>Тестируемая стратегия</h2>
            <p>Отдельный участник, для которого позже будут рассчитаны результаты.</p>
          </div>
        </div>

        <div className="form-grid three-columns">
          <NumberField
            label={`Начальный баланс, ${quoteSymbol}`}
            min={0}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                test_initial_quote_balance: value,
              }))
            }
            value={draft.test_initial_quote_balance}
          />
          <NumberField
            label="Минимальный объём заявки"
            min={0.00000001}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                test_min_order_volume: value,
              }))
            }
            value={draft.test_min_order_volume}
          />
          <NumberField
            label="Максимальный объём заявки"
            min={0.00000001}
            onChange={(value) =>
              setDraft((current) => ({
                ...current,
                test_max_order_volume: value,
              }))
            }
            value={draft.test_max_order_volume}
          />
        </div>

        <div className="form-grid strategy-grid test-strategy-grid">
          <StrategyFields
            onChange={(value) =>
              setDraft((current) => ({ ...current, test_strategy: value }))
            }
            value={draft.test_strategy}
          />
        </div>

        <div className="subsection-heading">
          <h3>Начальные виртуальные активы</h3>
        </div>
        <div className="form-grid two-columns">
          {draft.instrument_configs.map((config, index) => {
            const selected = instruments.find(
              (item) => item.id === config.instrument_id,
            );
            return (
              <NumberField
                key={`${config.instrument_id}-${index}`}
                label={selected?.base_asset.symbol ?? `Инструмент ${index + 1}`}
                min={0}
                onChange={(value) =>
                  updateInstrument(index, { test_initial_base_balance: value })
                }
                value={config.test_initial_base_balance}
              />
            );
          })}
        </div>
      </section>

      <div className="form-actions">
        <button className="secondary-button" onClick={onCancel} type="button">
          Отмена
        </button>
        <button className="primary-button" disabled={pending} type="submit">
          {pending ? "Сохраняем…" : simulation ? "Сохранить изменения" : "Создать эксперимент"}
        </button>
      </div>
    </form>
  );
}


function StrategyFields({
  value,
  onChange,
}: {
  value: StrategyParameters;
  onChange: (value: StrategyParameters) => void;
}) {
  function changeType(strategyType: StrategyType) {
    onChange(
      strategyType === "random" ? randomStrategy() : trendStrategy(),
    );
  }

  return (
    <>
      <label>
        Тип стратегии
        <select
          onChange={(event) => changeType(event.target.value as StrategyType)}
          value={value.strategy_type}
        >
          <option value="random">Random</option>
          <option value="trend_following">Trend Following</option>
        </select>
      </label>
      {value.strategy_type === "random" ? (
        <>
          <NumberField
            label="BUY, %"
            max={100}
            min={0}
            onChange={(next) => onChange({ ...value, buy_probability: next })}
            value={value.buy_probability ?? 0}
          />
          <NumberField
            label="SELL, %"
            max={100}
            min={0}
            onChange={(next) => onChange({ ...value, sell_probability: next })}
            value={value.sell_probability ?? 0}
          />
          <NumberField
            label="HOLD, %"
            max={100}
            min={0}
            onChange={(next) => onChange({ ...value, hold_probability: next })}
            value={value.hold_probability ?? 0}
          />
          <NumberField
            label="Отклонение цены, %"
            min={0}
            onChange={(next) => onChange({ ...value, price_deviation_pct: next })}
            value={value.price_deviation_pct ?? 0}
          />
        </>
      ) : (
        <>
          <NumberField
            label="Окно наблюдения"
            min={1}
            onChange={(next) => onChange({ ...value, trend_window: next })}
            step={1}
            value={value.trend_window ?? 1}
          />
          <NumberField
            label="Порог изменения, %"
            min={0.000001}
            onChange={(next) =>
              onChange({ ...value, trend_threshold_pct: next })
            }
            value={value.trend_threshold_pct ?? 1}
          />
        </>
      )}
    </>
  );
}


function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  step = "any",
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min?: number;
  max?: number;
  step?: number | "any";
}) {
  return (
    <label>
      {label}
      <input
        max={max}
        min={min}
        onChange={(event) => onChange(Number(event.target.value))}
        required
        step={step}
        type="number"
        value={value}
      />
    </label>
  );
}


function randomStrategy(): StrategyParameters {
  return {
    strategy_type: "random",
    buy_probability: 34,
    sell_probability: 33,
    hold_probability: 33,
    price_deviation_pct: 1,
    trend_window: null,
    trend_threshold_pct: null,
  };
}


function trendStrategy(): StrategyParameters {
  return {
    strategy_type: "trend_following",
    buy_probability: null,
    sell_probability: null,
    hold_probability: null,
    price_deviation_pct: null,
    trend_window: 20,
    trend_threshold_pct: 1.5,
  };
}


function emptyInstrument(instrument: Instrument): SimulationInstrument {
  const defaultPrice = instrument.base_asset.symbol === "BTC" ? 60000 : 3000;
  return {
    instrument_id: instrument.id,
    initial_price: defaultPrice,
    background_initial_base_balance: 10,
    test_initial_base_balance: 1,
  };
}


function reconcileInstrumentConfigs(
  configs: SimulationInstrument[],
  activeInstruments: Instrument[],
): SimulationInstrument[] {
  if (activeInstruments.length === 0) return configs;

  const activeById = new Map(
    activeInstruments.map((instrument) => [instrument.id, instrument]),
  );
  const firstStillActive = configs
    .map((config) => activeById.get(config.instrument_id))
    .find((instrument) => instrument !== undefined);
  const quoteAssetId =
    firstStillActive?.quote_asset_id ?? activeInstruments[0].quote_asset_id;
  const reservedIds = new Set(
    configs
      .map((config) => activeById.get(config.instrument_id))
      .filter(
        (instrument): instrument is Instrument =>
          instrument !== undefined && instrument.quote_asset_id === quoteAssetId,
      )
      .map((instrument) => instrument.id),
  );
  const usedIds = new Set<number>();
  const result: SimulationInstrument[] = [];

  for (const config of configs) {
    const currentInstrument = activeById.get(config.instrument_id);
    if (
      currentInstrument &&
      currentInstrument.quote_asset_id === quoteAssetId &&
      !usedIds.has(currentInstrument.id)
    ) {
      result.push(config);
      usedIds.add(currentInstrument.id);
      continue;
    }

    const replacement = activeInstruments.find(
      (instrument) =>
        instrument.quote_asset_id === quoteAssetId &&
        !usedIds.has(instrument.id) &&
        !reservedIds.has(instrument.id),
    );
    if (!replacement) continue;

    result.push({
      ...config,
      instrument_id: replacement.id,
    });
    usedIds.add(replacement.id);
  }

  if (result.length === 0) {
    result.push(emptyInstrument(activeInstruments[0]));
  }

  const unchanged =
    result.length === configs.length &&
    result.every(
      (config, index) => config.instrument_id === configs[index].instrument_id,
    );

  return unchanged ? configs : result;
}


function makeDraft(
  instruments: Instrument[],
  simulation: Simulation | null,
): SimulationPayload {
  if (simulation) {
    const draft = cleanPayload(simulation);
    return {
      ...draft,
      instrument_configs: reconcileInstrumentConfigs(
        draft.instrument_configs,
        instruments,
      ),
    };
  }

  return {
    name: "",
    duration_steps: 1000,
    seed: 42,
    background_initial_quote_balance: 10000,
    background_min_order_volume: 0.01,
    background_max_order_volume: 1,
    test_initial_quote_balance: 10000,
    test_min_order_volume: 0.01,
    test_max_order_volume: 1,
    instrument_configs: instruments[0] ? [emptyInstrument(instruments[0])] : [],
    background_profiles: [{ ...randomStrategy(), agent_count: 10 }],
    test_strategy: randomStrategy(),
  };
}


function cleanPayload(source: SimulationPayload): SimulationPayload {
  return {
    name: source.name,
    duration_steps: Number(source.duration_steps),
    seed: Number(source.seed),
    background_initial_quote_balance: Number(source.background_initial_quote_balance),
    background_min_order_volume: Number(source.background_min_order_volume),
    background_max_order_volume: Number(source.background_max_order_volume),
    test_initial_quote_balance: Number(source.test_initial_quote_balance),
    test_min_order_volume: Number(source.test_min_order_volume),
    test_max_order_volume: Number(source.test_max_order_volume),
    instrument_configs: source.instrument_configs.map((item) => ({
      instrument_id: Number(item.instrument_id),
      initial_price: Number(item.initial_price),
      background_initial_base_balance: Number(
        item.background_initial_base_balance,
      ),
      test_initial_base_balance: Number(item.test_initial_base_balance),
    })),
    background_profiles: source.background_profiles.map((item) => ({
      ...strategyPayload(item),
      agent_count: Number(item.agent_count),
    })),
    test_strategy: strategyPayload(source.test_strategy),
  };
}


function strategyPayload(source: StrategyParameters): StrategyParameters {
  return {
    strategy_type: source.strategy_type,
    buy_probability:
      source.buy_probability === null ? null : Number(source.buy_probability),
    sell_probability:
      source.sell_probability === null ? null : Number(source.sell_probability),
    hold_probability:
      source.hold_probability === null ? null : Number(source.hold_probability),
    price_deviation_pct:
      source.price_deviation_pct === null
        ? null
        : Number(source.price_deviation_pct),
    trend_window:
      source.trend_window === null ? null : Number(source.trend_window),
    trend_threshold_pct:
      source.trend_threshold_pct === null
        ? null
        : Number(source.trend_threshold_pct),
  };
}


function quoteAssetSymbol(
  draft: SimulationPayload,
  instruments: Instrument[],
): string {
  const instrument = instruments.find(
    (item) => item.id === draft.instrument_configs[0]?.instrument_id,
  );
  return instrument?.quote_asset.symbol ?? "котируемый актив";
}

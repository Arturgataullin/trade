import { useCallback, useState } from "react";
import type { ReactNode } from "react";

import {
  apiRequest, type Instrument, type OrderBook, type ParticipantBalance,
  type RunParticipant, type Simulation, type SimulationResults,
  type SimulationRun, type TradingOrder, type TradingTrade,
} from "./api";
import { decimalLabel, runStatusLabel } from "./simulationDisplay";
import { usePolling } from "./usePolling";

const continueResults = (results: SimulationResults) => results.status === "running";
const PAGE_SIZE = 50;
const orderStatuses = {
  open: "Активна", partial: "Частично исполнена", filled: "Исполнена",
  cancelled: "Отменена", rejected: "Отклонена",
};

type MonitorProps = {
  token: string;
  instruments: Instrument[];
  simulation: Simulation;
  run: SimulationRun;
  onBack: () => void;
  onRunChanged: (run: SimulationRun) => void;
};

export function SimulationMonitor({ token, instruments, simulation, run, onBack, onRunChanged }: MonitorProps) {
  const [instrumentId, setInstrumentId] = useState(run.instrument_ids[0]);
  const [stopping, setStopping] = useState(false);
  const [actionError, setActionError] = useState("");
  const loadResults = useCallback(async (signal: AbortSignal) => {
    const results = await apiRequest<SimulationResults>(
      `/api/simulations/${simulation.id}/results?run_id=${run.id}`, { signal }, token,
    );
    if (!signal.aborted) onRunChanged({
      ...run, status: results.status, current_step: results.current_step,
      error_message: results.error_message,
    });
    return results;
  }, [simulation.id, run, token, onRunChanged]);
  const { data: results, error, updatedAt, refresh } = usePolling(loadResults, true, continueResults);
  const status = results?.status ?? run.status;
  const running = status === "running";
  const currentStep = results?.current_step ?? run.current_step;
  const percent = Math.min(100, Math.round(currentStep / Math.max(run.total_steps, 1) * 100));
  const pair = instruments.find((item) => item.id === instrumentId);
  const quoteSymbol = instruments.find((item) => item.quote_asset_id === results?.quote_asset_id)?.quote_asset.symbol ?? pair?.quote_asset.symbol ?? "ед.";
  const assetSymbol = (id: number) => {
    for (const instrument of instruments) {
      if (instrument.base_asset_id === id) return instrument.base_asset.symbol;
      if (instrument.quote_asset_id === id) return instrument.quote_asset.symbol;
    }
    return `Актив #${id}`;
  };

  async function stop() {
    setStopping(true);
    setActionError("");
    try {
      const stopped = await apiRequest<SimulationRun>(
        `/api/simulations/${simulation.id}/stop?run_id=${run.id}`, { method: "POST" }, token,
      );
      onRunChanged(stopped);
    } catch (cause) {
      setActionError(cause instanceof Error ? cause.message : "Не удалось остановить запуск");
    } finally {
      setStopping(false);
      refresh();
    }
  }

  return (
    <div className="simulation-monitor">
      <div className="editor-heading">
        <div><span className="eyebrow">Запуск #{run.id}</span><h1>{simulation.name}</h1></div>
        <div className="card-actions">
          {running && <button className="secondary-button negative" disabled={stopping} onClick={stop} type="button">{stopping ? "Останавливаем…" : "Остановить запуск"}</button>}
          <button className="secondary-button" onClick={onBack} type="button">К экспериментам</button>
        </div>
      </div>

      <section className="panel monitor-progress" aria-label="Состояние запуска">
        <div className="monitor-toolbar"><span className={`run-status ${status}`}>{runStatusLabel(status)}</span>
          <strong>Шаг {currentStep} / {run.total_steps} · {percent}%</strong>
          <button className="text-button" onClick={refresh} type="button">Обновить</button></div>
        <progress aria-label="Прогресс моделирования" value={currentStep} max={run.total_steps} />
        <span className="user-meta">Seed {run.seed} · Начало: {new Date(run.started_at).toLocaleString("ru-RU")}
          {updatedAt && ` · Обновлено: ${updatedAt.toLocaleTimeString("ru-RU")}`}</span>
        {running ? <p className="panel-note">Данные обновляются раз в секунду. Результаты пока промежуточные.</p>
          : <p className="panel-note">Запуск завершён или остановлен. Оставшиеся заявки отменены, резервы освобождены.</p>}
        {error && <RequestError message={error} retry={refresh} stale={Boolean(results)} />}
        {actionError && <div className="form-error" role="alert">{actionError}</div>}
        {(results?.error_message ?? run.error_message) && <div className="form-error" role="alert">{results?.error_message ?? run.error_message}</div>}
      </section>

      {results ? <>
        <section className="panel" aria-label="Результаты стратегии">
          <h2>Тестируемая стратегия</h2>
          <div className="result-grid">
            <Metric label={`Начальный портфель, ${quoteSymbol}`} value={decimalLabel(results.initial_portfolio_value)} />
            <Metric label={`Текущий портфель, ${quoteSymbol}`} value={decimalLabel(results.portfolio_value)} />
            <Metric label={`Прибыль, ${quoteSymbol}`} value={decimalLabel(results.profit)} tone={results.profit.startsWith("-") ? "negative" : "positive"} />
            <Metric label="Доходность, %" value={decimalLabel(results.return_pct, 4)} />
            <Metric label="Сделки стратегии" value={String(results.test_trade_count)} />
            <Metric label="Все сделки" value={String(results.trade_count)} />
          </div>
          <p className="panel-note">Стоимость портфеля включает доступные и зарезервированные средства и активы по последним ценам сделок.</p>
          {results.return_pct === null && <p className="panel-note">Доходность не определена: начальная стоимость портфеля равна нулю.</p>}
          <h3>Баланс тестируемого участника #{results.test_participant_id}</h3>
          <BalanceTable balances={results.balances} assetSymbol={assetSymbol} />
        </section>
      </> : !error && <p className="muted" role="status">Загрузка результатов…</p>}

      <section className="panel">
        <div className="panel-heading monitor-toolbar"><h2>Торговый инструмент</h2>
          <label>Пара
            <select value={instrumentId} onChange={(event) => setInstrumentId(Number(event.target.value))}>
              {run.instrument_ids.map((id) => {
                const instrument = instruments.find((item) => item.id === id);
                return <option key={id} value={id}>{instrument ? `${instrument.base_asset.symbol}/${instrument.quote_asset.symbol}` : `Инструмент #${id}`}</option>;
              })}
            </select>
          </label>
        </div>
        {instrumentId ? <MarketPanels key={instrumentId} simulationId={simulation.id} runId={run.id}
          instrumentId={instrumentId} token={token} running={running}
          base={pair?.base_asset.symbol ?? "ед."} quote={pair?.quote_asset.symbol ?? "ед."} />
          : <p className="muted">У запуска нет инструментов.</p>}
      </section>
      <section className="panel"><h2>Виртуальные участники</h2>
        <Participants simulationId={simulation.id} runId={run.id} token={token} running={running} assetSymbol={assetSymbol} />
      </section>
    </div>
  );
}

function Metric({ label, value, tone = "" }: { label: string; value: string; tone?: string }) {
  return <div className="result-metric"><span>{label}</span><strong className={tone}>{value}</strong></div>;
}

function RequestError({ message, retry, stale = false }: { message: string; retry: () => void; stale?: boolean }) {
  return <div className="form-error" role="alert">{message}{stale && " Показаны последние полученные данные."}
    {" "}<button className="text-button" onClick={retry} type="button">Повторить</button></div>;
}

function BalanceTable({ balances, assetSymbol }: { balances: ParticipantBalance[]; assetSymbol: (id: number) => string }) {
  return <DataTable headers={["Актив", "Доступно", "В резерве"]}>
    {balances.map((b) => <tr key={b.asset_id}><td>{assetSymbol(b.asset_id)}</td><td>{decimalLabel(b.available)}</td><td>{decimalLabel(b.reserved)}</td></tr>)}
  </DataTable>;
}

function DataTable({ headers, children }: { headers: string[]; children: ReactNode }) {
  return <div className="table-wrap monitor-table"><table><thead><tr>{headers.map((header) => <th key={header} scope="col">{header}</th>)}</tr></thead>
    <tbody>{children}</tbody></table></div>;
}

type MarketProps = { simulationId: number; runId: number; instrumentId: number; token: string; running: boolean; base: string; quote: string };

function MarketPanels(props: MarketProps) {
  const { simulationId, runId, instrumentId, token, running, base, quote } = props;
  const [tab, setTab] = useState<"trades" | "orders">("trades");
  const load = useCallback((signal: AbortSignal) => apiRequest<OrderBook>(
    `/api/simulations/${simulationId}/order-book?run_id=${runId}&instrument_id=${instrumentId}&limit=20`, { signal }, token,
  ), [simulationId, runId, instrumentId, token]);
  const { data: book, error, refresh } = usePolling(load, running);
  return <>
    <div className="monitor-toolbar"><h3>Стакан заявок</h3><span>Последняя цена: {book ? decimalLabel(book.last_price) : "—"} {quote}</span></div>
    <p className="panel-note">До 20 лучших заявок с каждой стороны. При равной цене первой исполняется более ранняя заявка.</p>
    {error && <RequestError message={error} retry={refresh} stale={Boolean(book)} />}
    {!book && !error && <p className="muted">Загрузка стакана…</p>}
    {book && <div className="order-books">{(["bids", "asks"] as const).map((side) => (
      <div key={side}><h3 className={side === "bids" ? "positive" : "negative"}>{side === "bids" ? "Покупка · BUY" : "Продажа · SELL"}</h3>
        <DataTable headers={[`Цена, ${quote}`, `Остаток, ${base}`, "Заявка"]}>
          {book[side].map((order) => <tr key={order.id}><td>{decimalLabel(order.price)}</td><td>{decimalLabel(order.remaining_volume)}</td><td>#{order.id}</td></tr>)}
          {book[side].length === 0 && <tr><td colSpan={3}>Нет активных заявок</td></tr>}
        </DataTable>
      </div>
    ))}</div>}
    <div className="monitor-tabs" aria-label="История торгов">
      <button className={tab === "trades" ? "active" : ""} aria-pressed={tab === "trades"} onClick={() => setTab("trades")} type="button">Сделки</button>
      <button className={tab === "orders" ? "active" : ""} aria-pressed={tab === "orders"} onClick={() => setTab("orders")} type="button">Заявки</button>
    </div>
    <History key={tab} {...props} kind={tab} />
  </>;
}

function History(props: MarketProps & { kind: "orders" | "trades" }) {
  const [cursors, setCursors] = useState([0]);
  const cursor = cursors[cursors.length - 1];
  return <HistoryPage key={cursor} {...props} cursor={cursor} page={cursors.length}
    onBack={() => setCursors((current) => current.slice(0, -1))}
    onNext={(next) => setCursors((current) => [...current, next])} />;
}

function HistoryPage({ simulationId, runId, instrumentId, token, running, kind, base, quote, cursor, page, onBack, onNext }: MarketProps & {
  kind: "orders" | "trades"; cursor: number; page: number; onBack: () => void; onNext: (cursor: number) => void;
}) {
  const load = useCallback((signal: AbortSignal) => apiRequest<(TradingOrder | TradingTrade)[]>(
    `/api/simulations/${simulationId}/${kind}?run_id=${runId}&instrument_id=${instrumentId}&after=${cursor}&limit=${PAGE_SIZE + 1}`, { signal }, token,
  ), [simulationId, runId, instrumentId, kind, cursor, token]);
  const { data, error, refresh } = usePolling(load, running);
  const rows = data?.slice(0, PAGE_SIZE) ?? [];
  return <>
    {error && <RequestError message={error} retry={refresh} stale={Boolean(data)} />}
    {!data && !error && <p className="muted">Загрузка истории…</p>}
    {data && <DataTable headers={kind === "orders"
      ? ["Заявка", "Шаг", "Участник", "Действие", `Цена, ${quote}`, `Объём, ${base}`, "Остаток", "Статус"]
      : ["Сделка", "Шаг", `Цена, ${quote}`, `Объём, ${base}`, `Сумма, ${quote}`, "BUY / SELL"]}>
      {rows.map((row) => "side" in row ? (
        <tr key={row.id}><td>#{row.id}</td><td>{row.step}</td><td>#{row.participant_id}</td><td className={row.side === "BUY" ? "positive" : "negative"}>{row.side}</td>
          <td>{decimalLabel(row.price)}</td><td>{decimalLabel(row.volume)}</td><td>{decimalLabel(row.remaining_volume)}</td>
          <td>{orderStatuses[row.status]}{row.rejection_reason && <small className="negative">{row.rejection_reason}</small>}</td></tr>
      ) : (
        <tr key={row.id}><td>#{row.id}</td><td>{row.step}</td><td>{decimalLabel(row.price)}</td><td>{decimalLabel(row.volume)}</td>
          <td>{decimalLabel(row.quote_amount)}</td><td>#{row.buy_order_id} / #{row.sell_order_id}</td></tr>
      ))}
      {rows.length === 0 && <tr><td colSpan={kind === "orders" ? 8 : 6}>Пока нет {kind === "orders" ? "заявок" : "сделок"}</td></tr>}
    </DataTable>}
    <Pagination label="История" page={page} back={onBack} next={() => onNext(rows[rows.length - 1].sequence_number)} hasNext={Boolean(data && data.length > PAGE_SIZE)} />
  </>;
}

function Pagination({ label, page, back, next, hasNext }: { label: string; page: number; back: () => void; next: () => void; hasNext: boolean }) {
  return <nav className="pagination" aria-label={label}><button className="secondary-button" disabled={page === 1} onClick={back} type="button">Назад</button>
    <span className="user-meta">Страница {page} · до {PAGE_SIZE} записей</span>
    <button className="secondary-button" disabled={!hasNext} onClick={next} type="button">Далее</button></nav>;
}

function Participants(props: { simulationId: number; runId: number; token: string; running: boolean; assetSymbol: (id: number) => string }) {
  const [cursors, setCursors] = useState([0]);
  const cursor = cursors[cursors.length - 1];
  return <ParticipantPage key={cursor} {...props} cursor={cursor} page={cursors.length}
    back={() => setCursors((current) => current.slice(0, -1))}
    next={(next) => setCursors((current) => [...current, next])} />;
}

function ParticipantPage({ simulationId, runId, token, running, assetSymbol, cursor, page, back, next }: {
  simulationId: number; runId: number; token: string; running: boolean; assetSymbol: (id: number) => string;
  cursor: number; page: number; back: () => void; next: (cursor: number) => void;
}) {
  const load = useCallback((signal: AbortSignal) => apiRequest<RunParticipant[]>(
    `/api/simulations/${simulationId}/balances?run_id=${runId}&after=${cursor}&limit=${PAGE_SIZE + 1}`, { signal }, token,
  ), [simulationId, runId, cursor, token]);
  const { data, error, refresh } = usePolling(load, running);
  const participants = data?.slice(0, PAGE_SIZE) ?? [];
  return <>
    {error && <RequestError message={error} retry={refresh} stale={Boolean(data)} />}
    {!data && !error && <p className="muted">Загрузка балансов…</p>}
    {data && <DataTable headers={["Участник", "Тип", "Актив", "Доступно", "В резерве"]}>
      {participants.flatMap((p) => p.balances.map((b) => <tr key={`${p.id}:${b.asset_id}`}>
        <td>#{p.id} <small>порядковый №{p.sequence_number}</small></td><td>{p.participant_type === "test" ? "Тестируемый" : "Фоновый"}</td>
        <td>{assetSymbol(b.asset_id)}</td><td>{decimalLabel(b.available)}</td><td>{decimalLabel(b.reserved)}</td></tr>))}
      {participants.length === 0 && <tr><td colSpan={5}>Нет участников</td></tr>}
    </DataTable>}
    <Pagination label="Участники" page={page} back={back} next={() => next(participants[participants.length - 1].sequence_number)} hasNext={Boolean(data && data.length > PAGE_SIZE)} />
  </>;
}

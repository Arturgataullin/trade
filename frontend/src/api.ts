export type UserRole = "user" | "admin";

export type User = {
  id: number;
  email: string;
  is_active: boolean;
  role: UserRole;
  created_at: string;
};

export type TokenResponse = {
  access_token: string;
  token_type: "bearer";
};

export type Asset = {
  id: number;
  symbol: string;
  name: string;
  is_active: boolean;
};

export type Instrument = {
  id: number;
  base_asset_id: number;
  quote_asset_id: number;
  is_active: boolean;
  base_asset: Asset;
  quote_asset: Asset;
};

export type StrategyType = "random" | "trend_following";

export type StrategyParameters = {
  strategy_type: StrategyType;
  buy_probability: number | null;
  sell_probability: number | null;
  hold_probability: number | null;
  price_deviation_pct: number | null;
  trend_window: number | null;
  trend_threshold_pct: number | null;
};

export type BackgroundStrategyProfile = StrategyParameters & {
  id?: number;
  agent_count: number;
};

export type TestStrategy = StrategyParameters & {
  id?: number;
};

export type SimulationInstrument = {
  id?: number;
  instrument_id: number;
  initial_price: number;
  background_initial_base_balance: number;
  test_initial_base_balance: number;
  instrument?: Instrument;
};

export type SimulationPayload = {
  name: string;
  duration_steps: number;
  seed: number;
  background_initial_quote_balance: number;
  background_min_order_volume: number;
  background_max_order_volume: number;
  test_initial_quote_balance: number;
  test_min_order_volume: number;
  test_max_order_volume: number;
  instrument_configs: SimulationInstrument[];
  background_profiles: BackgroundStrategyProfile[];
  test_strategy: TestStrategy;
};

export type Simulation = SimulationPayload & {
  id: number;
  owner_id: number;
  created_at: string;
  updated_at: string;
};

export type SimulationRunStatus =
  | "running"
  | "stopped"
  | "completed"
  | "failed";

export type SimulationRun = {
  id: number;
  simulation_id: number;
  status: SimulationRunStatus;
  current_step: number;
  total_steps: number;
  seed: number;
  engine_version: string;
  stop_requested: boolean;
  started_at: string;
  finished_at: string | null;
  error_message: string | null;
  instrument_ids: number[];
};

// Pydantic returns Decimal values as strings to preserve their precision.
export type DecimalValue = string;

export type TradingOrder = {
  id: number;
  run_id: number;
  participant_id: number;
  instrument_id: number;
  sequence_number: number;
  step: number;
  side: "BUY" | "SELL";
  status: "open" | "partial" | "filled" | "cancelled" | "rejected";
  price: DecimalValue;
  volume: DecimalValue;
  remaining_volume: DecimalValue;
  reserved_amount: DecimalValue;
  rejection_reason: string | null;
};

export type TradingTrade = {
  id: number;
  run_id: number;
  instrument_id: number;
  buy_order_id: number;
  sell_order_id: number;
  sequence_number: number;
  step: number;
  price: DecimalValue;
  volume: DecimalValue;
  quote_amount: DecimalValue;
};

export type OrderBook = {
  run_id: number;
  instrument_id: number;
  last_price: DecimalValue;
  bids: TradingOrder[];
  asks: TradingOrder[];
};

export type ParticipantBalance = {
  asset_id: number;
  available: DecimalValue;
  reserved: DecimalValue;
};

export type RunParticipant = {
  id: number;
  sequence_number: number;
  participant_type: "background" | "test";
  balances: ParticipantBalance[];
};

export type SimulationResults = {
  run_id: number;
  status: SimulationRunStatus;
  error_message: string | null;
  current_step: number;
  total_steps: number;
  quote_asset_id: number;
  test_participant_id: number;
  initial_portfolio_value: DecimalValue;
  portfolio_value: DecimalValue;
  profit: DecimalValue;
  return_pct: DecimalValue | null;
  trade_count: number;
  test_trade_count: number;
  balances: ParticipantBalance[];
};

function errorMessage(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = payload.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((item) =>
          item && typeof item === "object" && "msg" in item
            ? String(item.msg)
            : "Некорректные данные",
        )
        .join(". ");
    }
  }

  return `Ошибка сервера (${status})`;
}

export async function apiRequest<T>(
  path: string,
  options: RequestInit = {},
  token?: string,
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body) headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const response = await fetch(path, { ...options, headers });
  const payload = await response.json().catch(() => null);

  if (!response.ok) {
    throw new Error(errorMessage(payload, response.status));
  }

  return payload as T;
}

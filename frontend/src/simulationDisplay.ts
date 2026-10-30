import type { SimulationRun } from "./api";

export function runStatusLabel(status: SimulationRun["status"]): string {
  return {
    running: "Выполняется",
    stopped: "Остановлен",
    completed: "Завершён",
    failed: "Ошибка",
  }[status];
}

// Format money without converting it to a floating-point number.
export function decimalLabel(value: string | null, maxDigits = 8): string {
  if (value === null) return "—";
  const scientific = /^(-?)(\d+)(?:\.(\d+))?[eE]([+-]?\d+)$/.exec(value);
  if (scientific) {
    const [, sign, integer, fraction = "", exponent] = scientific;
    const point = integer.length + Number(exponent);
    const digits = integer + fraction;
    if (Math.abs(point) > 1000) return value;
    value = sign + (point <= 0 ? `0.${"0".repeat(-point)}${digits}`
      : point >= digits.length ? digits + "0".repeat(point - digits.length)
      : `${digits.slice(0, point)}.${digits.slice(point)}`);
  }
  const match = /^(-?)(\d+)(?:\.(\d+))?$/.exec(value);
  if (!match) return value;
  const [, sign, whole, fraction = ""] = match;
  const decimals = fraction.slice(0, maxDigits).replace(/0+$/, "");
  if (/^0+$/.test(whole) && !decimals) return /[1-9]/.test(fraction) ? "≈0" : "0";
  return `${sign}${whole.replace(/\B(?=(\d{3})+(?!\d))/g, "\u00a0")}${decimals ? `,${decimals}` : ""}`;
}

// A delayed poll must not replace a newer run, progress or terminal status.
export function newerRun(current: SimulationRun | null | undefined, incoming: SimulationRun) {
  if (!current || incoming.id > current.id) return incoming;
  if (incoming.id < current.id || incoming.current_step < current.current_step) return current;
  if (current.status !== "running" && incoming.status === "running") return current;
  return incoming;
}

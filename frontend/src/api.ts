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

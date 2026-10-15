import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import "./App.css";
import {
  apiRequest,
  type TokenResponse,
  type User,
  type UserRole,
} from "./api";

const TOKEN_KEY = "exchange-simulator-token";

type AuthMode = "login" | "register";

function AuthScreen({
  notice,
  onAuthenticated,
}: {
  notice: string;
  onAuthenticated: (token: string) => void;
}) {
  const [mode, setMode] = useState<AuthMode>("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [passwordConfirmation, setPasswordConfirmation] = useState("");
  const [error, setError] = useState("");
  const [pending, setPending] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError("");

    if (mode === "register" && password !== passwordConfirmation) {
      setError("Пароли не совпадают");
      return;
    }

    setPending(true);
    try {
      if (mode === "register") {
        await apiRequest<User>("/api/auth/register", {
          method: "POST",
          body: JSON.stringify({ email, password }),
        });
      }

      const token = await apiRequest<TokenResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      });
      localStorage.setItem(TOKEN_KEY, token.access_token);
      onAuthenticated(token.access_token);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось выполнить запрос",
      );
    } finally {
      setPending(false);
    }
  }

  function changeMode(nextMode: AuthMode) {
    setMode(nextMode);
    setError("");
    setPassword("");
    setPasswordConfirmation("");
  }

  return (
    <div className="auth-layout">
      <section className="auth-intro">
        <span className="eyebrow">Exchange Simulator</span>
        <h1>Торговые эксперименты без финансового риска</h1>
        <p>
          Создавайте воспроизводимые конфигурации рынка и проверяйте стратегии
          на виртуальных активах.
        </p>
        <div className="feature-list" aria-label="Возможности системы">
          <span>Воспроизводимые сценарии</span>
          <span>Виртуальные активы</span>
          <span>Контроль доступа</span>
        </div>
      </section>

      <section className="auth-card" aria-labelledby="auth-title">
        <div className="auth-tabs" role="tablist" aria-label="Авторизация">
          <button
            className={mode === "login" ? "active" : ""}
            onClick={() => changeMode("login")}
            type="button"
          >
            Вход
          </button>
          <button
            className={mode === "register" ? "active" : ""}
            onClick={() => changeMode("register")}
            type="button"
          >
            Регистрация
          </button>
        </div>

        <div className="auth-heading">
          <h2 id="auth-title">
            {mode === "login" ? "С возвращением" : "Создать аккаунт"}
          </h2>
          <p>
            {mode === "login"
              ? "Введите данные своей учётной записи"
              : "После регистрации вход выполнится автоматически"}
          </p>
        </div>

        {notice && <div className="notice">{notice}</div>}

        <form onSubmit={submit}>
          <label>
            Email
            <input
              autoComplete="email"
              onChange={(event) => setEmail(event.target.value)}
              placeholder="user@example.com"
              required
              type="email"
              value={email}
            />
          </label>

          <label>
            Пароль
            <input
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={8}
              onChange={(event) => setPassword(event.target.value)}
              placeholder="Не менее 8 символов"
              required
              type="password"
              value={password}
            />
          </label>

          {mode === "register" && (
            <label>
              Повторите пароль
              <input
                autoComplete="new-password"
                minLength={8}
                onChange={(event) => setPasswordConfirmation(event.target.value)}
                required
                type="password"
                value={passwordConfirmation}
              />
            </label>
          )}

          {error && <div className="form-error">{error}</div>}

          <button className="primary-button" disabled={pending} type="submit">
            {pending
              ? "Подождите…"
              : mode === "login"
                ? "Войти"
                : "Зарегистрироваться"}
          </button>
        </form>
      </section>
    </div>
  );
}

function AdminPanel({ token, currentUser }: { token: string; currentUser: User }) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);

  useEffect(() => {
    let active = true;
    apiRequest<User[]>("/api/users", {}, token)
      .then((data) => {
        if (active) setUsers(data);
      })
      .catch((requestError) => {
        if (active) {
          setError(
            requestError instanceof Error
              ? requestError.message
              : "Не удалось загрузить пользователей",
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

  async function updateRole(user: User, role: UserRole) {
    setSavingId(user.id);
    setError("");
    try {
      const updated = await apiRequest<User>(
        `/api/users/${user.id}/role`,
        { method: "PUT", body: JSON.stringify({ role }) },
        token,
      );
      setUsers((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      );
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось изменить роль",
      );
    } finally {
      setSavingId(null);
    }
  }

  return (
    <section className="panel admin-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Администрирование</span>
          <h2>Пользователи и роли</h2>
        </div>
        <span className="count-badge">{users.length}</span>
      </div>

      {error && <div className="form-error">{error}</div>}
      {loading ? (
        <p className="muted">Загрузка пользователей…</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Пользователь</th>
                <th>Статус</th>
                <th>Роль</th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>
                    <strong>{user.email}</strong>
                    <span className="user-meta">
                      ID {user.id}
                      {user.id === currentUser.id ? " · текущий аккаунт" : ""}
                    </span>
                  </td>
                  <td>
                    <span className={`status-dot ${user.is_active ? "on" : ""}`} />
                    {user.is_active ? "Активен" : "Отключён"}
                  </td>
                  <td>
                    <select
                      aria-label={`Роль пользователя ${user.email}`}
                      disabled={savingId === user.id || user.id === currentUser.id}
                      onChange={(event) =>
                        updateRole(user, event.target.value as UserRole)
                      }
                      value={user.role}
                    >
                      <option value="user">Пользователь</option>
                      <option value="admin">Администратор</option>
                    </select>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="panel-note">
        Роль текущего аккаунта нельзя изменить из этого интерфейса.
      </p>
    </section>
  );
}

function Dashboard({ user, token, onLogout }: { user: User; token: string; onLogout: () => void }) {
  return (
    <div className="dashboard">
      <header className="topbar">
        <div className="brand-mark">ES</div>
        <div className="brand-copy">
          <strong>Exchange Simulator</strong>
          <span>Панель управления</span>
        </div>
        <div className="account-summary">
          <div>
            <strong>{user.email}</strong>
            <span>{user.role === "admin" ? "Администратор" : "Пользователь"}</span>
          </div>
          <button className="secondary-button" onClick={onLogout} type="button">
            Выйти
          </button>
        </div>
      </header>

      <main className="dashboard-content">
        <section className="welcome-block">
          <span className="eyebrow">Личный кабинет</span>
          <h1>Добро пожаловать</h1>
          <p>
            Авторизация настроена. Следующим шагом здесь появятся торговые
            инструменты и конфигурации экспериментов.
          </p>
        </section>

        <section className="panel profile-panel">
          <div>
            <span className="eyebrow">Учётная запись</span>
            <h2>{user.email}</h2>
          </div>
          <dl>
            <div>
              <dt>Роль</dt>
              <dd>{user.role === "admin" ? "Администратор" : "Пользователь"}</dd>
            </div>
            <div>
              <dt>Статус</dt>
              <dd>{user.is_active ? "Активен" : "Отключён"}</dd>
            </div>
            <div>
              <dt>Создан</dt>
              <dd>{new Date(user.created_at).toLocaleDateString("ru-RU")}</dd>
            </div>
          </dl>
        </section>

        {user.role === "admin" && <AdminPanel token={token} currentUser={user} />}
      </main>
    </div>
  );
}

export default function App() {
  const [token, setToken] = useState<string | null>(() =>
    localStorage.getItem(TOKEN_KEY),
  );
  const [user, setUser] = useState<User | null>(null);
  const [restoring, setRestoring] = useState(Boolean(token));
  const [notice, setNotice] = useState("");

  useEffect(() => {
    let active = true;
    if (!token) {
      return;
    }

    apiRequest<User>("/api/auth/me", {}, token)
      .then((currentUser) => {
        if (active) {
          setUser(currentUser);
          setNotice("");
        }
      })
      .catch(() => {
        if (active) {
          localStorage.removeItem(TOKEN_KEY);
          setToken(null);
          setUser(null);
          setNotice("Сессия завершена. Войдите снова.");
        }
      })
      .finally(() => {
        if (active) setRestoring(false);
      });

    return () => {
      active = false;
    };
  }, [token]);

  function logout() {
    localStorage.removeItem(TOKEN_KEY);
    setToken(null);
    setUser(null);
    setNotice("");
  }

  if (restoring) {
    return (
      <div className="loading-screen">
        <div className="spinner" />
        <p>Восстанавливаем сессию…</p>
      </div>
    );
  }

  if (!token || !user) {
    return (
      <AuthScreen
        notice={notice}
        onAuthenticated={(accessToken) => setToken(accessToken)}
      />
    );
  }

  return <Dashboard user={user} token={token} onLogout={logout} />;
}

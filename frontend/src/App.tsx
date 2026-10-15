import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import "./App.css";
import { AdminPanel } from "./AdminPanel";
import { MarketCatalog } from "./MarketCatalog";
import { SimulationsPanel } from "./SimulationsPanel";
import {
  apiRequest,
  type Asset,
  type Instrument,
  type TokenResponse,
  type User,
} from "./api";


const TOKEN_KEY = "exchange-simulator-token";

type AuthMode = "login" | "register";
type DashboardSection = "experiments" | "market" | "profile" | "admin";


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
  const [instruments, setInstruments] = useState<Instrument[]>([]);

  useEffect(() => {
    apiRequest<Instrument[]>("/api/instruments")
      .then((items) =>
        setInstruments(
          items.filter(
            (item) =>
              item.is_active && item.base_asset.is_active && item.quote_asset.is_active,
          ),
        ),
      )
      .catch(() => setInstruments([]));
  }, []);

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
        <div className="feature-list" aria-label="Доступные инструменты">
          {instruments.length > 0 ? (
            instruments.map((instrument) => (
              <span key={instrument.id}>
                {instrument.base_asset.symbol}/{instrument.quote_asset.symbol}
              </span>
            ))
          ) : (
            <span>Виртуальный рынок</span>
          )}
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


function Dashboard({
  user,
  token,
  onLogout,
}: {
  user: User;
  token: string;
  onLogout: () => void;
}) {
  const [section, setSection] = useState<DashboardSection>("experiments");
  const [assets, setAssets] = useState<Asset[]>([]);
  const [instruments, setInstruments] = useState<Instrument[]>([]);
  const [catalogError, setCatalogError] = useState("");

  const loadCatalog = useCallback(async () => {
    try {
      const [assetItems, instrumentItems] = await Promise.all([
        apiRequest<Asset[]>("/api/assets"),
        apiRequest<Instrument[]>("/api/instruments"),
      ]);
      setAssets(assetItems);
      setInstruments(instrumentItems);
      setCatalogError("");
    } catch (requestError) {
      setCatalogError(
        requestError instanceof Error
          ? requestError.message
          : "Не удалось загрузить справочник рынка",
      );
    }
  }, []);

  useEffect(() => {
    void loadCatalog();
  }, [loadCatalog]);

  return (
    <div className="dashboard">
      <header className="topbar">
        <div className="brand-mark">ES</div>
        <div className="brand-copy">
          <strong>Exchange Simulator</strong>
          <span>Панель управления</span>
        </div>
        <nav className="main-nav" aria-label="Разделы">
          <NavButton
            active={section === "experiments"}
            label="Эксперименты"
            onClick={() => setSection("experiments")}
          />
          <NavButton
            active={section === "market"}
            label="Инструменты"
            onClick={() => setSection("market")}
          />
          <NavButton
            active={section === "profile"}
            label="Профиль"
            onClick={() => setSection("profile")}
          />
          {user.role === "admin" && (
            <NavButton
              active={section === "admin"}
              label="Администрирование"
              onClick={() => setSection("admin")}
            />
          )}
        </nav>
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
        {catalogError && <div className="form-error">{catalogError}</div>}

        {section === "experiments" && (
          <SimulationsPanel instruments={instruments} token={token} />
        )}
        {section === "market" && <MarketCatalog instruments={instruments} />}
        {section === "profile" && <ProfilePanel user={user} />}
        {section === "admin" && user.role === "admin" && (
          <AdminPanel
            assets={assets}
            currentUser={user}
            instruments={instruments}
            onCatalogChanged={loadCatalog}
            token={token}
          />
        )}
      </main>
    </div>
  );
}


function NavButton({
  active,
  label,
  onClick,
}: {
  active: boolean;
  label: string;
  onClick: () => void;
}) {
  return (
    <button className={active ? "active" : ""} onClick={onClick} type="button">
      {label}
    </button>
  );
}


function ProfilePanel({ user }: { user: User }) {
  return (
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
      setRestoring(false);
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

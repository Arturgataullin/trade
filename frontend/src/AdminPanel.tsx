import { useEffect, useState } from "react";
import type { FormEvent } from "react";

import {
  apiRequest,
  type Asset,
  type Instrument,
  type User,
  type UserRole,
} from "./api";


type AdminPanelProps = {
  token: string;
  currentUser: User;
  assets: Asset[];
  instruments: Instrument[];
  onCatalogChanged: () => Promise<void>;
};


export function AdminPanel({
  token,
  currentUser,
  assets,
  instruments,
  onCatalogChanged,
}: AdminPanelProps) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);
  const [assetSymbol, setAssetSymbol] = useState("");
  const [assetName, setAssetName] = useState("");
  const [baseAssetId, setBaseAssetId] = useState("");
  const [quoteAssetId, setQuoteAssetId] = useState("");
  const [catalogPending, setCatalogPending] = useState(false);

  useEffect(() => {
    let active = true;
    apiRequest<User[]>("/api/users", {}, token)
      .then((data) => {
        if (active) setUsers(data);
      })
      .catch((requestError) => {
        if (active) setError(messageFrom(requestError));
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
      setError(messageFrom(requestError));
    } finally {
      setSavingId(null);
    }
  }

  async function addAsset(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCatalogPending(true);
    setError("");
    try {
      await apiRequest<Asset>(
        "/api/assets",
        {
          method: "POST",
          body: JSON.stringify({
            symbol: assetSymbol,
            name: assetName,
            is_active: true,
          }),
        },
        token,
      );
      setAssetSymbol("");
      setAssetName("");
      await onCatalogChanged();
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setCatalogPending(false);
    }
  }

  async function toggleAsset(asset: Asset) {
    setCatalogPending(true);
    setError("");
    try {
      await apiRequest<Asset>(
        `/api/assets/${asset.id}`,
        {
          method: "PUT",
          body: JSON.stringify({ ...asset, is_active: !asset.is_active }),
        },
        token,
      );
      await onCatalogChanged();
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setCatalogPending(false);
    }
  }

  async function addInstrument(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCatalogPending(true);
    setError("");
    try {
      await apiRequest<Instrument>(
        "/api/instruments",
        {
          method: "POST",
          body: JSON.stringify({
            base_asset_id: Number(baseAssetId),
            quote_asset_id: Number(quoteAssetId),
            is_active: true,
          }),
        },
        token,
      );
      setBaseAssetId("");
      setQuoteAssetId("");
      await onCatalogChanged();
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setCatalogPending(false);
    }
  }

  async function toggleInstrument(instrument: Instrument) {
    setCatalogPending(true);
    setError("");
    try {
      await apiRequest<Instrument>(
        `/api/instruments/${instrument.id}`,
        {
          method: "PUT",
          body: JSON.stringify({
            base_asset_id: instrument.base_asset_id,
            quote_asset_id: instrument.quote_asset_id,
            is_active: !instrument.is_active,
          }),
        },
        token,
      );
      await onCatalogChanged();
    } catch (requestError) {
      setError(messageFrom(requestError));
    } finally {
      setCatalogPending(false);
    }
  }

  return (
    <div className="admin-stack">
      {error && <div className="form-error">{error}</div>}

      <section className="panel admin-panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Администрирование</span>
            <h2>Пользователи и роли</h2>
          </div>
          <span className="count-badge">{users.length}</span>
        </div>

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
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Справочник</span>
            <h2>Виртуальные активы</h2>
          </div>
          <span className="count-badge">{assets.length}</span>
        </div>

        <form className="inline-form" onSubmit={addAsset}>
          <label>
            Символ
            <input
              maxLength={16}
              onChange={(event) => setAssetSymbol(event.target.value)}
              placeholder="BTC"
              required
              value={assetSymbol}
            />
          </label>
          <label>
            Название
            <input
              maxLength={128}
              onChange={(event) => setAssetName(event.target.value)}
              placeholder="Bitcoin"
              required
              value={assetName}
            />
          </label>
          <button className="primary-button" disabled={catalogPending} type="submit">
            Добавить актив
          </button>
        </form>

        <div className="chip-list">
          {assets.map((asset) => (
            <button
              className={`status-chip ${asset.is_active ? "enabled" : ""}`}
              disabled={catalogPending}
              key={asset.id}
              onClick={() => toggleAsset(asset)}
              type="button"
            >
              <strong>{asset.symbol}</strong> · {asset.name} · {asset.is_active ? "включён" : "отключён"}
            </button>
          ))}
        </div>
      </section>

      <section className="panel">
        <div className="panel-heading">
          <div>
            <span className="eyebrow">Справочник</span>
            <h2>Торговые инструменты</h2>
          </div>
          <span className="count-badge">{instruments.length}</span>
        </div>

        <form className="inline-form" onSubmit={addInstrument}>
          <label>
            Базовый актив
            <select
              onChange={(event) => setBaseAssetId(event.target.value)}
              required
              value={baseAssetId}
            >
              <option value="">Выберите</option>
              {assets.map((asset) => (
                <option key={asset.id} value={asset.id}>{asset.symbol}</option>
              ))}
            </select>
          </label>
          <label>
            Котируемый актив
            <select
              onChange={(event) => setQuoteAssetId(event.target.value)}
              required
              value={quoteAssetId}
            >
              <option value="">Выберите</option>
              {assets.map((asset) => (
                <option key={asset.id} value={asset.id}>{asset.symbol}</option>
              ))}
            </select>
          </label>
          <button className="primary-button" disabled={catalogPending} type="submit">
            Добавить инструмент
          </button>
        </form>

        <div className="chip-list">
          {instruments.map((instrument) => (
            <button
              className={`status-chip ${instrument.is_active ? "enabled" : ""}`}
              disabled={catalogPending}
              key={instrument.id}
              onClick={() => toggleInstrument(instrument)}
              type="button"
            >
              <strong>{instrument.base_asset.symbol}/{instrument.quote_asset.symbol}</strong>
              {instrument.is_active ? " · включён" : " · отключён"}
            </button>
          ))}
        </div>
        <p className="panel-note">Нажатие на элемент включает или отключает его.</p>
      </section>
    </div>
  );
}


function messageFrom(error: unknown): string {
  return error instanceof Error ? error.message : "Не удалось выполнить запрос";
}

import { useEffect, useState } from "react";

type ApiStatus = "loading" | "online" | "offline";

export default function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("loading");

  useEffect(() => {
    fetch("/health")
      .then((response) => {
        if (!response.ok) throw new Error();
        setApiStatus("online");
      })
      .catch(() => setApiStatus("offline"));
  }, []);

  const statusText = {
    loading: "Проверка подключения…",
    online: "Backend подключён",
    offline: "Backend недоступен",
  }[apiStatus];

  return (
    <main>
      <h1>Exchange Simulator</h1>
      <p>Система моделирования биржевой торговли</p>
      <p>Статус: {statusText}</p>
    </main>
  );
}
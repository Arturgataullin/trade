# Exchange Simulator

Web-система имитационного моделирования биржевой торговли
для тестирования торговых стратегий.

## Структура

- `backend` — серверная часть на FastAPI;
- `frontend` — клиентская часть на React и Vite;
- `compose.yaml` — локальный PostgreSQL;
- `backend/migrations` — миграции базы данных Alembic.

## Локальный запуск

### Требования

- Python 3;
- Node.js и npm;
- Docker с поддержкой Docker Compose.

Все команды ниже выполняются из корня проекта.

### 1. Создать `.env`

Скопируйте пример конфигурации:

```bash
cp .env.example .env
```

В PowerShell используйте:

```powershell
Copy-Item .env.example .env
```

При необходимости измените логин, пароль и другие значения в `.env`. Значения
`POSTGRES_DB`, `POSTGRES_USER` и `POSTGRES_PASSWORD` должны соответствовать строке
подключения `DATABASE_URL`. По умолчанию PostgreSQL доступен на порту `5433`.

### 2. Запустить PostgreSQL

```bash
docker compose up -d db
```

Проверить состояние контейнера можно командой:

```bash
docker compose ps
```

### 3. Создать Python-окружение и установить зависимости

Linux/macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r backend/requirements.txt
```

### 4. Применить миграции

С активированным виртуальным окружением выполните:

```bash
python -m alembic upgrade head
```

### 5. Установить зависимости frontend

```bash
cd frontend
npm install
cd ..
```

### 6. Одновременно запустить backend и frontend

Откройте два терминала в корне проекта. В первом активируйте `.venv` и запустите
backend:

```bash
python -m uvicorn backend.app.main:app --reload
```

Во втором запустите frontend:

```bash
npm --prefix frontend run dev
```

После запуска доступны:

- frontend: <http://localhost:5173>;
- backend: <http://localhost:8000>;
- проверка backend: <http://localhost:8000/health>;
- Swagger UI: <http://localhost:8000/docs>.

## Остановка PostgreSQL

Остановить контейнер, сохранив данные в Docker volume:

```bash
docker compose down
```

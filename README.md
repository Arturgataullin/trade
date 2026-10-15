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

Загрузить воспроизводимый демонстрационный справочник рынка с активами BTC, ETH,
USD и инструментами BTC/USD, ETH/USD:

```powershell
python -m backend.scripts.seed_market
```

Команду можно запускать повторно — дубликаты не создаются.

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

## Просмотр содержимого базы данных

PostgreSQL работает внутри контейнера `db`. Чтобы открыть интерактивную консоль
`psql`, выполните из корня проекта:

```powershell
docker compose exec db psql -U exchange_user -d exchange_simulator
```

Если значения `POSTGRES_USER` или `POSTGRES_DB` были изменены в `.env`, замените
`exchange_user` и `exchange_simulator` в команде на свои значения.

Основные команды внутри `psql`:

```sql
-- Показать таблицы базы данных
\dt

-- Показать структуру таблицы пользователей
\d users

-- Показать виртуальные активы
SELECT id, symbol, name, is_active FROM assets ORDER BY symbol;

-- Показать торговые инструменты
SELECT
    instruments.id,
    base.symbol || '/' || quote.symbol AS symbol,
    instruments.is_active
FROM instruments
JOIN assets AS base ON base.id = instruments.base_asset_id
JOIN assets AS quote ON quote.id = instruments.quote_asset_id
ORDER BY instruments.id;

-- Показать сохранённые эксперименты
SELECT id, owner_id, name, duration_steps, seed, updated_at
FROM simulations
ORDER BY id;

-- Показать пользователей без хэшей паролей
SELECT id, email, role, is_active, created_at
FROM users
ORDER BY id;

-- Показать применённую версию миграций Alembic
SELECT * FROM alembic_version;

-- Выйти из psql
\q
```

Отдельный запрос можно выполнить без входа в интерактивную консоль:

```powershell
docker compose exec db psql -U exchange_user -d exchange_simulator -c "SELECT id, email, role, is_active, created_at FROM users ORDER BY id;"
```

## Роли пользователей

После обновления кода примените новую миграцию:

```powershell
python -m alembic upgrade head
```

Новые пользователи получают роль `user`. Для назначения первого администратора
зарегистрируйте пользователя обычным способом, затем из корня проекта выполните
на сервере с доступом к базе данных:

```powershell
python -m backend.scripts.promote_admin admin@example.com
```

Подставьте email зарегистрированного пользователя. Дальше администратор может
менять роли через `PUT /api/users/{id}/role` с Bearer-токеном и телом
`{"role": "user"}` или `{"role": "admin"}`. Роль также возвращается в
`GET /api/auth/me`. Без действительного токена сервер отвечает `401`, а
пользователю без роли администратора возвращает `403`.

## Возможности первого этапа

После регистрации и входа пользователь может через web-интерфейс:

- просмотреть доступные торговые инструменты;
- создать конфигурацию эксперимента с одним или двумя инструментами;
- задать продолжительность, seed, начальные цены, балансы и объёмы заявок;
- добавить несколько фоновых профилей Random и Trend Following;
- отдельно настроить тестируемую стратегию;
- сохранить, повторно открыть и изменить свою конфигурацию.

Пользователь не может открыть конфигурацию другого пользователя. Администратору
доступны управление ролями, виртуальными активами и торговыми инструментами.

Основные маршруты конфигураций:

```text
GET  /api/assets
GET  /api/instruments
POST /api/simulations
GET  /api/simulations
GET  /api/simulations/{id}
PUT  /api/simulations/{id}
```

Создание и изменение активов и инструментов выполняется администратором через
`POST` и `PUT` маршруты `/api/assets` и `/api/instruments`.

## Остановка PostgreSQL

Остановить контейнер, сохранив данные в Docker volume:

```bash
docker compose down
```

## Основные HTTP-коды

- `201` — ресурс успешно создан;
- `401` — не удалось подтвердить личность: неправильный пароль, неактивный
  пользователь, отсутствующий или просроченный JWT;
- `403` — личность подтверждена, но не хватает прав;
- `404` — запрошенный ресурс не найден или не принадлежит пользователю;
- `409` — ресурс с таким уникальным значением уже существует;
- `422` — данные не прошли проверку.

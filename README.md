# Exchange Simulator

Web-система имитационного моделирования биржевой торговли
для тестирования торговых стратегий.

## Структура

- backend - серверная часть
- frontend - клиентская часть

## Запуск backend

pip install -r backend/requirements.txt

uvicorn backend.app.main:app --reload

## Проверка

GET http://localhost:8000/health
# StepByStepBot

См. также:
- [API бота](api.md)
- [Настройка пароля администратора](password.md)

## Установка

1. Установите зависимости:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
2. Скопируйте шаблон переменных окружения и заполните:
   ```bash
   cp .env.example .env
   ```
3. Подготовьте базу данных (пример для PostgreSQL):
   ```bash
   export DB_URL="postgresql+psycopg://user:pass@localhost:5432/stepbystep"
   ```

## Запуск

```bash
source .venv/bin/activate
python bot.py
```

`bot.py` теперь поднимает сразу:
- Telegram-бота (aiogram),
- Reload API (FastAPI),
- фоновые задачи (проверка платежей/инвайты),
- админку Streamlit (`admin.py`) как дочерний процесс.

## Структура проекта (после рефакторинга)

- `bot.py` — точка входа и оркестрация сервисов.
- `bot_modules/logger.py` — настройка логгера и `logger`.
- `bot_modules/db.py` — загрузка `.env` для DB, `engine`, SQLModel-модели.
- `bot_modules/promo.py` — загрузка/сохранение промокодов.
- `bot_modules/config.py` — `Settings` и `Script`.
- `bot_modules/handlers.py` — фильтры, FSM-состояния и хендлеры aiogram.
- `bot_modules/tasks.py` — фоновые задачи и прокси-сессия.
- `bot_modules/api.py` — FastAPI-ендпоинты для reload/promo.
- `bot_modules/bot_messages.py` — шаблоны лог-сообщений.

## Структура `.env`

Файл `.env` использует шаблон `.env.example` и должен содержать:

- `BOT_KEY` — токен Telegram-бота.
- `DB_URL` — строка подключения к БД.
- `ADMIN_PASSWORD` — пароль администратора (plaintext) **или**
- `ADMIN_PASSWORD_HASH` и `ADMIN_PASSWORD_SALT` — хэш/соль для пароля.
- `STORE_ID` — идентификатор магазина YooKassa.
- `YKASSA_API_KEY` — ключ API YooKassa.
- `BOT_LINK` — ссылка возврата YooKassa.
- `RELOAD_API_HOST` — хост reload API (по умолчанию `0.0.0.0`).
- `RELOAD_API_PORT` — порт reload API (по умолчанию `8000`).
- `RELOAD_API_URL` — URL для админки, чтобы дергать reload/promo API.
- `BOT_LOG_PATH` — путь к файлу логов (для админки).

## Основные принципы работы

- **Бот** работает на aiogram и хранит состояние пользователей в БД через SQLModel.
- **Платежи** создаются через YooKassa, сумма берётся из `settings.json`.
- **Сценарий** (steps) хранится в `script.json` и редактируется через админку.
- **Админка** (Streamlit) позволяет:
  - редактировать шаги,
  - менять настройки,
  - генерировать промокоды,
  - смотреть логи с фильтрами по уровню.
- **Reload API** (FastAPI внутри бота) получает запросы от админки и обновляет
  настройки/сценарий без рестарта.
- **Логи** ротируются ежедневно (`TimedRotatingFileHandler`).

Подробнее про HTTP-ендпоинты см. в [api.md](api.md).

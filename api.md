# Bot API

Бот поднимает небольшой HTTP API (FastAPI) для перезагрузки данных и генерации промокодов.

Базовый адрес задаётся переменными `RELOAD_API_HOST` и `RELOAD_API_PORT`.
В админке используется `RELOAD_API_URL`.

## POST /reload/settings

Перечитывает `settings.json` без перезапуска бота.

**Ответ**
```json
{"status": "ok"}
```

## POST /reload/script

Перечитывает `script.json` без перезапуска бота.

**Ответ**
```json
{"status": "ok"}
```

## POST /promo/generate

Генерирует новый промокод и сохраняет в `promo_codes.json`.

**Ответ**
```json
{"status": "ok", "code": "<generated_code>"}
```

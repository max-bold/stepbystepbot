# Настройка пароля администратора

Админский пароль используется в двух местах:

- `bot.py` — команда `/login` в Telegram-боте.
- `admin.py` — вход в Streamlit админку.

Поддерживаются два режима:

## 1. Простой пароль (plaintext)

В `.env` задайте:

```
ADMIN_PASSWORD=your_password_here
```

Этот вариант проще, но менее безопасен.

## 2. Хэшированный пароль (рекомендуется)

1. Сгенерируйте соль и хэш:

```bash
python - <<'PY'
import os
import hashlib
import secrets

password = "your_password_here"
salt = secrets.token_hex(16)
hash_value = hashlib.pbkdf2_hmac(
    "sha256",
    password.encode("utf-8"),
    salt.encode("utf-8"),
    120000,
).hex()

print("ADMIN_PASSWORD_SALT=", salt)
print("ADMIN_PASSWORD_HASH=", hash_value)
PY
```

2. Запишите значения в `.env`:

```
ADMIN_PASSWORD_SALT=...  # из вывода
ADMIN_PASSWORD_HASH=...  # из вывода
```

> При наличии `ADMIN_PASSWORD_HASH` и `ADMIN_PASSWORD_SALT`
> значение `ADMIN_PASSWORD` игнорируется.

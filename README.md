# stepbystepbot
Telegram bot for step-by-step instructions with a FastAPI backend and Streamlit admin panel.

## Services
- **backend**: FastAPI service that stores users and logs in the database, and serves `settings.json`/`script.json` via REST.
- **bot**: Telegram bot (aiogram) that talks to the backend over REST.
- **admin**: Streamlit admin panel that edits settings and scripts through the backend.

## Requirements
- Python 3.10+
- A database defined in `DB_URL` (SQLite, Postgres, etc.)

## Environment variables

| Variable | Purpose |
| --- | --- |
| `DB_URL` | Database URL for backend |
| `BOT_KEY` | Telegram bot token |
| `BACKEND_URL` | Backend base URL (default `http://127.0.0.1:8000`) |
| `ADMIN_PASSWORD` | Admin password for Streamlit (temporary until Telegram login) |
| `STORE_ID` | YooKassa store id |
| `YKASSA_API_KEY` | YooKassa API key |
| `BOT_LINK` | YooKassa return URL |
| `DATA_DIR` | Optional data directory for settings/script files |

## Data files
The backend expects default files:
- `default_settings.json`
- `test_script.json`

If `settings.json` or `script.json` are missing in the working directory (or `DATA_DIR`), the backend creates them from these defaults on startup.

## Local setup

### Ubuntu/macOS
```bash
./scripts/setup.sh
./scripts/run.sh
```

### Windows (PowerShell)
```powershell
.\scripts\setup.ps1
.\scripts\run.ps1
```

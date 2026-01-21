& .\.venv\Scripts\Activate.ps1

if (-not $env:BACKEND_URL) {
    $env:BACKEND_URL = "http://127.0.0.1:8000"
}

$backend = Start-Process -PassThru -NoNewWindow python -ArgumentList "-m", "uvicorn", "backend:app", "--host", "0.0.0.0", "--port", "8000"
$admin = Start-Process -PassThru -NoNewWindow streamlit -ArgumentList "run", "admin.py"
$bot = Start-Process -PassThru -NoNewWindow python -ArgumentList "bot.py"

Wait-Process -Id $backend.Id, $admin.Id, $bot.Id

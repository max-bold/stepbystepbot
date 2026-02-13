import secrets
from os import getenv
import uvicorn
from fastapi import FastAPI

from bot_modules import bot_messages as bms
from bot_modules.config import script, settings
from bot_modules.logger import logger
from bot_modules.promo import promo_codes, save_promo_codes

app = FastAPI()


@app.post("/reload/settings")
async def reload_settings() -> dict[str, str]:
    settings.reload()
    return {"status": "ok"}


@app.post("/reload/script")
async def reload_script() -> dict[str, str]:
    script.reload()
    return {"status": "ok"}


@app.post("/promo/generate")
async def generate_promo_code() -> dict[str, str]:
    promo_code = secrets.token_urlsafe(8)
    promo_codes.append(promo_code)
    save_promo_codes()
    logger.info(bms.promo_code_generated.format(code=promo_code))
    return {"status": "ok", "code": promo_code}


async def run_reload_api() -> None:
    host = getenv("RELOAD_API_HOST", "0.0.0.0")
    port = int(getenv("RELOAD_API_PORT", "8000"))
    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

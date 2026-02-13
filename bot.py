import asyncio
from aiogram import Bot
from sqlmodel import SQLModel

from bot_modules.api import run_reload_api
from bot_modules.handlers import dp
from os import getenv

from dotenv import load_dotenv

from bot_modules.db import engine
from bot_modules.logger import logger
from admin import start_admin_panel, stop_admin_panel
from bot_modules.tasks import SocksAiohttpSession, check_payments, update_next_steps

load_dotenv()
bot_key = getenv("BOT_KEY")
proxy_url = getenv("PROXY_URL")


async def main():
    if bot_key is None:
        raise ValueError("BOT_KEY environment variable not set")

    if proxy_url:
        tg_session = SocksAiohttpSession(proxy_url=proxy_url)
        bot = Bot(bot_key, tg_session)
    else:
        bot = Bot(bot_key)

    logger.info("Creating database tables")
    SQLModel.metadata.create_all(engine)
    logger.info("Starting reload API")
    asyncio.create_task(run_reload_api())
    logger.info("Starting payment checking task")
    asyncio.create_task(check_payments(bot))
    logger.info("Starting next step update task")
    asyncio.create_task(update_next_steps(bot))
    admin_process = await start_admin_panel()
    logger.info("Starting bot polling")

    try:
        await dp.start_polling(bot)
    finally:
        await bot.session.close()
        await stop_admin_panel(admin_process)

    logger.info("Bot has stopped")


if __name__ == "__main__":
    asyncio.run(main())

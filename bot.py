import asyncio
from os import getenv

from aiogram import Bot
from dotenv import load_dotenv
from sqlmodel import SQLModel

from admin import start_admin_panel, stop_admin_panel
from bot_modules.api import run_reload_api
from bot_modules.db import engine
from bot_modules.handlers import dp
from bot_modules.logger import logger
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
    reload_api_task = asyncio.create_task(run_reload_api(), name="reload_api")
    logger.info("Starting payment checking task")
    check_payments_task = asyncio.create_task(check_payments(bot), name="check_payments")
    logger.info("Starting next step update task")
    update_next_steps_task = asyncio.create_task(update_next_steps(bot), name="update_next_steps")

    background_tasks = [reload_api_task, check_payments_task, update_next_steps_task]

    admin_process = await start_admin_panel()
    logger.info("Starting bot polling")

    try:
        await dp.start_polling(bot)
    except asyncio.CancelledError:
        logger.info("Polling cancelled during shutdown")
    finally:
        for task in background_tasks:
            task.cancel()
        await asyncio.gather(*background_tasks, return_exceptions=True)
        await bot.session.close()
        await stop_admin_panel(admin_process)

    logger.info("Bot has stopped")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")

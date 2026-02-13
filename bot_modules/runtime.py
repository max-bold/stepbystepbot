from os import getenv
import json
import logging
from logging.handlers import TimedRotatingFileHandler

from dotenv import load_dotenv
from sqlmodel import create_engine
from aiogram import Dispatcher


log_handler = TimedRotatingFileHandler(
    "bot.log",
    when="midnight",
    interval=1,
    backupCount=7,
    encoding="utf-8",
)
log_handler.setFormatter(
    logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
)
logging.basicConfig(level=logging.INFO, handlers=[log_handler])
logger = logging.getLogger("bot")

load_dotenv()

db_url = getenv("DB_URL")
bot_key = getenv("BOT_KEY")
proxy_url = getenv("PROXY_URL")

if db_url is None:
    raise ValueError("DB_URL environment variable not set")
engine = create_engine(db_url)


try:
    promo_codes: list[str] = json.load(open("promo_codes.json", "r", encoding="utf-8"))
except FileNotFoundError:
    promo_codes: list[str] = []


def save_promo_codes() -> None:
    json.dump(promo_codes, open("promo_codes.json", "w", encoding="utf-8"))


dp = Dispatcher()

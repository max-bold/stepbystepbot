import logging
from logging.handlers import TimedRotatingFileHandler


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

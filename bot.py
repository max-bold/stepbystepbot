from math import log
from sqlmodel import SQLModel, create_engine, Field, Session, select
from sqlalchemy import BigInteger
from dotenv import load_dotenv
from os import getenv
import json
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    CallbackQuery,
)

import logging

from kassa import create_payment, get_payment_status

from time import time

import bot_messages as bms

logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class User(SQLModel, table=True):
    id: int = Field(primary_key=True, sa_type=BigInteger)
    current_step: int = Field(default=-1)
    payment_status: str = Field(default="")
    payment_key: str = Field(default="")
    payed: bool = Field(default=False)
    step_sent_time: float = Field(default=0.0)
    next_step_invite_sent: bool = Field(default=False)


load_dotenv()
db_url = getenv("DB_URL")
bot_key = getenv("BOT_KEY")
uploads_dir = getenv("UPLOADS_DIR")
script_path = getenv("SCRIPT_PATH")

if db_url is None:
    raise ValueError("DB_URL environment variable not set")

if script_path is None:
    raise ValueError("SCRIPT_PATH environment variable not set")

if bot_key is None:
    raise ValueError("BOT_KEY environment variable not set")

engine = create_engine(db_url)
script: dict = json.load(open(script_path, "r", encoding="utf-8"))
bot = Bot(token=bot_key)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_command_handler(message: Message):
    if message.from_user:
        logger.info(f"User {message.from_user.id} started the bot")
        with Session(engine) as session:
            user = session.get(User, message.from_user.id)
            if not user:
                user = User(id=message.from_user.id)
                user.payed = script.get("create_payed_users", False)
                session.add(user)
                session.commit()
                logger.info(f"Created new user with id {user.id}")
            else:
                logger.info(f"User {user.id} already exists")
            if not user.payed:
                payment_id, confirmation_url = create_payment()
                user.payment_key = payment_id
                user.payment_status = "pending"
                session.commit()
                logger.info(f"Created payment {payment_id} for user {user.id}")
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="Complete Payment", url=confirmation_url
                            )
                        ]
                    ]
                )
                await message.answer(
                    script.get("welcome_message", ""),
                    reply_markup=keyboard,
                )
                logger.info(f"Sent payment link to user {user.id}")
            else:
                await message.answer(
                    "У вас уже есть доступ к боту. Добро пожаловать обратно!"
                )
                logger.info(
                    f"User {user.id} has already paid, sent welcome back message"
                )
    else:
        logger.warning("Received /start command from unknown user")


@dp.callback_query(F.data == "get_step")
async def get_step_command_handler(callback_query: CallbackQuery):
    if callback_query.from_user:
        user_id = callback_query.from_user.id
        logger.info(f"User {user_id} requested next step")
        with Session(engine) as session:
            user = session.get(User, user_id)
            if not user:
                await bot.send_message(user_id, bms.not_registered[0])
                logger.info(bms.not_registered[1].format(id=user_id))
                return
            if not user.payed:
                await bot.send_message(user_id, bms.not_payed[0])
                logger.info(bms.not_payed[1].format(id=user_id))
                return
            if user.step_sent_time:
                await bot.send_message(user_id, bms.step_sent[0])
                logger.info(bms.step_sent[1].format(id=user_id))
                return
            if user.current_step >= len(script["steps"]):
                await bot.send_message(user_id, bms.script_completed[0])
                logger.info(bms.script_completed[1].format(id=user_id))
                return
            callback_query.answer()
            for payload in script["steps"][user.current_step]["content"]:
                payload: dict
                try:
                    if payload["type"] == "text":
                        await bot.send_message(user_id, payload["value"])
                    else:
                        
                        file = FSInputFile(uploads_dir + payload["file"])
                        caption = payload.get("caption", None)
                        if payload["type"] == "image":
                            await bot.send_photo(user_id, file, caption=caption)
                        if payload["type"] == "video":
                            await bot.send_video(user_id, file, caption=caption)
                        if payload["type"] == "audio":
                            await bot.send_audio(user_id, file, caption=caption)
                        if payload["type"] == "voice":
                            await bot.send_voice(user_id, file, caption=caption)
                        if payload["type"] == "video note":
                            await bot.send_video_note(user_id, file)
                        if payload["type"] == "document":
                            await bot.send_document(user_id, file, caption=caption)
                except Exception as e:
                    logger.error(
                        f"Failed to send {payload['type']} to user {user.id}: {e}"
                    )
            user.step_sent_time = time()
            user.next_step_invite_sent = False
            session.commit()
            logger.info(f"Sent step {user.current_step} to user {user.id}")


@dp.message()
async def default_message_handler(message: Message):
    id = message.from_user.id if message.from_user else "unknown"
    logger.info(bms.on_message[1].format(id=id, text=message.text))
    await message.answer(
        bms.on_message[0].format(
            support_contact=script.get("support_contact", "поддержке")
        )
    )


async def check_payments():
    while True:
        with Session(engine) as session:
            users = session.exec(select(User).where(User.payment_status == "pending")).all()  # type: ignore
            if users:
                for user in users:
                    logger.info(
                        f"Checking payment status for user {user.id} with payment key {user.payment_key}"
                    )
                    status = get_payment_status(user.payment_key)
                    if status == "succeeded":
                        user.payed = True
                        user.payment_status = "succeeded"
                        session.commit()
                        logger.info(f"User {user.id} has completed payment.")
                        try:
                            await bot.send_message(
                                chat_id=user.id,
                                text="Спасибо за ваш платеж! Теперь у вас есть полный доступ к боту.",
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to send payment confirmation to user {user.id}: {e}"
                            )
                    elif status == "canceled":
                        user.payment_status = "canceled"
                        session.commit()
                        logger.info(f"User {user.id} payment was canceled.")
                        try:
                            await bot.send_message(
                                chat_id=user.id,
                                text="Ваш платеж был отменен. Если вы хотите получить доступ к боту, пожалуйста, отправьте команду /start еще раз.",
                            )
                        except Exception as e:
                            logger.error(
                                f"Failed to send payment confirmation to user {user.id}: {e}"
                            )
                    await asyncio.sleep(1)  # avoid hammering the payment API
            else:
                await asyncio.sleep(1)


async def update_next_steps():
    while True:
        current_time = time()
        with Session(engine) as session:
            time_threshold = (
                current_time - script["next_step_delay"]["value"]
            )  # 24 hours ago
            users = session.exec(
                select(User).where(
                    User.payed == True,
                    User.current_step < len(script["steps"])-1,
                    User.step_sent_time <= time_threshold,
                    User.next_step_invite_sent == False,
                )
            ).all()  # type: ignore
            for user in users:
                user.current_step += 1
                user.step_sent_time = 0.0
                step = script["steps"][user.current_step]
                try:
                    kbd = InlineKeyboardMarkup(
                        inline_keyboard=[
                            [
                                InlineKeyboardButton(
                                    text=bms.next_step_button, callback_data="get_step"
                                )
                            ]
                        ]
                    )
                    await bot.send_message(
                        chat_id=user.id,
                        text=bms.step_invite[0].format(
                            title=step["title"],
                            description=step["description"],
                        ),
                        reply_markup=kbd,
                    )
                    logger.info(bms.step_invite[1].format(id=user.id))
                    user.next_step_invite_sent = True
                    session.commit()
                except Exception as e:
                    logger.error(bms.massage_failed.format(id=user.id, e=e))
                    session.rollback()
        await asyncio.sleep(1)


async def main():
    logger.info("Creating database tables")
    SQLModel.metadata.create_all(engine)
    logger.info("Starting payment checking task")
    asyncio.create_task(check_payments())
    logger.info("Starting next step update task")
    asyncio.create_task(update_next_steps())
    logger.info("Starting bot polling")
    await dp.start_polling(bot)
    logger.info("Bot has stopped")


if __name__ == "__main__":
    asyncio.run(main())

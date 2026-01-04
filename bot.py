from math import asin, log
from turtle import title
from typing import Any
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
from datetime import datetime

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
    upload_mode: bool = Field(default=False)


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
script: list[dict] = json.load(open(script_path, "r", encoding="utf-8"))
settings: dict[str, Any] = json.load(open("settings.json", "r", encoding="utf-8"))
bot = Bot(token=bot_key)
dp = Dispatcher()


@dp.message(CommandStart())
async def start_command_handler(message: Message):
    if message.from_user:
        logger.info(bms.on_start_command.format(id=message.from_user.id))
        with Session(engine) as session:
            user = session.get(User, message.from_user.id)
            if not user:
                user = User(id=message.from_user.id)
                user.payed = settings["create_paid_users"]
                session.add(user)
                session.commit()
                logger.info(bms.user_created.format(id=user.id))
            else:
                logger.info(bms.user_exists.format(id=user.id))
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
                                text=settings["messages"]["pay_button_text"],
                                url=confirmation_url,
                            )
                        ]
                    ]
                )
                await message.answer(
                    settings["messages"]["welcome_message"],
                    reply_markup=keyboard,
                )
                logger.info(bms.pay_link_sent.format(id=user.id))
            else:
                await message.answer(settings["messages"]["already_registered"])
                logger.info(bms.wlc_back.format(id=user.id))
    else:
        logger.warning(bms.no_user_id)


@dp.message(Command("upload"))
async def upload_command(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id:
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                user.upload_mode = not user.upload_mode
                session.commit()
                await message.answer(
                    bms.upload_mode.format(
                        state="enabled" if user.upload_mode else "disabled."
                    )
                )
            else:
                await message.answer(settings["messages"]["not_registered"])
                logger.info(bms.not_registered.format(id=user_id))


@dp.callback_query(F.data == "get_step")
async def get_step_command_handler(callback_query: CallbackQuery):
    if callback_query.from_user:
        user_id = callback_query.from_user.id
        logger.info(bms.next_request.format(id=user_id))
        with Session(engine) as session:
            user = session.get(User, user_id)
            if not user:
                await bot.send_message(user_id, settings["messages"]["not_registered"])
                logger.info(bms.not_registered.format(id=user_id))
                return
            if not user.payed:
                await bot.send_message(user_id, settings["messages"]["not_payed"])
                logger.info(bms.not_payed.format(id=user_id))
                return
            if user.step_sent_time:
                await bot.send_message(user_id, settings["messages"]["step_sent"])
                logger.info(bms.step_sent.format(id=user_id))
                return
            if user.current_step >= len(script):
                await bot.send_message(
                    user_id, settings["messages"]["script_completed"]
                )
                logger.info(bms.script_completed.format(id=user_id))
                return

            for content in script[user.current_step]["content"]:
                try:
                    if content["type"] == "text":
                        await bot.send_message(user_id, content["value"])
                    else:
                        file_id = content["file_id"]
                        if file_id:
                            caption = content["caption"]
                            if content["type"] == "photo":
                                await bot.send_photo(user_id, file_id, caption=caption, protect_content=True)
                            if content["type"] == "video":
                                await bot.send_video(user_id, file_id, caption=caption, protect_content=True)
                            if content["type"] == "audio":
                                await bot.send_audio(user_id, file_id, caption=caption, protect_content=True)
                            if content["type"] == "voice":
                                await bot.send_voice(user_id, file_id, caption=caption, protect_content=True)
                            if content["type"] == "video note":
                                await bot.send_video_note(user_id, file_id, protect_content=True)
                            if content["type"] == "document":
                                await bot.send_document(
                                    user_id, file_id, caption=caption
                                )
                except Exception as e:
                    logger.error(
                        bms.send_fail.format(type=content["type"], id=user_id, e=e)
                    )
            user.step_sent_time = time()
            user.next_step_invite_sent = False
            session.commit()
            await callback_query.answer()
            logger.info(
                bms.step_sent_success.format(step_number=user.current_step, id=user_id)
            )


@dp.message()
async def default_message_handler(message: Message):
    if message.text:
        id = message.from_user.id if message.from_user else "unknown"
        logger.info(bms.on_message.format(id=id, text=message.text))
        await message.answer(settings["messages"]["on_message"])
    else:
        user_id = message.from_user.id if message.from_user else None
        if user_id:
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user and user.upload_mode:
                    if message.photo:
                        texts = []
                        for size in message.photo:
                            texts.append(
                                f"Size: {size.width}x{size.height}, {size.file_size/1024/1024 if size.file_size else 0:.2f} MB\n\n{size.file_id}"
                            )
                        await message.reply("\n\n".join(texts))
                    if message.video:
                        await message.reply(message.video.file_id)
                    if message.video_note:
                        await message.reply(message.video_note.file_id)
                    if message.document:
                        await message.reply(message.document.file_id)
                    if message.audio:
                        await message.reply(message.audio.file_id)
                    if message.voice:
                        await message.reply(message.voice.file_id)


async def check_payments():
    while True:
        with Session(engine) as session:
            users = session.exec(
                select(User).where(
                    User.payment_status == "pending",
                    User.payed == False,
                )
            ).all()
            if users:
                for user in users:
                    logger.info(bms.check_payment.format(id=user.id))
                    status = get_payment_status(user.payment_key)
                    if status == "succeeded":
                        user.payed = True
                        user.payment_status = "succeeded"
                        session.commit()
                        logger.info(bms.payment_confirmed.format(id=user.id))
                        await bot.send_message(
                            chat_id=user.id,
                            text=settings["messages"]["payment_successful"],
                        )
                    elif status == "canceled":
                        user.payment_status = "canceled"
                        session.commit()
                        logger.info(bms.payment_canceled.format(id=user.id))
                        await bot.send_message(
                            chat_id=user.id,
                            text=settings["messages"]["payment_canceled"],
                        )
                    await asyncio.sleep(1)  # avoid hammering the payment API
            else:
                await asyncio.sleep(1)


async def update_next_steps():
    while True:
        current_time = time()
        next_step_delay = settings["next_step_delay"]
        if next_step_delay["type"] == "Period":
            time_threshold = current_time - next_step_delay["value"]
        elif next_step_delay["type"] == "Fixed time":
            start_of_day = (
                datetime.fromtimestamp(current_time)
                .replace(hour=0, minute=0, second=0, microsecond=0)
                .timestamp()
            )
            time_threshold = start_of_day + next_step_delay["value"]
        else:
            raise ValueError("Invalid next_step_delay type in settings")

        with Session(engine) as session:

            users = session.exec(
                select(User).where(
                    User.payed == True,
                    User.current_step < len(script),
                    User.step_sent_time < time_threshold,
                    User.next_step_invite_sent == False,
                )
            ).all()  # type: ignore

            for user in users:
                user.current_step += 1
                user.step_sent_time = 0.0
                if user.current_step < len(script):
                    step = script[user.current_step]
                    try:
                        kbd = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text=settings["messages"]["next_step_button"],
                                        callback_data="get_step",
                                    )
                                ]
                            ]
                        )
                        await bot.send_message(
                            chat_id=user.id,
                            text=settings["messages"]["step_invite"].format(
                                title=step["title"],
                                description=step["description"],
                                step_number=user.current_step+1,
                            ),
                            reply_markup=kbd,
                        )
                        logger.info(bms.step_invite.format(id=user.id))
                        user.next_step_invite_sent = True
                        session.commit()
                    except Exception as e:
                        logger.error(bms.message_failed.format(id=user.id, e=e))
                        session.rollback()
                else:
                    await bot.send_message(
                        chat_id=user.id,
                        text=settings["messages"]["script_completed"],
                    )
                    logger.info(bms.script_completed.format(id=user.id))
                    session.commit()
        await asyncio.sleep(1)


async def reload_settings():
    while True:
        global settings
        global script
        settings = json.load(open("settings.json", "r", encoding="utf-8"))
        script = json.load(open("script.json", "r", encoding="utf-8"))
        logger.info("Settings reloaded")
        await asyncio.sleep(10)  # reload every 10 seconds


async def main():
    logger.info("Creating database tables")
    SQLModel.metadata.create_all(engine)
    logger.info("Starting payment checking task")
    asyncio.create_task(check_payments())
    logger.info("Starting next step update task")
    asyncio.create_task(update_next_steps())
    logger.info("Starting settings reload task")
    asyncio.create_task(reload_settings())
    logger.info("Starting bot polling")
    await dp.start_polling(bot)
    logger.info("Bot has stopped")


if __name__ == "__main__":
    asyncio.run(main())

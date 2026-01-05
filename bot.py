from math import asin, log
from operator import is_, le
from re import U
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

import bot_messages as bms
from datetime import datetime, timezone, timedelta, time

logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


class User(SQLModel, table=True):
    id: int = Field(primary_key=True, sa_type=BigInteger)
    current_step: int = Field(default=0)
    payment_status: str = Field(default="")
    payment_key: str = Field(default="")
    payed: bool = Field(default=False)
    step_sent_time: float = Field(default=0.0)
    next_step_invite_sent: bool = Field(default=False)
    upload_mode: bool = Field(default=False)
    is_admin: bool = Field(default=False)


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


def now() -> float:
    """
    Get the current time in UTC+3 timezone as a timestamp.

    Returns:
        float: Current time in UTC+3 as a Unix timestamp.
    """
    utc_plus_3 = timezone(timedelta(hours=3))
    return datetime.now(utc_plus_3).timestamp()


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


@dp.message(Command("login"))
async def login_command_handler(message: Message):
    if message.from_user and message.text:
        user_id = message.from_user.id
        key = message.text.split(" ")[1]
        if key == getenv("ADMIN_PASSWORD"):
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user:
                    user.payed = True
                    user.is_admin = True
                    session.commit()
                    await message.answer(settings["messages"]["login_successful"])
                    logger.info(bms.login_successful.format(admin_id=user_id))
                else:
                    await message.answer(settings["messages"]["not_registered"])
                    logger.info(bms.not_registered.format(id=user_id))
        else:
            await message.answer(settings["messages"]["not_admin"])
            logger.info(bms.invalid_login.format(admin_id=user_id))


@dp.message(Command("logout"))
async def logout_command(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id:
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                user.is_admin = False
                session.commit()
                await message.answer("You have been logged out from admin mode.")
                logger.info(bms.admin_logout.format(admin_id=user_id))
            else:
                await message.answer(settings["messages"]["not_registered"])
                logger.info(bms.not_registered.format(id=user_id))


@dp.message(Command("get_step"))
async def get_step_message_handler(message: Message):
    if message.from_user:
        user_id = message.from_user.id
        with Session(engine) as session:
            user = session.get(User, user_id)
            if not user:
                await message.answer(settings["messages"]["not_registered"])
                logger.info(bms.not_registered.format(id=user_id))
            else:
                if user.is_admin:
                    row_count = len(script) // 3 + (1 if len(script) % 3 != 0 else 0)
                    step_buttons = []
                    row = []
                    for i in range(row_count):
                        for j in range(3):
                            step_index = i * 3 + j
                            if step_index < len(script):
                                row.append(
                                    InlineKeyboardButton(
                                        text=f"{step_index+1}. {script[step_index]['title']}",
                                        callback_data=f"admin_get_step={step_index}",
                                    )
                                )
                            else:
                                # Add empty button to fill the row
                                row.append(
                                    InlineKeyboardButton(
                                        text=" ", callback_data="empty"
                                    )
                                )
                        step_buttons.append(row)
                        row = []
                    keyboard = InlineKeyboardMarkup(inline_keyboard=step_buttons)
                    await message.answer("Select a step:", reply_markup=keyboard)
                else:
                    await message.answer(settings["messages"]["not_admin"])
                    logger.info(bms.get_step_not_admin.format(id=user_id))


@dp.message(Command("reset"))
async def reset_command_handler(message: Message):
    if message.from_user:
        user_id = message.from_user.id
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                user.current_step = 0
                user.step_sent_time = 0.0
                user.next_step_invite_sent = False
                session.commit()
                await message.answer(settings["messages"]["progress_reset"])
                logger.info(bms.progress_reset.format(id=user_id))
            else:
                await message.answer(settings["messages"]["not_registered"])
                logger.info(bms.not_registered.format(id=user_id))


# /delete_me command to delete user data from database
@dp.message(Command("delete_me"))
async def delete_me_command_handler(message: Message):
    if message.from_user:
        user_id = message.from_user.id
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                session.delete(user)
                session.commit()
                await message.answer("Your data has been deleted from the database.")
                logger.info(f"User {user_id} data deleted from database.")
            else:
                await message.answer(settings["messages"]["not_registered"])
                logger.info(bms.not_registered.format(id=user_id))


async def send_step_content(user_id: int, step_number: int) -> bool:
    errors = False
    for content in script[step_number]["content"]:
        try:
            if content["type"] == "text":
                await bot.send_message(user_id, content["value"], protect_content=True)
            else:
                file_id = content["file_id"]
                if file_id:
                    caption = content["caption"]
                    if content["type"] == "photo":
                        await bot.send_photo(
                            user_id, file_id, caption=caption, protect_content=True
                        )
                    if content["type"] == "video":
                        await bot.send_video(
                            user_id, file_id, caption=caption, protect_content=True
                        )
                    if content["type"] == "audio":
                        await bot.send_audio(
                            user_id, file_id, caption=caption, protect_content=True
                        )
                    if content["type"] == "voice":
                        await bot.send_voice(
                            user_id, file_id, caption=caption, protect_content=True
                        )
                    if content["type"] == "video note":
                        await bot.send_video_note(
                            user_id, file_id, protect_content=True
                        )
                    if content["type"] == "document":
                        await bot.send_document(user_id, file_id, caption=caption)
        except Exception as e:
            logger.error(bms.send_fail.format(type=content["type"], id=user_id, e=e))
            errors = True
    return not errors


@dp.callback_query(F.data.startswith("admin_get_step="))
async def admin_get_step_handler(callback_query: CallbackQuery):
    if callback_query.from_user and callback_query.data:
        user_id = callback_query.from_user.id
        step_number = int(callback_query.data.split("=")[1])
        logger.info(
            bms.get_step_menu_request.format(
                admin_id=user_id,
                step_number=step_number,
            )
        )
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user and user.is_admin:
                await send_step_content(user_id, step_number)
                await callback_query.answer()
                logger.info(
                    bms.sent_step_to_admin.format(
                        admin_id=user_id, step_number=step_number
                    )
                )
            else:
                await callback_query.answer(bms.not_authorized, show_alert=True)
    else:
        await callback_query.answer(bms.not_authorized, show_alert=True)


@dp.callback_query(F.data == "empty")
async def empty_button_handler(callback_query: CallbackQuery):
    await callback_query.answer()


@dp.callback_query(F.data == "get_step")
async def get_step_command_handler(callback_query: CallbackQuery):
    if callback_query.from_user:
        user_id = callback_query.from_user.id
        logger.info(bms.next_request.format(id=user_id))
        with Session(engine) as session:
            user = session.get(User, user_id)
            if not user:
                await callback_query.answer(settings["messages"]["not_registered"])
                logger.info(bms.not_registered.format(id=user_id))
            elif not user.payed:
                await callback_query.answer(settings["messages"]["not_payed"])
                logger.info(bms.not_payed.format(id=user_id))
                return
            elif user.step_sent_time:
                await callback_query.answer(settings["messages"]["step_sent"])
                logger.info(bms.step_sent.format(id=user_id))
                await callback_query.answer()
                return
            elif user.current_step >= len(script):
                await bot.send_message(
                    user_id, settings["messages"]["script_completed"]
                )
                logger.info(bms.script_completed.format(id=user_id))
                return
            else:
                if await send_step_content(user_id, user.current_step):
                    user.step_sent_time = now()
                    user.next_step_invite_sent = False
                    user.current_step += 1
                    session.commit()
                    if user.current_step >= len(script):
                        await bot.send_message(
                            user_id, settings["messages"]["script_completed"]
                        )
                        logger.info(bms.script_completed.format(id=user_id))
                    else:
                        value: int = settings["next_step_delay"]["value"]
                        if settings["next_step_delay"]["type"] == "Fixed time":
                            hh = value // 3600
                            mm = (value % 3600) // 60
                            time_str = f"{hh:02}:{mm:02} МСК"
                        elif settings["next_step_delay"]["type"] == "Period":
                            td = timedelta(seconds=value)
                            dt = datetime.fromtimestamp(user.step_sent_time) + td
                            time_str = dt.strftime("%H:%M") + " МСК"
                        else:
                            raise ValueError("Invalid next_step_delay type")
                        await bot.send_message(
                            user_id,
                            settings["messages"]["next_step_timeout"].format(
                                time=time_str
                            ),
                        )
                    await callback_query.answer()
                    logger.info(
                        bms.step_sent_success.format(
                            step_number=user.current_step, id=user_id
                        )
                    )
                else:
                    await callback_query.answer(
                        settings["messages"]["step_send_error"].format(
                            step_number=user.current_step,
                            id=user_id,
                        ),
                        show_alert=True,
                    )
                    logger.error(
                        bms.step_send_error.format(
                            step_number=user.current_step,
                            id=user_id,
                        )
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
                        await message.reply(message.photo[-1].file_id)
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


NEXT_STEP_KBD = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(
                text=settings["messages"]["next_step_button"],
                callback_data="get_step",
            )
        ]
    ]
)


async def send_invite(user: User) -> bool:
    step = script[user.current_step]
    try:
        await bot.send_message(
            chat_id=user.id,
            text=settings["messages"]["step_invite"].format(
                title=step["title"],
                description=step["description"],
                step_number=user.current_step + 1,
            ),
            reply_markup=NEXT_STEP_KBD,
        )
        logger.info(bms.step_invite.format(id=user.id))
        return True
    except Exception as e:
        logger.error(bms.message_failed.format(id=user.id, e=e))
        return False


async def send_invites(time_threshold: float):
    with Session(engine) as session:
        users = session.exec(
            select(User).where(
                User.payed == True,
                User.current_step < len(script),
                User.step_sent_time < time_threshold,
                User.next_step_invite_sent == False,
            )
        ).all()
        for user in users:
            if await send_invite(user):
                user.next_step_invite_sent = True
                user.step_sent_time = 0.0
                session.commit()


async def invite_zero_steppers():
    with Session(engine) as session:
        users = session.exec(
            select(User).where(
                User.payed == True,
                User.current_step == 0,
                User.next_step_invite_sent == False,
            )
        ).all()
        for user in users:
            if await send_invite(user):
                user.next_step_invite_sent = True
                user.step_sent_time = 0.0
                session.commit()


async def invite_admins():
    with Session(engine) as session:
        users = session.exec(
            select(User).where(
                User.is_admin == True,
                User.current_step < len(script),
                User.next_step_invite_sent == False,
            )
        ).all()
        for user in users:
            if await send_invite(user):
                user.next_step_invite_sent = True
                user.step_sent_time = 0.0
                session.commit()


async def update_next_steps():
    while True:
        next_step_delay = settings["next_step_delay"]
        if next_step_delay["type"] == "Period":
            time_threshold = now() - next_step_delay["value"]
            await send_invites(time_threshold)
        if next_step_delay["type"] == "Fixed time":
            utc_plus_3 = timezone(timedelta(hours=3))
            now_dt = datetime.now(utc_plus_3)
            start_of_day = now_dt.replace(
                hour=0, minute=0, second=0, microsecond=0
            ).timestamp()
            time_threshold = start_of_day + next_step_delay["value"]
            if now() > time_threshold:
                await send_invites(time_threshold)
            else:
                await invite_zero_steppers()
        await invite_admins()
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

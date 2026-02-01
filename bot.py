from argparse import Action
from ast import In
from operator import call
import os
from typing import Any, Generator, Literal
from aiogram.fsm import state
from alembic import context
from sqlmodel import SQLModel, create_engine, Field, Session, select
from sqlalchemy import BigInteger, exc
from dotenv import load_dotenv
from os import getenv
import json
import asyncio
import shutil
import secrets

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    CallbackQuery,
    ForceReply,
)

import logging

from streamlit import user
from kassa import create_payment, get_payment_status

import bot_messages as bms
from datetime import datetime, timezone, timedelta, time

from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.filters import Filter

from contextlib import contextmanager

from time import monotonic


class AdminLogin(StatesGroup):
    waiting_password = State()


class PromoCodeEntry(StatesGroup):
    waiting_promo_code = State()


class DeleteAccount(StatesGroup):
    waiting_confirmation = State()


logging.basicConfig(
    filename="bot.log",
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("bot")


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

if db_url is None:
    raise ValueError("DB_URL environment variable not set")

if bot_key is None:
    raise ValueError("BOT_KEY environment variable not set")

engine = create_engine(db_url)

# try:
#     script: list[dict] = json.load(open("script.json", "r", encoding="utf-8"))
# except FileNotFoundError:
#     shutil.copy("test_script.json", "script.json")
#     logger.info("script.json not found, copied test_script.json to script.json")
#     script: list[dict] = json.load(open("script.json", "r", encoding="utf-8"))

# try:
#     settings: dict[str, Any] = json.load(open("settings.json", "r", encoding="utf-8"))
# except FileNotFoundError:
#     shutil.copy("default_settings.json", "settings.json")
#     settings: dict[str, Any] = json.load(open("settings.json", "r", encoding="utf-8"))
#     logger.info(
#         "settings.json not found, copied default_settings.json to settings.json"
#     )

try:
    promo_codes: list[str] = json.load(open("promo_codes.json", "r", encoding="utf-8"))
except FileNotFoundError:
    promo_codes: list[str] = []


bot = Bot(token=bot_key)
dp = Dispatcher()


class Settings:
    def __init__(self) -> None:
        self.settings = self._load()
        self.reload_time = monotonic()

    def _dump(self) -> None:
        json.dump(self.settings, open("settings.json", "w", encoding="utf-8"))

    def _load(self) -> dict[str, Any]:
        try:
            return json.load(open("settings.json", "r", encoding="utf-8"))
        except FileNotFoundError:
            logger.warning(
                "settings.json not found, copied default_settings.json to settings.json"
            )
            settings =  json.load(open("default_settings.json", "r", encoding="utf-8"))
            json.dump(settings, open("settings.json", "w", encoding="utf-8"))
            return settings
        
    def _reload(self) -> None:
        if self.reload_time + 10 < monotonic():
            self.settings = self._load()
            self.reload_time = monotonic()

    @property
    def create_paid_users(self) -> bool:
        self._reload()
        if "create_paid_users" not in self.settings:
            self.settings["create_paid_users"] = False
            self._dump()
        return self.settings["create_paid_users"]

    class NSD():
        def __init__(self,data:dict[str,Any]) -> None:
            self.type:Literal["Fixed time", "Period"] = data["type"]
            self.value:int = data["value"]
    @property
    def next_step_delay(self) -> NSD:
        self._reload()
        if "next_step_delay" not in self.settings:
            self.settings["next_step_delay"] = {"type": "Period", "value": 300}
            self._dump()
        return self.NSD(self.settings["next_step_delay"])

    def messages(self, key: str) -> str:
        self._reload()
        if "messages" not in self.settings:
            self.settings["messages"] = {}
            self._dump()
        if key not in self.settings["messages"]:
            self.settings["messages"][key] = f"Empty {key} message"
            self._dump()
        return self.settings["messages"][key]
    
settings = Settings()

class Script():
    def __init__(self) -> None:
        self.script = self._load()
        self.reload_time = monotonic()
        pass

    def _load(self) -> list[dict]:
        try:
            return json.load(open("script.json", "r", encoding="utf-8"))
        except FileNotFoundError:
            script = json.load(open("test_script.json", "r", encoding="utf-8"))
            json.dump(script, open("script.json","w", encoding="utf-8"))
            logger.info("script.json not found, copied test_script.json to script.json")
            return script

    def _reload(self):
        if self.reload_time + 10 < monotonic():
            self.settings = self._load()
            self.reload_time = monotonic()

    def __getitem__(self, n):
        self._reload()
        return self.script[n]
    
    def __len__(self):
        return len(self.script)
    
script = Script()


class UploadModeFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id if message.from_user else None
        if user_id:
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user and user.upload_mode:
                    return True
        return False


class AdminFilter(Filter):
    async def __call__(self, message: Message) -> bool:
        user_id = message.from_user.id if message.from_user else None
        if user_id:
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user and user.is_admin:
                    return True
        return False


class UserRegisteredFilter(Filter):
    async def __call__(self, message: Message) -> bool | dict[str, Any]:
        user_id = message.from_user.id if message.from_user else None
        if user_id:
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user:
                    return True
        return False


@contextmanager
def get_user(user_id: int) -> Generator[User, None, None]:
    with Session(engine) as session:
        user = session.get(User, user_id)
        if not user:
            user = User(id=user_id)
            user.payed = settings.create_paid_users
            session.add(user)
            logger.info(f"Created user with id={user.id}")
        try:
            yield user
            session.commit()
        except:
            session.rollback()
            raise


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
                user.payed = settings.create_paid_users
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
                                text=settings.messages("pay_button_text"),
                                url=confirmation_url,
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="Ввести промокод",
                                callback_data="enter_promo_code",
                            )
                        ],
                    ]
                )
                await message.answer(
                    settings.messages("welcome_message"),
                    reply_markup=keyboard,
                )
                logger.info(bms.pay_link_sent.format(id=user.id))
            else:
                await message.answer(settings.messages("already_registered"))
                logger.info(bms.wlc_back.format(id=user.id))
    else:
        logger.warning(bms.no_user_id)


# Handle `enter_promo_code` callback query
@dp.callback_query(F.data == "enter_promo_code")
async def enter_promo_code_handler(callback_query: CallbackQuery, state: FSMContext):
    if callback_query.from_user:
        if await state.get_value("promo_attempts", 0) < 3:
            user_id = callback_query.from_user.id
            await bot.send_message(
                user_id,
                "Пожалуйста, введите промокод:",
                reply_markup=ForceReply(input_field_placeholder="Промокод"),
            )
            await state.set_state(PromoCodeEntry.waiting_promo_code)
        else:
            await bot.send_message(
                callback_query.from_user.id,
                "Превышено максимальное количество попыток ввода промокода. Пожалуйста, свяжитесь с администратором.",
            )
    await callback_query.answer()


# Handle promo code entry
@dp.message(PromoCodeEntry.waiting_promo_code)
async def promo_code_entry_handler(message: Message, state: FSMContext):
    attempts = await state.get_value("promo_attempts", 0)
    if attempts < 3:
        if message.from_user and message.text:
            user_id = message.from_user.id
            entered_code = message.text.strip()
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user:
                    if entered_code in promo_codes:
                        user.payed = True
                        session.commit()
                        promo_codes.remove(entered_code)
                        json.dump(
                            promo_codes, open("promo_codes.json", "w", encoding="utf-8")
                        )
                        await message.answer(
                            "Промокод принят. Теперь у вас есть доступ к курсу!"
                        )
                        logger.info(
                            f"User {user_id} used promo code {entered_code} and is now registered."
                        )
                        await state.set_state(None)
                        await state.update_data(promo_attempts=0)
                    else:
                        attempts += 1
                        await state.update_data(promo_attempts=attempts)
                        if attempts == 3:
                            await message.answer(
                                "Превышено максимальное количество попыток ввода промокода."
                            )
                            await state.set_state(None)
                        else:
                            await message.answer(
                                "Промокод неверный. Попробуйте снова:",
                                reply_markup=ForceReply(
                                    input_field_placeholder="Промокод"
                                ),
                            )
                        logger.info(
                            f"User {user_id} entered invalid promo code {entered_code}."
                        )
                else:
                    await message.answer(settings.messages("not_registered"))
                    logger.info(
                        bms.not_registered.format(id=user_id, action="enter promo code")
                    )


@dp.message(Command("upload"), AdminFilter())
async def upload_command(message: Message):
    if message.from_user:
        with Session(engine) as session:
            user = session.get(User, message.from_user.id)
            if user:
                user.upload_mode = not user.upload_mode
                session.commit()
                await message.answer(
                    bms.upload_mode.format(
                        state="enabled" if user.upload_mode else "disabled."
                    )
                )
                logger.info(f"Upload mode for user {user.id} set to {user.upload_mode}")


# Message handler in upload mode
@dp.message(UploadModeFilter())
async def upload_mode_handler(message: Message):
    logger.info(f"Received message in upload mode")
    if message.photo:
        await message.reply(message.photo[-1].file_id)
    elif message.video:
        await message.reply(message.video.file_id)
    elif message.video_note:
        await message.reply(message.video_note.file_id)
    elif message.document:
        await message.reply(message.document.file_id)
    elif message.audio:
        await message.reply(message.audio.file_id)
    elif message.voice:
        await message.reply(message.voice.file_id)
    else:
        await message.answer(
            "Unsupported message type. Please send media files (photo, video, document, etc.) to get their file IDs. Use /upload to exit upload mode."
        )


@dp.message(Command("login"), ~AdminFilter())
async def login_command_handler(message: Message, state: FSMContext):
    if await state.get_value("login_attempts", 0) < 3:
        await message.answer(
            "Please enter the admin password:",
            reply_markup=ForceReply(input_field_placeholder="password"),
        )
        await state.set_state(AdminLogin.waiting_password)
    else:
        await message.answer(
            "Too many login attempts. Please contact the administrator."
        )
    if message.from_user:
        logger.info(bms.login_attempt.format(admin_id=message.from_user.id))


@dp.message(AdminLogin.waiting_password)
async def admin_password_handler(message: Message, state: FSMContext):
    attempts = await state.get_value("login_attempts", 0)
    if attempts < 3:
        if message.from_user and message.text:
            user_id = message.from_user.id
            entered_password = message.text.strip()
            if entered_password == getenv("ADMIN_PASSWORD"):
                with Session(engine) as session:
                    user = session.get(User, user_id)
                    if not user:
                        user = User(id=user_id, payed=True, is_admin=True)
                        session.add(user)
                        logger.info(bms.user_created.format(id=user_id))
                    user.payed = True
                    user.is_admin = True
                    session.commit()
                    await message.answer(
                        "Теперь у вас есть права администратора.\n\nВам доступны следующие команды:\n/upload - для загрузки файлов\n/logout - для выхода из режима администратора\n/get_step - для выбора и получения шага.\n/delete_me - для удаления своего id из БД\n/reset - для возврата к первому шагу\n/gen_promo - для генерации промокода"
                    )
                    logger.info(bms.login_successful.format(admin_id=user_id))
                await state.set_state(None)
                await state.update_data(login_attempts=0)
            else:
                attempts += 1
                await state.update_data(login_attempts=attempts)
                if attempts == 3:
                    await message.answer(
                        "Too many login attempts. Please contact the administrator."
                    )
                    await state.set_state(None)
                else:
                    await message.answer(
                        "Wrong password. Please try again:",
                        reply_markup=ForceReply(input_field_placeholder="Пароль"),
                    )
                logger.info(bms.invalid_login.format(admin_id=user_id))


@dp.message(Command("logout"), AdminFilter())
async def logout_command(message: Message):
    if message.from_user:
        with Session(engine) as session:
            user = session.get(User, message.from_user.id)
            if user:
                user.is_admin = False
                session.commit()
                await message.answer("You have been logged out from admin mode.")
                logger.info(bms.admin_logout.format(admin_id=user.id))


@dp.message(Command("get_step"), AdminFilter())
async def get_step_message_handler(message: Message):
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
                row.append(InlineKeyboardButton(text=" ", callback_data="empty"))
        step_buttons.append(row)
        row = []
    keyboard = InlineKeyboardMarkup(inline_keyboard=step_buttons)
    await message.answer("Select a step:", reply_markup=keyboard)


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
                await message.answer(settings.messages("progress_reset"))
                logger.info(bms.progress_reset.format(id=user_id))
            else:
                await message.answer(settings.messages("not_registered"))
                logger.info(
                    bms.not_registered.format(id=user_id, action="reset progress")
                )


# /delete_me command to delete user data from database
@dp.message(Command("delete_me"), UserRegisteredFilter())
async def delete_me_command_handler(message: Message, state: FSMContext):
    await message.answer(
        "Are you sure you want to delete your account?\n\n*This action cannot be undone!*",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="Yes, delete my account",
                        callback_data="confirm_delete_me",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="Cancel", callback_data="cancel_delete_me"
                    ),
                ],
            ]
        ),
        parse_mode="Markdown",
    )
    await state.set_state(DeleteAccount.waiting_confirmation)
    user_id = message.from_user.id if message.from_user else None
    logger.info(f"User {user_id} initiated account deletion. Waiting for confirmation.")


@dp.callback_query(DeleteAccount.waiting_confirmation)
async def delete_me_callback_handler(callback: CallbackQuery, state: FSMContext):
    if callback.data == "confirm_delete_me":
        user_id = callback.from_user.id
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                session.delete(user)
                session.commit()
                await bot.send_message(user_id, "Your account has been deleted.")
                logger.info(f"User {user_id} account deleted from database.")
        await state.set_state(None)
    elif callback.data == "cancel_delete_me":
        await bot.send_message(callback.from_user.id, "Account deletion cancelled.")
        await state.set_state(None)
    await callback.answer()


# /gen_promo command to generate a promo code (admin only)
@dp.message(Command("gen_promo"), AdminFilter())
async def gen_promo_command_handler(message: Message):
    promo_code = secrets.token_urlsafe(8)
    promo_codes.append(promo_code)
    json.dump(promo_codes, open("promo_codes.json", "w", encoding="utf-8"))
    await message.answer(f"Generated promo code: `{promo_code}`", parse_mode="Markdown")
    logger.info(bms.promo_code_generated.format(code=promo_code))


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
                await callback_query.answer(settings.messages("not_registered"))
                logger.info(
                    bms.not_registered.format(id=user_id, action="request next step")
                )
            elif not user.payed:
                await callback_query.answer(settings.messages("not_payed"))
                logger.info(bms.not_payed.format(id=user_id))
                return
            elif user.step_sent_time:
                await callback_query.answer(settings.messages("step_sent"))
                logger.info(bms.step_sent.format(id=user_id))
                await callback_query.answer()
                return
            elif user.current_step >= len(script):
                await bot.send_message(
                    user_id, settings.messages("script_completed")
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
                            user_id, settings.messages("script_completed")
                        )
                        logger.info(bms.script_completed.format(id=user_id))
                    else:
                        value: int = settings.next_step_delay.value
                        if settings.next_step_delay.type == "Fixed time":
                            hh = value // 3600
                            mm = (value % 3600) // 60
                            time_str = f"{hh:02}:{mm:02} МСК"
                        elif settings.next_step_delay.type == "Period":
                            td = timedelta(seconds=value)
                            dt = datetime.fromtimestamp(user.step_sent_time) + td
                            time_str = dt.strftime("%H:%M") + " МСК"
                        else:
                            raise ValueError("Invalid next_step_delay type")
                        await bot.send_message(
                            user_id,
                            settings.messages("next_step_timeout").format(
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
                        settings.messages("step_send_error").format(
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


@dp.message(F.text.startswith("/"))
async def default_command_handler(message: Message):
    user_id = message.from_user.id if message.from_user else None
    logger.info(f"Got unknown command from user {user_id}: {message.text}")
    await message.answer("Данная команда не существует или недоступна вам.")


@dp.message()
async def default_message_handler(message: Message):
    user_id = message.from_user.id if message.from_user else None
    logger.info(bms.on_message.format(id=user_id, text=message.text))
    await message.answer(settings.messages("on_message"))


async def check_payments():
    while True:
        try:
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
                                text=settings.messages("payment_successful"),
                            )
                        elif status == "canceled":
                            user.payment_status = "canceled"
                            session.commit()
                            logger.info(bms.payment_canceled.format(id=user.id))
                            await bot.send_message(
                                chat_id=user.id,
                                text=settings.messages("payment_canceled"),
                            )
                        await asyncio.sleep(1)  # avoid hammering the payment API
                else:
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to check payments: {e}")


async def send_invite(user: User) -> bool:
    step = script[user.current_step]
    NEXT_STEP_KBD = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=settings.messages("next_step_button"),
                    callback_data="get_step",
                )
            ]
        ]
    )
    try:
        await bot.send_message(
            chat_id=user.id,
            text=settings.messages("step_invite").format(
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
        try:
            next_step_delay = settings.next_step_delay
            if next_step_delay.type == "Period":
                time_threshold = now() - next_step_delay.value
                await send_invites(time_threshold)
            if next_step_delay.type == "Fixed time":
                utc_plus_3 = timezone(timedelta(hours=3))
                now_dt = datetime.now(utc_plus_3)
                start_of_day = now_dt.replace(
                    hour=0, minute=0, second=0, microsecond=0
                ).timestamp()
                time_threshold = start_of_day + next_step_delay.value
                if now() > time_threshold:
                    await send_invites(time_threshold)
                else:
                    await invite_zero_steppers()
            await invite_admins()
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to update next steps: {e}")


# async def reload_settings():
#     while True:
#         try:
#             global settings
#             global script
#             settings = json.load(open("settings.json", "r", encoding="utf-8"))
#             script = json.load(open("script.json", "r", encoding="utf-8"))
#             # logger.info("Settings reloaded")
#             await asyncio.sleep(10)  # reload every 10 seconds
#         except Exception as e:
#             logger.error(f"Failed to reload settings: {e}")


async def main():
    logger.info("Creating database tables")
    SQLModel.metadata.create_all(engine)
    logger.info("Starting payment checking task")
    asyncio.create_task(check_payments())
    logger.info("Starting next step update task")
    asyncio.create_task(update_next_steps())
    # logger.info("Starting settings reload task")
    # asyncio.create_task(reload_settings())
    logger.info("Starting bot polling")
    await dp.start_polling(bot)
    logger.info("Bot has stopped")


if __name__ == "__main__":
    asyncio.run(main())

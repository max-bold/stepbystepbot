from typing import Any, Optional
from dotenv import load_dotenv
from os import getenv
import asyncio
import httpx

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    CallbackQuery,
)

from kassa import create_payment, get_payment_status

import logging
import bot_messages as bms
from datetime import datetime, timezone, timedelta

logger = logging.getLogger("bot")


load_dotenv()
bot_key = getenv("BOT_KEY")
backend_url = getenv("BACKEND_URL")

if bot_key is None:
    raise ValueError("BOT_KEY environment variable not set")
if backend_url is None:
    raise ValueError("BACKEND_URL environment variable not set")

bot = Bot(token=bot_key)
dp = Dispatcher()
backend_client = httpx.AsyncClient(base_url=backend_url, timeout=10.0)
script: list[dict[str, Any]] = []
settings: dict[str, Any] = {}


async def log_event(
    message: str,
    user_id: Optional[int] = None,
    level: str = "info",
) -> None:
    try:
        await backend_client.post(
            "/logs",
            json={
                "user_id": user_id,
                "level": level,
                "message": message,
            },
        )
    except httpx.HTTPError:
        logger.warning("Failed to send log to backend: %s", message)


async def get_user(user_id: int) -> Optional[dict[str, Any]]:
    try:
        response = await backend_client.get(f"/users/{user_id}")
        if response.status_code == 404:
            return None
        response.raise_for_status()
        return response.json()
    except httpx.HTTPError as exc:
        logger.exception("Failed to fetch user %s: %s", user_id, exc)
        await log_event(
            f"Failed to fetch user {user_id}: {exc}",
            user_id=user_id,
            level="error",
        )
        return None


async def create_user(user_id: int, payed: bool) -> dict[str, Any]:
    response = await backend_client.post(
        "/users",
        json={"id": user_id, "payed": payed},
    )
    response.raise_for_status()
    return response.json()


async def update_user(user_id: int, **fields: Any) -> dict[str, Any]:
    response = await backend_client.patch(f"/users/{user_id}", json=fields)
    response.raise_for_status()
    return response.json()


async def fetch_settings() -> dict[str, Any]:
    response = await backend_client.get("/settings")
    response.raise_for_status()
    return response.json()


async def fetch_script() -> list[dict[str, Any]]:
    response = await backend_client.get("/script")
    response.raise_for_status()
    return response.json()


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
        user_id = message.from_user.id
        await log_event(bms.on_start_command.format(id=user_id), user_id=user_id)
        user = await get_user(user_id)
        if not user:
            user = await create_user(
                user_id,
                payed=settings["create_paid_users"],
            )
            await log_event(bms.user_created.format(id=user_id), user_id=user_id)
        else:
            await log_event(bms.user_exists.format(id=user_id), user_id=user_id)
        if not user["payed"]:
            payment_id, confirmation_url = create_payment()
            user = await update_user(
                user_id,
                payment_key=payment_id,
                payment_status="pending",
            )
            await log_event(
                f"Created payment {payment_id} for user {user_id}",
                user_id=user_id,
            )
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
            await log_event(bms.pay_link_sent.format(id=user_id), user_id=user_id)
        else:
            await message.answer(settings["messages"]["already_registered"])
            await log_event(bms.wlc_back.format(id=user_id), user_id=user_id)
    else:
        await log_event(bms.no_user_id, level="warning")


@dp.message(Command("upload"))
async def upload_command(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id:
        user = await get_user(user_id)
        if user and user["is_admin"]:
            updated_user = await update_user(
                user_id, upload_mode=not user["upload_mode"]
            )
            await message.answer(
                bms.upload_mode.format(
                    state="enabled" if updated_user["upload_mode"] else "disabled."
                )
            )
            await log_event(
                f"Upload mode toggled to {updated_user['upload_mode']}",
                user_id=user_id,
            )
        else:
            await message.answer(
                "You are not authorized to perform this action. Only admins can use this command."
            )
            await log_event(bms.not_registered.format(id=user_id), user_id=user_id)


@dp.message(Command("login"))
async def login_command_handler(message: Message):
    if message.from_user and message.text:
        user_id = message.from_user.id
        key = message.text.split(" ")[-1]
        if key == getenv("ADMIN_PASSWORD"):
            user = await get_user(user_id)
            if user:
                await update_user(user_id, payed=True, is_admin=True)
                await log_event(
                    bms.login_successful.format(admin_id=user_id),
                    user_id=user_id,
                )
            else:
                await create_user(user_id, payed=True)
                await update_user(user_id, is_admin=True)
                await log_event(bms.created_admin.format(id=user_id), user_id=user_id)
            await message.answer(settings["messages"]["login_successful"])
            await log_event(
                bms.login_successful.format(admin_id=user_id), user_id=user_id
            )
        else:
            await message.answer("Wrong password. Send in /login <password> format")
            await log_event(
                bms.invalid_login.format(admin_id=user_id),
                user_id=user_id,
                level="warning",
            )


@dp.message(Command("logout"))
async def logout_command(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if user_id:
        user = await get_user(user_id)
        if user:
            await update_user(user_id, is_admin=False)
            await message.answer("You have been logged out from admin mode.")
            await log_event(bms.admin_logout.format(admin_id=user_id), user_id=user_id)
        else:
            await message.answer(settings["messages"]["not_registered"])
            await log_event(bms.not_registered.format(id=user_id), user_id=user_id)


@dp.message(Command("get_step"))
async def get_step_message_handler(message: Message):
    if message.from_user:
        user_id = message.from_user.id
        user = await get_user(user_id)
        if not user:
            await message.answer(settings["messages"]["not_registered"])
            await log_event(bms.not_registered.format(id=user_id), user_id=user_id)
        else:
            if user["is_admin"]:
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
                await log_event(
                    bms.get_step_not_admin.format(id=user_id),
                    user_id=user_id,
                )


@dp.message(Command("reset"))
async def reset_command_handler(message: Message):
    if message.from_user:
        user_id = message.from_user.id
        user = await get_user(user_id)
        if user:
            await update_user(
                user_id,
                current_step=0,
                step_sent_time=0.0,
                next_step_invite_sent=False,
            )
            await message.answer(settings["messages"]["progress_reset"])
            await log_event(bms.progress_reset.format(id=user_id), user_id=user_id)
        else:
            await message.answer(settings["messages"]["not_registered"])
            await log_event(bms.not_registered.format(id=user_id), user_id=user_id)


# /delete_me command to delete user data from database
@dp.message(Command("delete_me"))
async def delete_me_command_handler(message: Message):
    if message.from_user:
        user_id = message.from_user.id
        user = await get_user(user_id)
        if user:
            await backend_client.delete(f"/users/{user_id}")
            await message.answer("Your data has been deleted from the database.")
            await log_event(
                f"User {user_id} data deleted from database.",
                user_id=user_id,
            )
        else:
            await message.answer(settings["messages"]["not_registered"])
            await log_event(bms.not_registered.format(id=user_id), user_id=user_id)


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
            await log_event(
                bms.send_fail.format(type=content["type"], id=user_id, e=e),
                user_id=user_id,
                level="error",
            )
            errors = True
    return not errors


@dp.callback_query(F.data.startswith("admin_get_step="))
async def admin_get_step_handler(callback_query: CallbackQuery):
    if callback_query.from_user and callback_query.data:
        user_id = callback_query.from_user.id
        step_number = int(callback_query.data.split("=")[1])
        await log_event(
            bms.get_step_menu_request.format(
                admin_id=user_id,
                step_number=step_number,
            ),
            user_id=user_id,
        )
        user = await get_user(user_id)
        if user and user["is_admin"]:
            await send_step_content(user_id, step_number)
            await callback_query.answer()
            await log_event(
                bms.sent_step_to_admin.format(
                    admin_id=user_id, step_number=step_number
                ),
                user_id=user_id,
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
        await log_event(bms.next_request.format(id=user_id), user_id=user_id)
        user = await get_user(user_id)
        if not user:
            await callback_query.answer(settings["messages"]["not_registered"])
            await log_event(bms.not_registered.format(id=user_id), user_id=user_id)
        elif not user["payed"]:
            await callback_query.answer(settings["messages"]["not_payed"])
            await log_event(bms.not_payed.format(id=user_id), user_id=user_id)
            return
        elif user["step_sent_time"]:
            await callback_query.answer(settings["messages"]["step_sent"])
            await log_event(bms.step_sent.format(id=user_id), user_id=user_id)
            await callback_query.answer()
            return
        elif user["current_step"] >= len(script):
            await bot.send_message(user_id, settings["messages"]["script_completed"])
            await log_event(bms.script_completed.format(id=user_id), user_id=user_id)
            return
        else:
            if await send_step_content(user_id, user["current_step"]):
                updated_user = await update_user(
                    user_id,
                    step_sent_time=now(),
                    next_step_invite_sent=False,
                    current_step=user["current_step"] + 1,
                )
                if updated_user["current_step"] >= len(script):
                    await bot.send_message(
                        user_id, settings["messages"]["script_completed"]
                    )
                    await log_event(
                        bms.script_completed.format(id=user_id), user_id=user_id
                    )
                else:
                    value: int = settings["next_step_delay"]["value"]
                    if settings["next_step_delay"]["type"] == "Fixed time":
                        hh = value // 3600
                        mm = (value % 3600) // 60
                        time_str = f"{hh:02}:{mm:02} МСК"
                    elif settings["next_step_delay"]["type"] == "Period":
                        td = timedelta(seconds=value)
                        dt = datetime.fromtimestamp(updated_user["step_sent_time"]) + td
                        time_str = dt.strftime("%H:%M") + " МСК"
                    else:
                        raise ValueError("Invalid next_step_delay type")
                    await bot.send_message(
                        user_id,
                        settings["messages"]["next_step_timeout"].format(time=time_str),
                    )
                await callback_query.answer()
                await log_event(
                    bms.step_sent_success.format(
                        step_number=updated_user["current_step"], id=user_id
                    ),
                    user_id=user_id,
                )
            else:
                await callback_query.answer(
                    settings["messages"]["step_send_error"].format(
                        step_number=user["current_step"],
                        id=user_id,
                    ),
                    show_alert=True,
                )
                await log_event(
                    bms.step_send_error.format(
                        step_number=user["current_step"],
                        id=user_id,
                    ),
                    user_id=user_id,
                    level="error",
                )


@dp.message()
async def default_message_handler(message: Message):
    if message.text:
        id = message.from_user.id if message.from_user else "unknown"
        await log_event(bms.on_message.format(id=id, text=message.text))
        await message.answer(settings["messages"]["on_message"])
    else:
        user_id = message.from_user.id if message.from_user else None
        if user_id:
            user = await get_user(user_id)
            if user and user["upload_mode"]:
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
        try:
            response = await backend_client.get(
                "/users",
                params={"payed": False, "payment_status": "pending"},
            )
            response.raise_for_status()
            users = response.json()
        except httpx.HTTPError as exc:
            await log_event(f"Failed to load pending users: {exc}", level="error")
            await asyncio.sleep(1)
            continue
        if users:
            for user in users:
                await log_event(bms.check_payment.format(id=user["id"]), user_id=user["id"])
                status = get_payment_status(user["payment_key"])
                if status == "succeeded":
                    await update_user(
                        user["id"], payed=True, payment_status="succeeded"
                    )
                    await log_event(
                        bms.payment_confirmed.format(id=user["id"]),
                        user_id=user["id"],
                    )
                    await bot.send_message(
                        chat_id=user["id"],
                        text=settings["messages"]["payment_successful"],
                    )
                elif status == "canceled":
                    await update_user(user["id"], payment_status="canceled")
                    await log_event(
                        bms.payment_canceled.format(id=user["id"]),
                        user_id=user["id"],
                    )
                    await bot.send_message(
                        chat_id=user["id"],
                        text=settings["messages"]["payment_canceled"],
                    )
                await asyncio.sleep(1)
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


async def send_invite(user: dict[str, Any]) -> bool:
    step = script[user["current_step"]]
    try:
        await bot.send_message(
            chat_id=user["id"],
            text=settings["messages"]["step_invite"].format(
                title=step["title"],
                description=step["description"],
                step_number=user["current_step"] + 1,
            ),
            reply_markup=NEXT_STEP_KBD,
        )
        await log_event(bms.step_invite.format(id=user["id"]), user_id=user["id"])
        return True
    except Exception as e:
        await log_event(
            bms.message_failed.format(id=user["id"], e=e),
            user_id=user["id"],
            level="error",
        )
        return False


async def send_invites(time_threshold: float):
    response = await backend_client.get(
        "/users",
        params={
            "payed": True,
            "current_step_lt": len(script),
            "step_sent_time_lt": time_threshold,
            "next_step_invite_sent": False,
        },
    )
    response.raise_for_status()
    users = response.json()
    for user in users:
        if await send_invite(user):
            await update_user(
                user["id"], next_step_invite_sent=True, step_sent_time=0.0
            )


async def invite_zero_steppers():
    response = await backend_client.get(
        "/users",
        params={
            "payed": True,
            "current_step_eq": 0,
            "next_step_invite_sent": False,
        },
    )
    response.raise_for_status()
    users = response.json()
    for user in users:
        if await send_invite(user):
            await update_user(
                user["id"], next_step_invite_sent=True, step_sent_time=0.0
            )


async def invite_admins():
    response = await backend_client.get(
        "/users",
        params={
            "is_admin": True,
            "current_step_lt": len(script),
            "next_step_invite_sent": False,
        },
    )
    response.raise_for_status()
    users = response.json()
    for user in users:
        if await send_invite(user):
            await update_user(
                user["id"], next_step_invite_sent=True, step_sent_time=0.0
            )


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
        try:
            settings = await fetch_settings()
            script = await fetch_script()
            await log_event("Settings reloaded")
        except httpx.HTTPError as exc:
            await log_event(f"Failed to reload settings: {exc}", level="error")
        await asyncio.sleep(10)


async def main():
    global settings
    global script
    settings = await fetch_settings()
    script = await fetch_script()
    await log_event("Starting payment checking task")
    asyncio.create_task(check_payments())
    await log_event("Starting next step update task")
    asyncio.create_task(update_next_steps())
    await log_event("Starting settings reload task")
    asyncio.create_task(reload_settings())
    await log_event("Starting bot polling")
    try:
        await dp.start_polling(bot)
    finally:
        await log_event("Bot has stopped")
        await backend_client.aclose()


if __name__ == "__main__":
    asyncio.run(main())

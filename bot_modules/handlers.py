import secrets
from datetime import datetime, timedelta
from typing import Any

from aiogram import Bot, F
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    ForceReply,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from email_validator import EmailNotValidError, validate_email
from sqlmodel import Session

from bot_modules import bot_messages as bms
from kassa import create_payment
from aiogram.fsm.state import State, StatesGroup

from bot_modules.config import script, settings
from bot_modules.models import User
from bot_modules.runtime import dp, engine, logger, promo_codes, save_promo_codes
from bot_modules.utils import is_admin_password_valid, now


class AdminLogin(StatesGroup):
    waiting_password = State()


class PromoCodeEntry(StatesGroup):
    waiting_promo_code = State()


class DeleteAccount(StatesGroup):
    waiting_confirmation = State()


class CreatePayment(StatesGroup):
    waiting_email = State()
    waiting_payment = State()


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
                    return {"user": user}
        return False


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
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text=settings.messages("pay_button_text"),
                                callback_data="enter_email",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text=settings.messages("promo button"),
                                callback_data="enter_promo_code",
                            )
                        ],
                    ]
                )
                await message.answer(settings.messages("welcome_message"), reply_markup=keyboard)
                logger.info(f"New user registered: {user.id}")
            else:
                await message.answer(settings.messages("already_registered"))
                logger.info(bms.wlc_back.format(id=user.id))
    else:
        logger.warning(bms.no_user_id)


@dp.callback_query(F.data == "enter_promo_code")
async def enter_promo_code_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if callback_query.from_user:
        if await state.get_value("promo_attempts", 0) < 3:
            user_id = callback_query.from_user.id
            await bot.send_message(
                user_id,
                settings.messages("promo prompt"),
                reply_markup=ForceReply(input_field_placeholder="code"),
            )
            await state.set_state(PromoCodeEntry.waiting_promo_code)
        else:
            await bot.send_message(callback_query.from_user.id, settings.messages("promo limit reached"))
    await callback_query.answer()


@dp.callback_query(F.data == "enter_email")
async def enter_email_handler(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    if callback_query.from_user:
        user_id = callback_query.from_user.id
        await bot.send_message(
            user_id,
            settings.messages("email prompt"),
            reply_markup=ForceReply(input_field_placeholder="email"),
        )
        await state.set_state(CreatePayment.waiting_email)
    await callback_query.answer()


@dp.message(CreatePayment.waiting_email)
async def email_entry_handler(message: Message, state: FSMContext):
    if message.from_user and message.text:
        user_id = message.from_user.id
        email = message.text.strip()
        try:
            validate_email(email)
            with Session(engine) as session:
                user = session.get(User, user_id)
                if user:
                    user.email = email
                    session.commit()
                    logger.info(f"User {user_id} provided email: {email}")
                    await state.set_state(CreatePayment.waiting_payment)
                    payment_id, confirmation_url = create_payment(
                        settings.payment_amount, settings.goods_name, email
                    )
                    user.payment_key = payment_id
                    user.payment_status = "pending"
                    session.commit()
                    keyboard = InlineKeyboardMarkup(
                        inline_keyboard=[[
                            InlineKeyboardButton(text=settings.messages("pay_button_text"), url=confirmation_url)
                        ]]
                    )
                    await message.answer(settings.messages("go to yookassa"), reply_markup=keyboard)
        except EmailNotValidError:
            await message.answer(
                settings.messages("invalid_email"),
                reply_markup=ForceReply(input_field_placeholder="email"),
            )
            logger.info(f"User {user_id} entered invalid email: {email}")


@dp.message(CreatePayment.waiting_payment, UserRegisteredFilter())
async def handle_waiting_payment(message: Message, user: User):
    if not user.payed:
        await message.answer(settings.messages("payment_pending"))


@dp.message(PromoCodeEntry.waiting_promo_code)
async def promo_code_entry_handler(message: Message, state: FSMContext):
    attempts = await state.get_value("promo_attempts", 0)
    if attempts < 3 and message.from_user and message.text:
        user_id = message.from_user.id
        entered_code = message.text.strip()
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                if entered_code in promo_codes:
                    user.payed = True
                    session.commit()
                    promo_codes.remove(entered_code)
                    save_promo_codes()
                    await message.answer(settings.messages("promo_ok"))
                    await state.set_state(None)
                    await state.update_data(promo_attempts=0)
                else:
                    attempts += 1
                    await state.update_data(promo_attempts=attempts)
                    if attempts == 3:
                        await message.answer(settings.messages("promo limit reached"))
                        await state.set_state(None)
                    else:
                        await message.answer(
                            settings.messages("promo error"),
                            reply_markup=ForceReply(input_field_placeholder="code"),
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
                    bms.upload_mode.format(state="enabled" if user.upload_mode else "disabled.")
                )


@dp.message(UploadModeFilter())
async def upload_mode_handler(message: Message):
    file_id = None
    if message.photo:
        file_id = message.photo[-1].file_id
    elif message.video:
        file_id = message.video.file_id
    elif message.video_note:
        file_id = message.video_note.file_id
    elif message.document:
        file_id = message.document.file_id
    elif message.audio:
        file_id = message.audio.file_id
    elif message.voice:
        file_id = message.voice.file_id
    if file_id:
        await message.reply(f"`{file_id}`", parse_mode="Markdown")
    else:
        await message.answer(settings.messages("upload_failed"))


@dp.message(Command("login"), ~AdminFilter())
async def login_command_handler(message: Message, state: FSMContext):
    if await state.get_value("login_attempts", 0) < 3:
        await message.answer("Please enter the admin password:", reply_markup=ForceReply(input_field_placeholder="password"))
        await state.set_state(AdminLogin.waiting_password)


@dp.message(Command("login"), AdminFilter())
async def login_command_handler2(message: Message):
    await message.answer(settings.messages("login_successful"))


@dp.message(AdminLogin.waiting_password)
async def admin_password_handler(message: Message, state: FSMContext):
    attempts = await state.get_value("login_attempts", 0)
    if attempts < 3 and message.from_user and message.text:
        user_id = message.from_user.id
        if is_admin_password_valid(message.text.strip()):
            with Session(engine) as session:
                user = session.get(User, user_id)
                if not user:
                    user = User(id=user_id, payed=True, is_admin=True)
                    session.add(user)
                user.payed = True
                user.is_admin = True
                session.commit()
                await message.answer(settings.messages("login_successful"))
            await state.set_state(None)
            await state.update_data(login_attempts=0)
        else:
            attempts += 1
            await state.update_data(login_attempts=attempts)
            if attempts == 3:
                await message.answer("Too many login attempts. Please contact the administrator.")
                await state.set_state(None)
            else:
                await message.answer("Wrong password. Please try again:", reply_markup=ForceReply(input_field_placeholder="Пароль"))


@dp.message(Command("logout"), AdminFilter())
async def logout_command(message: Message):
    if message.from_user:
        with Session(engine) as session:
            user = session.get(User, message.from_user.id)
            if user:
                user.is_admin = False
                session.commit()
                await message.answer("You have been logged out from admin mode.")


@dp.message(Command("get_step"), AdminFilter())
async def get_step_message_handler(message: Message):
    row_count = len(script) // 3 + (1 if len(script) % 3 != 0 else 0)
    step_buttons = []
    row = []
    for i in range(row_count):
        for j in range(3):
            step_index = i * 3 + j
            if step_index < len(script):
                row.append(InlineKeyboardButton(text=f"{step_index+1}. {script[step_index]['title']}", callback_data=f"admin_get_step={step_index}"))
            else:
                row.append(InlineKeyboardButton(text=" ", callback_data="empty"))
        step_buttons.append(row)
        row = []
    await message.answer("Select a step:", reply_markup=InlineKeyboardMarkup(inline_keyboard=step_buttons))


@dp.message(Command("reset"))
async def reset_command_handler(message: Message):
    if message.from_user:
        with Session(engine) as session:
            user = session.get(User, message.from_user.id)
            if user:
                user.current_step = 0
                user.step_sent_time = 0.0
                user.next_step_invite_sent = False
                session.commit()
                await message.answer(settings.messages("progress_reset"))


@dp.message(Command("delete_me"), UserRegisteredFilter())
async def delete_me_command_handler(message: Message, state: FSMContext):
    await message.answer(
        "Are you sure you want to delete your account?\n\n*This action cannot be undone!*",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="Yes, delete my account", callback_data="confirm_delete_me")
        ], [InlineKeyboardButton(text="Cancel", callback_data="cancel_delete_me")]]),
        parse_mode="Markdown",
    )
    await state.set_state(DeleteAccount.waiting_confirmation)


@dp.callback_query(DeleteAccount.waiting_confirmation)
async def delete_me_callback_handler(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if callback.data == "confirm_delete_me":
        user_id = callback.from_user.id
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user:
                session.delete(user)
                session.commit()
                await bot.send_message(user_id, "Your account has been deleted.")
        await state.clear()
    elif callback.data == "cancel_delete_me":
        await bot.send_message(callback.from_user.id, "Account deletion cancelled.")
        await state.set_state(None)
    await callback.answer()


@dp.message(Command("gen_promo"), AdminFilter())
async def gen_promo_command_handler(message: Message):
    promo_code = secrets.token_urlsafe(8)
    promo_codes.append(promo_code)
    save_promo_codes()
    await message.answer(f"Generated promo code: `{promo_code}`", parse_mode="Markdown")


async def send_step_content(user_id: int, step_number: int, bot: Bot) -> bool:
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
                        await bot.send_document(user_id, file_id, caption=caption)
        except Exception:
            errors = True
    return not errors


@dp.callback_query(F.data.startswith("admin_get_step="))
async def admin_get_step_handler(callback_query: CallbackQuery, bot: Bot):
    if callback_query.from_user and callback_query.data:
        user_id = callback_query.from_user.id
        step_number = int(callback_query.data.split("=")[1])
        with Session(engine) as session:
            user = session.get(User, user_id)
            if user and user.is_admin:
                await send_step_content(user_id, step_number, bot)
                await callback_query.answer()
            else:
                await callback_query.answer(bms.not_authorized, show_alert=True)


@dp.callback_query(F.data == "empty")
async def empty_button_handler(callback_query: CallbackQuery):
    await callback_query.answer()


@dp.callback_query(F.data == "get_step")
async def get_step_command_handler(callback_query: CallbackQuery, bot: Bot):
    if callback_query.from_user:
        user_id = callback_query.from_user.id
        with Session(engine) as session:
            user = session.get(User, user_id)
            if not user:
                await callback_query.answer(settings.messages("not_registered"))
            elif not user.payed:
                await callback_query.answer(settings.messages("not_payed"))
                return
            elif user.step_sent_time:
                await callback_query.answer(settings.messages("step_sent"))
                return
            elif user.current_step >= len(script):
                await bot.send_message(user_id, settings.messages("script_completed"))
                return
            else:
                if await send_step_content(user_id, user.current_step, bot):
                    user.step_sent_time = now()
                    user.next_step_invite_sent = False
                    user.current_step += 1
                    session.commit()
                    if user.current_step >= len(script):
                        await bot.send_message(user_id, settings.messages("script_completed"))
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
                        await bot.send_message(user_id, settings.messages("next_step_timeout").format(time=time_str))
                    await callback_query.answer()
                else:
                    await callback_query.answer(
                        settings.messages("step_send_error").format(step_number=user.current_step, id=user_id),
                        show_alert=True,
                    )


@dp.message(F.text.startswith("/"))
async def default_command_handler(message: Message):
    await message.answer("Данная команда не существует или недоступна вам.")


@dp.message()
async def default_message_handler(message: Message):
    await message.answer(settings.messages("on_message"))

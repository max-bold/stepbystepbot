import asyncio
from datetime import datetime, timedelta, timezone

from aiohttp import ClientSession
from aiohttp_socks import ProxyConnector
from aiogram import Bot
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from sqlmodel import Session, select

import bot_messages as bms
from kassa import get_payment_status
from bot_modules.config import script, settings
from bot_modules.handlers import CreatePayment, send_step_content
from bot_modules.models import User
from bot_modules.runtime import dp, engine, logger
from bot_modules.utils import now


async def check_payments(bot: Bot):
    while True:
        try:
            with Session(engine) as session:
                users = session.exec(
                    select(User).where(User.payment_status == "pending", User.payed == False)
                ).all()
                if users:
                    for user in users:
                        status = get_payment_status(user.payment_key)
                        if status == "succeeded":
                            user.payed = True
                            user.payment_status = "succeeded"
                            session.commit()
                            await bot.send_message(chat_id=user.id, text=settings.messages("payment_successful"))
                            key = StorageKey(bot.id, user.id, user.id)
                            fsm = FSMContext(dp.storage, key)
                            if await fsm.get_state() == CreatePayment.waiting_payment:
                                await fsm.set_state(None)
                        elif status == "canceled":
                            user.payment_status = "canceled"
                            session.commit()
                            await bot.send_message(chat_id=user.id, text=settings.messages("payment_canceled"))
                        await asyncio.sleep(1)
                else:
                    await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to check payments: {e}")


async def send_invite(user: User, bot: Bot) -> bool:
    step = script[user.current_step]
    next_step_kbd = [[{"text": settings.messages("next_step_button"), "callback_data": "get_step"}]]
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        await bot.send_message(
            chat_id=user.id,
            text=settings.messages("step_invite").format(
                title=step["title"],
                description=step["description"],
                step_number=user.current_step + 1,
            ),
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(**next_step_kbd[0][0])]]
            ),
        )
        return True
    except Exception as e:
        logger.error(bms.message_failed.format(id=user.id, e=e))
        return False


async def send_invites(time_threshold: float, bot: Bot):
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
            if await send_invite(user, bot):
                user.next_step_invite_sent = True
                user.step_sent_time = 0.0
                session.commit()


async def invite_zero_steppers(bot: Bot):
    with Session(engine) as session:
        users = session.exec(
            select(User).where(
                User.payed == True,
                User.current_step == 0,
                User.next_step_invite_sent == False,
            )
        ).all()
        for user in users:
            if await send_invite(user, bot):
                user.next_step_invite_sent = True
                user.step_sent_time = 0.0
                session.commit()


async def invite_admins(bot: Bot):
    with Session(engine) as session:
        users = session.exec(
            select(User).where(
                User.is_admin == True,
                User.current_step < len(script),
                User.next_step_invite_sent == False,
            )
        ).all()
        for user in users:
            if await send_invite(user, bot):
                user.next_step_invite_sent = True
                user.step_sent_time = 0.0
                session.commit()


async def update_next_steps(bot: Bot):
    while True:
        try:
            next_step_delay = settings.next_step_delay
            if next_step_delay.type == "Period":
                await send_invites(now() - next_step_delay.value, bot)
            if next_step_delay.type == "Fixed time":
                utc_plus_3 = timezone(timedelta(hours=3))
                now_dt = datetime.now(utc_plus_3)
                start_of_day = now_dt.replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
                time_threshold = start_of_day + next_step_delay.value
                if now() > time_threshold:
                    await send_invites(time_threshold, bot)
                else:
                    await invite_zero_steppers(bot)
            await invite_admins(bot)
            await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Failed to update next steps: {e}")


class SocksAiohttpSession(AiohttpSession):
    def __init__(self, *, proxy_url: str, **kwargs):
        super().__init__(**kwargs)
        self._proxy_url = proxy_url
        self._connector: ProxyConnector | None = None
        self._client: ClientSession | None = None

    async def create_session(self) -> ClientSession:
        if self._client and not self._client.closed:
            return self._client
        if self._connector is None:
            self._connector = ProxyConnector.from_url(self._proxy_url)
        self._client = ClientSession(connector=self._connector)
        return self._client

    async def close(self) -> None:
        if self._client and not self._client.closed:
            await self._client.close()
        self._client = None
        if self._connector is not None:
            await self._connector.close()
        self._connector = None
        await super().close()

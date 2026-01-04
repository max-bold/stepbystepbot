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

load_dotenv()
bot_key = getenv("BOT_KEY")

if not bot_key:
    raise ValueError("BOT_KEY is not set in environment variables")

bot = Bot(token=bot_key)
dp = Dispatcher()

upload_mode = False
@dp.message(Command("upload"))
async def upload_command(message: Message):
    global upload_mode
    upload_mode = not upload_mode
    await message.answer(f"Upload mode is now {'enabled' if upload_mode else 'disabled'}.")

@dp.message()
async def echo_message(message: Message):
    global upload_mode
    if message.text:
        await message.answer(text=message.text)
    if upload_mode:
        if message.photo:
            for size in message.photo:
                text = f"Size: {size.width}x{size.height}, {size.file_size/1024/1024:.2f} MB\n\n{size.file_id}"
                await message.answer(text)
        if message.video:
            await message.answer(message.video.file_id)
        if message.video_note:
            await message.answer(message.video_note.file_id)
        if message.document:
            await message.answer(message.document.file_id)
        if message.audio:
            await message.answer(message.audio.file_id)
        if message.voice:
            await message.answer(message.voice.file_id)
if __name__ == "__main__":
    asyncio.run(dp.start_polling(bot))
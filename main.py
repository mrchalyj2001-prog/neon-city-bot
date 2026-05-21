from aiogram import Bot, Dispatcher
import asyncio
import os

from app.handlers.start import router as start_router

TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=TOKEN)
dp = Dispatcher()

dp.include_router(start_router)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

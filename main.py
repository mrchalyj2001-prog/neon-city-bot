import os
import asyncio
from aiohttp import web

from aiogram import Bot, Dispatcher
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from app.handlers.start import router as start_router

TOKEN = os.getenv("BOT_TOKEN")
BASE_URL = os.getenv("BASE_URL")  # Render даст домен

WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = BASE_URL + WEBHOOK_PATH

bot = Bot(token=TOKEN)
dp = Dispatcher()
dp.include_router(start_router)

async def on_startup(app):
    await bot.set_webhook(WEBHOOK_URL)

async def on_shutdown(app):
    await bot.delete_webhook()

app = web.Application()

SimpleRequestHandler(
    dispatcher=dp,
    bot=bot,
).register(app, path=WEBHOOK_PATH)

setup_application(app, dp, bot=bot)

app.on_startup.append(on_startup)
app.on_shutdown.append(on_shutdown)

if __name__ == "__main__":
    web.run_app(app, host="0.0.0.0", port=int(os.getenv("PORT", 10000)))

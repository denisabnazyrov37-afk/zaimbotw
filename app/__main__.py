import asyncio
from aiogram import Bot, Dispatcher
from app.config import settings
from app.db import init_db
from app.handlers import router

async def main():
    await init_db()
    bot = Bot(settings.bot_token)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

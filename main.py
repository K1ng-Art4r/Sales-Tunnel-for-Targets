import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramNetworkError

from app.config import BOT_TOKEN
from app.db import init_db
from app.export_sync import setup_export_scheduler
from app.handlers.start import router as start_router
from app.warmup import setup_scheduler

logger = logging.getLogger(__name__)


async def main():
    logging.basicConfig(level=logging.INFO)

    await init_db()

    bot = Bot(token=BOT_TOKEN)
    scheduler = None
    try:
        await bot.delete_webhook(drop_pending_updates=True, request_timeout=30)

        dp = Dispatcher()
        dp.include_router(start_router)

        scheduler = setup_scheduler(bot)
        setup_export_scheduler(scheduler)

        await dp.start_polling(bot)
    except TelegramNetworkError:
        logger.exception(
            "Failed to connect to Telegram API. Check network/VPN/proxy access and BOT_TOKEN, then restart the bot."
        )
        raise
    finally:
        if scheduler is not None:
            scheduler.shutdown(wait=False)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())

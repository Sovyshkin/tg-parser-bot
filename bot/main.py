"""Точка входа бота."""

import asyncio
import logging

from aiohttp.resolver import ThreadedResolver
from aiogram import Bot, Dispatcher
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.exceptions import TelegramNetworkError

from bot.config import config
from bot.database import init_db
from bot.handlers import routers
from bot.security import add_sensitive_log_filter

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
add_sensitive_log_filter()
logger = logging.getLogger(__name__)


async def main():
    """Главная функция запуска бота."""
    # Инициализация базы данных
    await init_db()
    logger.info("База данных инициализирована")
    
    # Создание сессии с системным DNS-резолвером.
    # Это устраняет ошибки aiodns вида "Could not contact DNS servers".
    session = AiohttpSession(timeout=60)
    session._connector_init["resolver"] = ThreadedResolver()
    session._connector_init["ttl_dns_cache"] = 300

    # Создание бота и диспетчера
    bot = Bot(token=config.bot.token, session=session)
    dp = Dispatcher()
    
    # Регистрация роутеров
    for router in routers:
        dp.include_router(router)
    
    logger.info("Бот запущен!")
    
    # Запуск polling с автопереподключением при временных сетевых сбоях
    try:
        while True:
            try:
                await dp.start_polling(bot)
                break
            except TelegramNetworkError as exc:
                logger.error(
                    "Проблема сети при подключении к Telegram: %s. Повтор через 5 сек.",
                    exc,
                )
                await asyncio.sleep(5)
    finally:
        await bot.session.close()
        logger.info("Бот остановлен")


if __name__ == "__main__":
    try:
        # На некоторых окружениях uvloop может давать нестабильный DNS-resolve.
        asyncio.set_event_loop_policy(asyncio.DefaultEventLoopPolicy())
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен пользователем")

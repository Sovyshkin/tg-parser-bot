"""Хендлеры бота."""

from bot.handlers.start import router as start_router
from bot.handlers.account import router as account_router
from bot.handlers.parse import router as parse_router
from bot.handlers.history import router as history_router

routers = [start_router, account_router, parse_router, history_router]

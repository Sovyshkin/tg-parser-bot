"""Inline клавиатуры бота."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def get_main_keyboard() -> InlineKeyboardMarkup:
    """Основная клавиатура."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔍 Парсить чат", callback_data="parse"),
            InlineKeyboardButton(text="📋 История", callback_data="history")
        ],
        [
            InlineKeyboardButton(text="❓ Помощь", callback_data="help")
        ]
    ])
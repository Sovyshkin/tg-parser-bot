"""Reply-клавиатуры бота."""

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


def get_persistent_menu() -> ReplyKeyboardMarkup:
    """Постоянное нижнее меню команд."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="/parse"), KeyboardButton(text="/account")],
            [KeyboardButton(text="/history"), KeyboardButton(text="/help")],
            [KeyboardButton(text="/menu")],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Выберите команду или отправьте invite-ссылку...",
    )

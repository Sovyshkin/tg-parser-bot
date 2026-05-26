"""Хендлер информации об активном аккаунте Telethon."""

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.enums import ParseMode

from bot.keyboards.reply import get_persistent_menu
from bot.services.parser import parser

router = Router()

def _mask_phone(phone: str) -> str:
    digits = "".join(ch for ch in phone if ch.isdigit())
    if len(digits) < 7:
        return "скрыт"
    return f"+{digits[:2]}***{digits[-2:]}"


@router.message(Command("account"))
async def cmd_account(message: Message):
    """Показать информацию об активном аккаунте."""
    await send_account_info(message)


@router.callback_query(F.data == "show_account_info")
async def cb_account_info(callback: CallbackQuery):
    """Показать информацию об активном аккаунте из кнопки."""
    await send_account_info(callback.message)
    await callback.answer()


async def send_account_info(message: Message):
    """Сбор и вывод информации об аккаунте Telethon."""
    try:
        client = await parser.connect()
        is_authorized = await client.is_user_authorized()
        if not is_authorized:
            await message.answer(
                "👤 <b>Аккаунт Telethon</b>\n\n"
                "Статус: ❌ не авторизован\n\n"
                "Чтобы авторизовать аккаунт, запусти /parse и следуй шагам в чате.",
                parse_mode=ParseMode.HTML,
                reply_markup=get_persistent_menu(),
            )
            return

        me = await client.get_me()
        full_name = " ".join(
            [part for part in [getattr(me, "first_name", None), getattr(me, "last_name", None)] if part]
        ) or "Без имени"
        username = f"@{me.username}" if getattr(me, "username", None) else "не указан"
        phone = _mask_phone(str(getattr(me, "phone", ""))) if getattr(me, "phone", None) else "скрыт"

        await message.answer(
            "👤 <b>Активный аккаунт Telethon</b>\n\n"
            f"• Имя: <b>{full_name}</b>\n"
            f"• Username: <b>{username}</b>\n"
            f"• Телефон: <b>{phone}</b>\n"
            f"• ID: <code>{me.id}</code>\n"
            "• Статус: ✅ авторизован",
            parse_mode=ParseMode.HTML,
            reply_markup=get_persistent_menu(),
        )
    except Exception as e:
        await message.answer(
            "❌ Не удалось получить информацию об аккаунте.\n"
            f"Причина: {e}",
            reply_markup=get_persistent_menu(),
        )

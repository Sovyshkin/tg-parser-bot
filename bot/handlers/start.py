"""Хендлеры команд start и help."""

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.enums import ParseMode

from bot.keyboards.reply import get_persistent_menu

router = Router()


@router.message(Command("start"))
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    await message.answer(
        "👋 <b>Привет!</b>\n\n"
        "Я бот для парсинга пользователей из Telegram чатов и каналов.\n\n"
        "📋 <b>Доступные команды:</b>\n"
        "/parse - Начать парсинг чата\n"
        "/account - Активный аккаунт\n"
        "/history - История парсингов\n"
        "/help - Помощь\n\n"
        "🚀 Чтобы начать, используй /parse: выбери чат из списка или отправь invite-ссылку.",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="👤 Аккаунт", callback_data="show_account_info")],
            ]
        ),
    )
    await message.answer("📌 Меню закреплено снизу для быстрого доступа.", reply_markup=get_persistent_menu())


@router.message(Command("menu"))
async def cmd_menu(message: Message):
    """Показать постоянное меню повторно."""
    await message.answer(
        "📌 Меню открыто. Можешь пользоваться кнопками ниже в любой момент.",
        reply_markup=get_persistent_menu(),
    )


@router.message(Command("help"))
async def cmd_help(message: Message):
    """Обработчик команды /help."""
    await message.answer(
        "📖 <b>Как пользоваться ботом:</b>\n\n"
        
        "1️⃣ <b>Парсинг чата:</b>\n"
        "• Используй /parse\n"
        "• Выбери чат из списка «Мои чаты» или отправь invite-ссылку\n"
        "  (https://t.me/+... или https://t.me/joinchat/...)\n"
        "• Дождись завершения\n"
        "• Получи Excel файл с данными\n\n"
        
        "2️⃣ <b>Полученные данные:</b>\n"
        "• ID пользователя\n"
        "• Username (@username)\n"
        "• Имя и фамилия\n"
        "• Телефон (если доступен)\n"
        "• Тип (бот/человек)\n\n"
        
        "⚠️ <b>Важно:</b>\n"
        "• Бот работает только с открытыми чатами\n"
        "• Некоторые данные могут быть скрыты настройками приватности",
        parse_mode=ParseMode.HTML,
        reply_markup=get_persistent_menu(),
    )

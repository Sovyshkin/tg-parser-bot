"""Хендлер истории парсинга."""

from datetime import datetime
from pathlib import Path

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile
from aiogram.enums import ParseMode

from bot.database import get_parsing_history

router = Router()


@router.message(Command("history"))
async def cmd_history(message: Message):
    """Показать историю парсинга."""
    history = await get_parsing_history(limit=10)
    
    if not history:
        await message.answer(
            "📋 <b>История парсинга пуста</b>\n\n"
            "Используй /parse чтобы начать первый парсинг!",
            parse_mode=ParseMode.HTML
        )
        return
    
    text = "📋 <b>История парсинга:</b>\n\n"
    
    for i, session in enumerate(history, 1):
        date = session.created_at.strftime("%d.%m.%Y %H:%M")
        title = session.chat_title or session.chat_username
        status_icon = "✅" if session.status == "completed" else "❌"
        
        text += (
            f"{i}. {status_icon} <b>{title}</b>\n"
            f"   👥 {session.user_count} участников\n"
            f"   📅 {date}\n\n"
        )
    
    # Проверяем существование последнего файла
    last_session = history[0]
    if last_session.file_path and Path(last_session.file_path).exists():
        await message.answer_document(
            document=FSInputFile(last_session.file_path),
            caption=text,
            parse_mode=ParseMode.HTML
        )
    else:
        await message.answer(text, parse_mode=ParseMode.HTML)
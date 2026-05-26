"""Хендлер парсинга."""

import asyncio
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.reply import get_persistent_menu
from bot.services.parser import (
    parser,
    AuthCodeRequiredError,
    AuthPasswordRequiredError,
    ParseChatError,
)
from bot.services.exporter import exporter
from bot.database import save_parsing_session_sync

router = Router()
CHATS_PAGE_SIZE = 8


class ParseStates(StatesGroup):
    """Состояния для процесса парсинга."""
    waiting_for_chat = State()
    waiting_for_auth_code = State()
    waiting_for_auth_password = State()


@router.message(Command("parse"))
async def cmd_parse(message: Message, state: FSMContext):
    """Начало процесса парсинга."""
    await message.answer(
        "🔍 <b>Парсинг чата</b>\n\n"
        "Выбери чат из списка или введи invite-ссылку вручную:\n\n"
        "Примеры:\n"
        "• https://t.me/+AAAA\n"
        "• https://t.me/joinchat/AAAA",
        parse_mode=ParseMode.HTML,
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Выбрать из моих чатов", callback_data="parse_choose_list")]
            ]
        ),
    )
    await message.answer("⬇️ Быстрое меню всегда доступно снизу.", reply_markup=get_persistent_menu())
    await state.set_state(ParseStates.waiting_for_chat)


@router.message(ParseStates.waiting_for_chat)
async def process_chat_input(message: Message, state: FSMContext):
    """Обработка ввода чата."""
    chat_input = (message.text or "").strip()

    if not chat_input:
        await message.answer("❌ Пустой ввод. Попробуй ещё раз:")
        return
    
    # Разрешаем только invite-ссылки (по запросу пользователя).
    if not (chat_input.startswith("https://t.me/+") or chat_input.startswith("https://t.me/joinchat/")):
        await message.answer(
            "❌ Сейчас поддерживается только invite-ссылка.\n"
            "Используй кнопку «Выбрать из моих чатов» или пришли ссылку вида "
            "https://t.me/+... / https://t.me/joinchat/..."
        )
        return
    
    await state.update_data(chat_input=chat_input)
    status_msg = await message.answer("⏳ Подключение к Telegram...")

    try:
        await run_parse_flow(message, state, chat_input, status_msg)
    except AuthCodeRequiredError:
        await parser.request_login_code()
        await state.update_data(pending_action="parse_chat")
        await status_msg.edit_text(
            "🔐 Telethon не авторизован.\n"
            "Введи код из Telegram/SMS одним сообщением."
        )
        await state.set_state(ParseStates.waiting_for_auth_code)
    except (ValueError, ParseChatError) as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")
        await state.clear()
    except Exception as e:
        await status_msg.edit_text(f"❌ Произошла ошибка: {e}")
        await state.clear()


@router.callback_query(F.data == "parse_choose_list")
async def choose_chat_list(callback: CallbackQuery, state: FSMContext):
    """Показать список доступных чатов аккаунта."""
    status_msg = await callback.message.answer("⏳ Загружаю список чатов...")
    try:
        chats = await parser.list_available_chats(limit=100)
    except AuthCodeRequiredError:
        await parser.request_login_code()
        await state.update_data(pending_action="list_chats")
        await status_msg.edit_text(
            "🔐 Telethon не авторизован.\n"
            "Введи код из Telegram/SMS одним сообщением."
        )
        await state.set_state(ParseStates.waiting_for_auth_code)
        await callback.answer()
        return
    except Exception as e:
        await status_msg.edit_text(f"❌ Не удалось получить список чатов: {e}")
        await callback.answer()
        return

    if not chats:
        await status_msg.edit_text("⚠️ Не найдено чатов для парсинга.")
        await callback.answer()
        return

    chats_data = [chat.__dict__ for chat in chats]
    await state.update_data(available_chats=chats_data, chats_page=0)
    await status_msg.edit_text(
        "📋 <b>Доступные чаты</b>\nВыбери чат для парсинга:",
        parse_mode=ParseMode.HTML,
        reply_markup=build_chats_keyboard(chats_data, page=0),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("parse_page:"))
async def parse_page(callback: CallbackQuery, state: FSMContext):
    """Пагинация списка чатов."""
    data = await state.get_data()
    chats = data.get("available_chats") or []
    if not chats:
        await callback.answer("Список чатов устарел, открой /parse снова.", show_alert=True)
        return
    page = int(callback.data.split(":")[1])
    await state.update_data(chats_page=page)
    await callback.message.edit_reply_markup(reply_markup=build_chats_keyboard(chats, page))
    await callback.answer()


@router.callback_query(F.data.startswith("parse_pick:"))
async def parse_pick(callback: CallbackQuery, state: FSMContext):
    """Запуск парсинга по выбору из списка чатов."""
    data = await state.get_data()
    chats = data.get("available_chats") or []
    idx = int(callback.data.split(":")[1])
    if idx < 0 or idx >= len(chats):
        await callback.answer("Чат не найден в текущем списке.", show_alert=True)
        return

    selected = chats[idx]
    dialog_id = selected["dialog_id"]
    title = selected["title"]
    status_msg = await callback.message.answer(f"⏳ Выбран чат: <b>{title}</b>\nЗапускаю парсинг...", parse_mode=ParseMode.HTML)

    await callback.answer()
    try:
        await run_parse_flow_by_dialog_id(callback.message, state, dialog_id, status_msg)
    except ParseChatError as e:
        await status_msg.edit_text(f"❌ {e}")
        await state.clear()
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при парсинге: {e}")
        await state.clear()


@router.message(ParseStates.waiting_for_auth_code)
async def process_auth_code(message: Message, state: FSMContext):
    """Ввод кода Telethon через бота."""
    code = (message.text or "").strip().replace(" ", "")
    if not code:
        await message.answer("❌ Код пустой. Введи код из Telegram/SMS.")
        return

    try:
        await parser.sign_in_with_code(code)
    except AuthPasswordRequiredError:
        await message.answer("🔒 Включена 2FA. Введи пароль Telegram одним сообщением.")
        await state.set_state(ParseStates.waiting_for_auth_password)
        return
    except Exception as e:
        await message.answer(f"❌ Не удалось авторизоваться: {e}")
        return

    data = await state.get_data()
    pending_action = data.get("pending_action")
    if pending_action == "list_chats":
        await state.update_data(pending_action=None)
        status_msg = await message.answer("✅ Авторизация прошла. Загружаю список чатов...")
        chats = await parser.list_available_chats(limit=100)
        if not chats:
            await status_msg.edit_text("⚠️ Не найдено чатов для парсинга.")
            await state.clear()
            return
        await state.update_data(available_chats=[chat.__dict__ for chat in chats], chats_page=0)
        await status_msg.edit_text(
            "📋 <b>Доступные чаты</b>\nВыбери чат для парсинга:",
            parse_mode=ParseMode.HTML,
            reply_markup=build_chats_keyboard([chat.__dict__ for chat in chats], page=0),
        )
        return

    chat_input = data.get("chat_input")
    if not chat_input:
        await message.answer("✅ Авторизация прошла. Введи чат заново через /parse.")
        await state.clear()
        return

    status_msg = await message.answer("✅ Авторизация прошла. Продолжаю парсинг...")
    try:
        await run_parse_flow(message, state, chat_input, status_msg)
    except ParseChatError as e:
        await message.answer(f"❌ {e}")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка при парсинге: {e}")


@router.message(ParseStates.waiting_for_auth_password)
async def process_auth_password(message: Message, state: FSMContext):
    """Ввод пароля 2FA Telethon через бота."""
    password = (message.text or "").strip()
    if not password:
        await message.answer("❌ Пароль пустой. Введи пароль Telegram.")
        return
    try:
        await parser.sign_in_with_password(password)
        data = await state.get_data()
        pending_action = data.get("pending_action")
        if pending_action == "list_chats":
            await state.update_data(pending_action=None)
            status_msg = await message.answer("✅ 2FA подтвержден. Загружаю список чатов...")
            chats = await parser.list_available_chats(limit=100)
            if not chats:
                await status_msg.edit_text("⚠️ Не найдено чатов для парсинга.")
                await state.clear()
                return
            await state.update_data(available_chats=[chat.__dict__ for chat in chats], chats_page=0)
            await status_msg.edit_text(
                "📋 <b>Доступные чаты</b>\nВыбери чат для парсинга:",
                parse_mode=ParseMode.HTML,
                reply_markup=build_chats_keyboard([chat.__dict__ for chat in chats], page=0),
            )
            return

        chat_input = data.get("chat_input")
        if not chat_input:
            await message.answer("✅ Авторизация прошла. Введи чат заново через /parse.")
            await state.clear()
            return
        status_msg = await message.answer("✅ 2FA подтвержден. Продолжаю парсинг...")
        await run_parse_flow(message, state, chat_input, status_msg)
    except ParseChatError as e:
        await message.answer(f"❌ {e}")
        await state.clear()
    except Exception as e:
        await message.answer(f"❌ Ошибка 2FA: {e}")


async def run_parse_flow(message: Message, state: FSMContext, chat_input: str, status_msg: Message):
    """Общий сценарий парсинга после авторизации."""
    await parser.get_me()
    await status_msg.edit_text("✅ Подключение установлено!\n🔄 Получение участников чата...")

    progress_msg = await message.answer("📊 Сбор данных: 0%")

    async def update_progress(current: int, total: int):
        percent = int((current / total) * 100) if total > 0 else 0
        try:
            await progress_msg.edit_text(f"📊 Сбор данных: {percent}% ({current}/{total})")
        except Exception:
            pass

    users, chat_title = await parser.parse_chat(chat_input, update_progress)

    if not users:
        await status_msg.edit_text(
            "⚠️ Участники не найдены. Возможно, чат приватный или в нём нет участников.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🔄 Попробовать снова", callback_data="retry_parse")
            ]])
        )
        await state.clear()
        return

    await progress_msg.edit_text(f"✅ Найдено {len(users)} участников!\n📁 Создание Excel файла...")
    filepath = exporter.export(users, chat_title)

    save_parsing_session_sync(
        chat_username=chat_input,
        chat_title=chat_title,
        user_count=len(users),
        file_path=str(filepath),
        status="completed"
    )

    await progress_msg.edit_text("📤 Отправка файла...")
    await message.answer_document(
        document=FSInputFile(str(filepath)),
        caption=f"✅ <b>Парсинг завершён!</b>\n\n"
                f"📌 Чаt: {chat_title}\n"
                f"👥 Участников: {len(users)}\n"
                f"📁 Файл: {filepath.name}",
        parse_mode=ParseMode.HTML
    )
    await state.clear()


async def run_parse_flow_by_dialog_id(message: Message, state: FSMContext, dialog_id: int, status_msg: Message):
    """Сценарий парсинга по выбранному чату из списка."""
    await parser.get_me()
    await status_msg.edit_text("✅ Подключение установлено!\n🔄 Получение участников чата...")
    progress_msg = await message.answer("📊 Сбор данных: 0%")

    async def update_progress(current: int, total: int):
        percent = int((current / total) * 100) if total > 0 else 0
        try:
            await progress_msg.edit_text(f"📊 Сбор данных: {percent}% ({current}/{total})")
        except Exception:
            pass

    users, chat_title = await parser.parse_chat_by_dialog_id(dialog_id, update_progress)
    if not users:
        await status_msg.edit_text("⚠️ Участники не найдены.")
        await state.clear()
        return

    await progress_msg.edit_text(f"✅ Найдено {len(users)} участников!\n📁 Создание Excel файла...")
    filepath = exporter.export(users, chat_title)
    save_parsing_session_sync(
        chat_username=f"dialog:{dialog_id}",
        chat_title=chat_title,
        user_count=len(users),
        file_path=str(filepath),
        status="completed"
    )
    await progress_msg.edit_text("📤 Отправка файла...")
    await message.answer_document(
        document=FSInputFile(str(filepath)),
        caption=f"✅ <b>Парсинг завершён!</b>\n\n"
                f"📌 Чаt: {chat_title}\n"
                f"👥 Участников: {len(users)}\n"
                f"📁 Файл: {filepath.name}",
        parse_mode=ParseMode.HTML
    )
    await state.clear()


def build_chats_keyboard(chats: list, page: int) -> InlineKeyboardMarkup:
    """Клавиатура списка чатов с пагинацией."""
    total = len(chats)
    max_page = (total - 1) // CHATS_PAGE_SIZE
    page = max(0, min(page, max_page))
    start = page * CHATS_PAGE_SIZE
    end = min(start + CHATS_PAGE_SIZE, total)

    rows = []
    for idx in range(start, end):
        item = chats[idx]
        title = item["title"]
        username = item.get("username")
        label = f"{title}"
        if username:
            label = f"{title} (@{username})"
        if len(label) > 56:
            label = f"{label[:53]}..."
        rows.append([InlineKeyboardButton(text=label, callback_data=f"parse_pick:{idx}")])

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"parse_page:{page - 1}"))
    if page < max_page:
        nav.append(InlineKeyboardButton(text="Вперёд ➡️", callback_data=f"parse_page:{page + 1}"))
    if nav:
        rows.append(nav)

    rows.append([InlineKeyboardButton(text="✍️ Ввести ссылку вручную", callback_data="retry_parse")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@router.callback_query(F.data == "retry_parse")
async def retry_parse(callback, state: FSMContext):
    """Повторный парсинг."""
    await callback.message.answer(
        "🔍 Введи invite-ссылку чата:\n"
        "• https://t.me/+...\n"
        "• https://t.me/joinchat/..."
    )
    await state.set_state(ParseStates.waiting_for_chat)
    await callback.answer()

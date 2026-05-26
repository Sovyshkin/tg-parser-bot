"""Парсер пользователей из Telegram."""

from dataclasses import dataclass
from typing import List, Optional, Callable, Awaitable

from telethon import TelegramClient
from telethon.errors import (
    FloodWaitError,
    InviteHashExpiredError,
    InviteHashInvalidError,
    InviteRequestSentError,
    RPCError,
    SessionPasswordNeededError,
    UserAlreadyParticipantError,
)
from telethon.tl.functions.messages import CheckChatInviteRequest, ImportChatInviteRequest
from telethon.sessions import StringSession
from telethon.tl.types import User
from telethon.utils import parse_username

from bot.config import config
from bot.security import ensure_secure_dir, ensure_secure_file, get_or_create_key
from cryptography.fernet import Fernet


@dataclass
class ParsedUser:
    """Данные спарсенного пользователя."""
    user_id: int
    username: Optional[str]
    first_name: Optional[str]
    last_name: Optional[str]
    phone: Optional[str]
    is_bot: bool
    
    def to_dict(self) -> dict:
        return {
            "ID": self.user_id,
            "Username": f"@{self.username}" if self.username else "",
            "Имя": self.first_name or "",
            "Фамилия": self.last_name or "",
            "Телефон": self.phone or "",
            "Бот": "Да" if self.is_bot else "Нет"
        }


@dataclass
class AvailableChat:
    """Чат/канал, доступный для парсинга."""
    dialog_id: int
    title: str
    username: Optional[str]


class AuthCodeRequiredError(RuntimeError):
    """Нужно ввести код подтверждения Telegram."""


class AuthPasswordRequiredError(RuntimeError):
    """Нужен пароль двухфакторной аутентификации."""


class ParseChatError(RuntimeError):
    """Понятная для пользователя ошибка парсинга."""


class TelegramParser:
    """Парсер пользователей из Telegram чатов."""
    
    def __init__(self):
        self.client: Optional[TelegramClient] = None
        self._phone_code_hash: Optional[str] = None
        self._session_enc_path = config.telethon.session_path.with_suffix(".session.enc")
        self._key_path = config.telethon.session_path.parent / ".session.key"

    def _encryptor(self) -> Fernet:
        key = get_or_create_key(self._key_path)
        return Fernet(key)

    def _load_session_string(self) -> str:
        """Чтение и расшифровка StringSession из файла."""
        ensure_secure_dir(self._session_enc_path.parent)
        if not self._session_enc_path.exists():
            return ""
        token = self._session_enc_path.read_bytes()
        ensure_secure_file(self._session_enc_path)
        return self._encryptor().decrypt(token).decode("utf-8")

    def _save_session_string(self) -> None:
        """Сохранение и шифрование текущего StringSession."""
        if self.client is None:
            return
        raw = self.client.session.save()
        if not raw:
            return
        ensure_secure_dir(self._session_enc_path.parent)
        enc = self._encryptor().encrypt(raw.encode("utf-8"))
        self._session_enc_path.write_bytes(enc)
        ensure_secure_file(self._session_enc_path)

    @staticmethod
    def _normalize_phone(phone: Optional[str]) -> str:
        """Оставляет только цифры в номере для корректного сравнения."""
        if not phone:
            return ""
        return "".join(ch for ch in str(phone) if ch.isdigit())
    
    async def connect(self) -> TelegramClient:
        """Подключение к Telegram."""
        if self.client is None:
            ensure_secure_dir(config.telethon.session_path.parent)
            session_string = self._load_session_string()
            self.client = TelegramClient(
                StringSession(session_string),
                config.telethon.api_id,
                config.telethon.api_hash
            )
            await self.client.connect()
            self._save_session_string()
        return self.client

    async def ensure_authorized(self):
        """Проверка авторизации пользователя Telethon."""
        client = await self.connect()
        if not await client.is_user_authorized():
            raise AuthCodeRequiredError("Telethon не авторизован")
        me = await client.get_me()
        active_phone = self._normalize_phone(getattr(me, "phone", None))
        env_phone = self._normalize_phone(config.telethon.phone)
        if env_phone and active_phone and active_phone != env_phone:
            await self.disconnect()
            self._phone_code_hash = None
            raise AuthCodeRequiredError(
                "Обнаружена сессия другого номера. "
                "Начни заново: бот запросит код для номера из .env."
            )

    async def request_login_code(self):
        """Запрос кода входа Telegram."""
        client = await self.connect()
        sent = await client.send_code_request(config.telethon.phone)
        self._phone_code_hash = sent.phone_code_hash

    async def sign_in_with_code(self, code: str):
        """Вход по коду Telegram."""
        client = await self.connect()
        if not self._phone_code_hash:
            await self.request_login_code()
        try:
            await client.sign_in(
                phone=config.telethon.phone,
                code=code,
                phone_code_hash=self._phone_code_hash,
            )
            self._phone_code_hash = None
            self._save_session_string()
        except SessionPasswordNeededError as exc:
            raise AuthPasswordRequiredError("Требуется пароль 2FA") from exc

    async def sign_in_with_password(self, password: str):
        """Вход с паролем 2FA."""
        client = await self.connect()
        await client.sign_in(password=password)
        self._save_session_string()
    
    async def disconnect(self):
        """Отключение от Telegram."""
        if self.client:
            self._save_session_string()
            await self.client.disconnect()
            self.client = None
    
    async def parse_chat(
        self,
        chat_identifier: str,
        progress_callback: Optional[Callable[[int, int], Awaitable]] = None
    ) -> tuple[List[ParsedUser], str]:
        """
        Парсинг пользователей из чата.
        
        Args:
            chat_identifier: invite-ссылка t.me/+... или t.me/joinchat/...
            progress_callback: колбэк для прогресса (текущее, всего)
        
        Returns:
            Кортеж (список пользователей, название чата)
        """
        client = await self.connect()
        
        # Получаем чат
        chat_input = chat_identifier.strip()
        parsed, is_invite = parse_username(chat_input)
        try:
            if not parsed:
                raise ParseChatError(
                    "Не удалось распознать invite-ссылку.\n"
                    "Отправь ссылку вида https://t.me/+... или https://t.me/joinchat/..."
                )

            if is_invite:
                # 1) Сначала проверяем ссылку без попытки вступления.
                check = await client(CheckChatInviteRequest(parsed))
                check_chat = getattr(check, "chat", None)
                if check_chat is not None:
                    # Уже участник (или чат доступен без вступления)
                    chat = check_chat
                else:
                    # 2) Если не участник — пробуем вступить по invite.
                    chat = None
                    try:
                        result = await client(ImportChatInviteRequest(parsed))
                        if getattr(result, "chats", None):
                            chat = result.chats[0]
                    except UserAlreadyParticipantError:
                        # Гонка состояния: уже участник.
                        check_after = await client(CheckChatInviteRequest(parsed))
                        chat = getattr(check_after, "chat", None)
                    except InviteRequestSentError:
                        raise ParseChatError(
                            "Заявка в чат отправлена и ожидает одобрения.\n"
                            "Пока админ не одобрит, участников получить нельзя."
                        )

                    if chat is None:
                        raise ParseChatError(
                            "Не получилось получить доступ к чату по ссылке.\n"
                            "Открой чат вручную в Telegram этим аккаунтом и попробуй снова."
                        )
            else:
                raise ParseChatError(
                    "Сейчас поддерживаются только invite-ссылки.\n"
                    "Используй https://t.me/+... или https://t.me/joinchat/..."
                )
        except (InviteHashInvalidError, InviteHashExpiredError):
            raise ParseChatError(
                "Ссылка-приглашение недействительна или устарела."
            )
        except FloodWaitError as e:
            raise ParseChatError(
                f"Telegram временно ограничил запросы. Подожди {e.seconds} сек и запусти снова."
            )
        except RPCError as e:
            text = str(e)
            if "FROZEN_METHOD_INVALID" in text:
                raise ParseChatError(
                    "Telegram временно ограничил это действие для аккаунта.\n"
                    "Попробуй выбрать чат из «Моих чатов» или подожди и повтори позже."
                )
            if "INVITE_REQUEST_SENT" in text:
                raise ParseChatError(
                    "Заявка в чат отправлена и ожидает одобрения.\n"
                    "Пока админ не одобрит, участников получить нельзя."
                )
            raise ParseChatError(f"Ошибка Telegram: {text}")
        except ValueError:
            raise ParseChatError(
                f"Чат не найден: {chat_identifier}\n"
                "Если это приватный чат, сначала открой его в Telegram этим аккаунтом."
            )
        
        return await self._parse_entity(chat, progress_callback)

    async def list_available_chats(self, limit: int = 30) -> List[AvailableChat]:
        """Список чатов/каналов пользователя для выбора в боте."""
        await self.ensure_authorized()
        client = await self.connect()
        chats: List[AvailableChat] = []

        async for dialog in client.iter_dialogs(limit=limit):
            entity = dialog.entity
            if getattr(entity, "broadcast", False):
                continue
            title = dialog.name or getattr(entity, "title", None) or str(dialog.id)
            chats.append(
                AvailableChat(
                    dialog_id=dialog.id,
                    title=title,
                    username=getattr(entity, "username", None),
                )
            )
        return chats

    async def parse_chat_by_dialog_id(
        self,
        dialog_id: int,
        progress_callback: Optional[Callable[[int, int], Awaitable]] = None
    ) -> tuple[List[ParsedUser], str]:
        """Парсинг выбранного диалога по его ID из списка диалогов."""
        await self.ensure_authorized()
        client = await self.connect()
        async for dialog in client.iter_dialogs():
            if int(dialog.id) == int(dialog_id):
                return await self._parse_entity(dialog.entity, progress_callback)
        raise ValueError("Выбранный чат не найден в списке диалогов")

    async def _parse_entity(
        self,
        chat,
        progress_callback: Optional[Callable[[int, int], Awaitable]] = None
    ) -> tuple[List[ParsedUser], str]:
        """Общий парсинг участников по entity."""
        client = await self.connect()
        chat_title = getattr(chat, 'title', None) or getattr(chat, 'username', None) or str(chat.id)

        users: List[ParsedUser] = []

        try:
            participants = await client.get_participants(chat, aggressive=True)

            total = len(participants)
            for i, participant in enumerate(participants):
                if isinstance(participant, User) and not participant.deleted:
                    user = ParsedUser(
                        user_id=participant.id,
                        username=participant.username,
                        first_name=participant.first_name,
                        last_name=participant.last_name,
                        phone=participant.phone if hasattr(participant, 'phone') else None,
                        is_bot=participant.bot
                    )
                    users.append(user)
                
                if progress_callback and (i + 1) % 50 == 0:
                    await progress_callback(i + 1, total)
            
            if progress_callback:
                await progress_callback(total, total)

        except FloodWaitError as e:
            raise ParseChatError(
                f"Telegram ограничил частые запросы. Подожди {e.seconds} сек и попробуй снова."
            )
        except RPCError as e:
            text = str(e)
            if "CHAT_ADMIN_REQUIRED" in text:
                raise ParseChatError(
                    "В этом чате список участников скрыт.\n"
                    "Нужны права администратора или другой чат."
                )
            if "CHANNEL_PRIVATE" in text:
                raise ParseChatError(
                    "Это приватный чат/канал без доступа для текущего аккаунта."
                )
            raise ParseChatError(f"Не удалось получить участников: {text}")
        except Exception as e:
            raise ParseChatError(f"Не удалось получить участников: {e}")

        return users, chat_title
    
    async def get_me(self) -> Optional[User]:
        """Получение информации о текущем пользователе."""
        await self.ensure_authorized()
        client = await self.connect()
        return await client.get_me()


# Глобальный экземпляр парсера
parser = TelegramParser()

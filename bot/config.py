"""Конфигурация бота."""

from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import os
from bot.security import ensure_secure_dir


@dataclass
class BotConfig:
    """Конфигурация Telegram Bot API."""
    token: str


@dataclass
class TelethonConfig:
    """Конфигурация Telethon Client."""
    api_id: int
    api_hash: str
    phone: str
    session_path: Path


@dataclass
class Config:
    """Общая конфигурация."""
    bot: BotConfig
    telethon: TelethonConfig
    exports_dir: Path


def load_config() -> Config:
    """Загрузка конфигурации из переменных окружения."""
    
    bot_token = os.getenv("BOT_TOKEN")
    if not bot_token:
        raise ValueError("BOT_TOKEN не найден в переменных окружения")
    
    api_id = os.getenv("API_ID")
    api_hash = os.getenv("API_HASH")
    phone = os.getenv("PHONE")
    
    if not api_id or not api_hash or not phone:
        raise ValueError("API_ID, API_HASH и PHONE должны быть указаны")
    
    base_dir = Path(__file__).parent.parent
    sessions_dir = base_dir / "sessions"
    exports_dir = base_dir / "exports"
    
    ensure_secure_dir(sessions_dir)
    exports_dir.mkdir(exist_ok=True)
    
    phone_digits = "".join(ch for ch in phone if ch.isdigit())
    session_name = f"user_session_{phone_digits}" if phone_digits else "user_session_default"

    return Config(
        bot=BotConfig(token=bot_token),
        telethon=TelethonConfig(
            api_id=int(api_id),
            api_hash=api_hash,
            phone=phone,
            session_path=sessions_dir / session_name
        ),
        exports_dir=exports_dir
    )


config = load_config()

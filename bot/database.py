"""База данных для хранения истории парсинга."""

from datetime import datetime
from typing import Optional

from sqlalchemy import create_engine, String, Integer, DateTime, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker

from bot.config import config


class Base(DeclarativeBase):
    """Базовая модель SQLAlchemy."""
    pass


class ParsingSession(Base):
    """Сессия парсинга."""
    __tablename__ = "parsing_sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    chat_username: Mapped[str] = mapped_column(String(255))
    chat_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    file_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="completed")


# Синхронный движок для миграций
sync_engine = create_engine(f"sqlite:///{config.exports_dir / 'parsing_history.db'}")
SyncSession = sessionmaker(sync_engine)

# Асинхронный движок для работы бота
async_engine = create_async_engine(
    f"sqlite+aiosqlite:///{config.exports_dir / 'parsing_history.db'}"
)
AsyncSessionLocal = async_sessionmaker(async_engine, class_=AsyncSession)


async def init_db():
    """Инициализация базы данных."""
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def save_parsing_session_sync(
    chat_username: str,
    chat_title: Optional[str],
    user_count: int,
    file_path: str,
    status: str = "completed"
) -> int:
    """Сохранение сессии парсинга (синхронно)."""
    with SyncSession() as session:
        session_obj = ParsingSession(
            chat_username=chat_username,
            chat_title=chat_title,
            user_count=user_count,
            file_path=file_path,
            status=status
        )
        session.add(session_obj)
        session.commit()
        return session_obj.id


async def get_parsing_history(limit: int = 10):
    """Получение истории парсинга."""
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(ParsingSession)
            .order_by(ParsingSession.created_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
"""Утилиты безопасности: права доступа, шифрование, маскирование логов."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet


def ensure_secure_dir(path: Path) -> None:
    """Создает директорию и ставит права только для владельца (700)."""
    path.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(path, 0o700)
    except PermissionError:
        logging.getLogger(__name__).warning(
            "Не удалось установить права 700 для %s", path
        )


def ensure_secure_file(path: Path) -> None:
    """Ставит права только для владельца (600), если файл существует."""
    if path.exists():
        try:
            os.chmod(path, 0o600)
        except PermissionError:
            logging.getLogger(__name__).warning(
                "Не удалось установить права 600 для %s", path
            )


def get_or_create_key(key_file: Path) -> bytes:
    """Возвращает ключ Fernet, создавая его при первом запуске."""
    key_file.parent.mkdir(parents=True, exist_ok=True)
    ensure_secure_dir(key_file.parent)
    if key_file.exists():
        key = key_file.read_bytes().strip()
        ensure_secure_file(key_file)
        return key

    key = Fernet.generate_key()
    key_file.write_bytes(key)
    ensure_secure_file(key_file)
    return key


class SensitiveDataFilter(logging.Filter):
    """Маскирует телефоны, токены, коды и пароли в логах."""

    TOKEN_RE = re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b")
    PHONE_RE = re.compile(r"(?<!\d)(\+?\d[\d\-\s()]{8,}\d)(?!\d)")
    KV_RE = re.compile(r"(?i)\b(phone|password|code|token)\b\s*[:=]\s*([^\s,;]+)")

    @staticmethod
    def _mask_phone(raw: str) -> str:
        digits = "".join(ch for ch in raw if ch.isdigit())
        if len(digits) < 7:
            return "***"
        return f"+{digits[:2]}***{digits[-2:]}"

    def _sanitize(self, message: str) -> str:
        sanitized = self.TOKEN_RE.sub("[REDACTED_TOKEN]", message)
        sanitized = self.KV_RE.sub(lambda m: f"{m.group(1)}=[REDACTED]", sanitized)
        sanitized = self.PHONE_RE.sub(lambda m: self._mask_phone(m.group(1)), sanitized)
        return sanitized

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            original = record.getMessage()
            sanitized = self._sanitize(original)
            record.msg = sanitized
            record.args = ()
        except Exception:
            pass
        return True


def add_sensitive_log_filter(logger: Optional[logging.Logger] = None) -> None:
    """Подключает фильтр ко всем хендлерам root-логгера."""
    root = logger or logging.getLogger()
    data_filter = SensitiveDataFilter()
    for handler in root.handlers:
        handler.addFilter(data_filter)

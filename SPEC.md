# TG Parsing Bot - Спецификация

## Концепция и Видение

Удобный Telegram-бот для быстрого сбора никнеймов пользователей из открытых групп, чатов и каналов с мгновенным экспортом в Excel. Минималистичный интерфейс, понятный даже новичкам.

## Стек технологий

- **Python 3.10+**
- **Aiogram 3** - Telegram Bot API
- **Telethon** - Telegram Client API (для парсинга)
- **Pandas + OpenPyXL** - генерация Excel
- **SQLite** - хранение данных
- **SQLAlchemy** - ORM

## Функционал

### Команды бота:
- `/start` - Приветствие и помощь
- `/help` - Список команд
- `/parse` - Начать парсинг (список group_id)
- `/history` - История парсингов
- `/settings` - Настройки (формат файла)

### Процесс парсинга:
1. Пользователь вводит username/ссылку группы
2. Бот подключается через Telethon сессию
3. Собирает: user_id, username, first_name, last_name, phone (если доступно)
4. Формирует Excel с автофильтрами
5. Отправляет файл пользователю

## Структура проекта

```
tg-parsing-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py           # Точка входа
│   ├── config.py         # Конфигурация
│   ├── database.py       # SQLite модели
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py
│   │   ├── parse.py
│   │   └── history.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── parser.py     # Логика парсинга
│   │   └── exporter.py   # Excel экспорт
│   └── keyboards/
│       ├── __init__.py
│       └── inline.py
├── sessions/             # Telethon сессии
├── exports/             # Excel файлы
├── requirements.txt
└── README.md
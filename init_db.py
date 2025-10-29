"""
Скрипт для инициализации базы данных (создание таблиц)
Используется для локальной разработки
"""
import asyncio
from database.database import init_db


async def main():
    print("🔄 Инициализация базы данных...")
    await init_db()
    print("✅ База данных успешно инициализирована!")
    print("\nТеперь можно запустить бота: python -m bot.main")


if __name__ == "__main__":
    asyncio.run(main())


"""
Главный файл бота - точка входа
"""
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import config
from database.database import async_session_maker, init_db, close_db
from database.models import UserRole
from database.crud import create_user, get_user_by_telegram_id
from bot.middlewares.auth_middleware import AuthMiddleware

# Импортируем все роутеры
from bot.handlers import start, objects, add_object, expenses, reports, admin, company_expenses

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)
logger = logging.getLogger(__name__)


# Middleware для добавления сессии БД
class DatabaseMiddleware:
    """Middleware для добавления сессии БД в контекст"""
    
    async def __call__(self, handler, event, data):
        async with async_session_maker() as session:
            data["session"] = session
            return await handler(event, data)


async def set_bot_commands(bot: Bot):
    """Установка команд бота"""
    commands = [
        BotCommand(command="start", description="🏠 Главное меню"),
        BotCommand(command="help", description="❓ Справка"),
        BotCommand(command="add_object", description="➕ Добавить объект (админ)"),
        BotCommand(command="add_user", description="👤 Добавить пользователя (админ)"),
        BotCommand(command="list_users", description="👥 Список пользователей (админ)"),
    ]
    
    await bot.set_my_commands(commands)
    logger.info("✅ Команды бота установлены")


async def initialize_admins():
    """Инициализация админов из конфигурации"""
    if not config.ADMIN_TELEGRAM_IDS:
        logger.warning("⚠️ ADMIN_TELEGRAM_IDS не настроен - не будет начальных админов")
        return
    
    async with async_session_maker() as session:
        for telegram_id in config.ADMIN_TELEGRAM_IDS:
            # Проверяем, существует ли пользователь
            existing_user = await get_user_by_telegram_id(session, telegram_id)
            
            if not existing_user:
                # Создаем админа
                await create_user(
                    session=session,
                    telegram_id=telegram_id,
                    role=UserRole.ADMIN,
                    username=None,
                    full_name="Администратор"
                )
                logger.info(f"✅ Создан администратор с ID: {telegram_id}")
            elif existing_user.role != UserRole.ADMIN:
                # Обновляем роль на админа
                existing_user.role = UserRole.ADMIN
                await session.commit()
                logger.info(f"✅ Пользователь {telegram_id} повышен до администратора")


async def main():
    """Главная функция запуска бота"""
    
    # Валидация конфигурации
    logger.info("🔍 Проверка конфигурации...")
    if not config.validate():
        logger.error("❌ Ошибка конфигурации. Проверьте переменные окружения.")
        return
    
    logger.info("✅ Конфигурация валидна")
    
    # Инициализация базы данных
    logger.info("📦 Инициализация базы данных...")
    await init_db()
    
    # Инициализация админов
    logger.info("👑 Инициализация администраторов...")
    await initialize_admins()
    
    # Создание бота и диспетчера
    bot = Bot(token=config.BOT_TOKEN)
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    # Регистрация middleware
    # DatabaseMiddleware должен быть первым
    dp.message.middleware(DatabaseMiddleware())
    dp.callback_query.middleware(DatabaseMiddleware())
    
    # AuthMiddleware для проверки доступа
    dp.message.middleware(AuthMiddleware())
    dp.callback_query.middleware(AuthMiddleware())
    
    # Регистрация роутеров
    dp.include_router(start.router)
    dp.include_router(objects.router)
    dp.include_router(add_object.router)
    dp.include_router(expenses.router)
    dp.include_router(reports.router)
    dp.include_router(admin.router)
    dp.include_router(company_expenses.router)
    
    logger.info("✅ Роутеры зарегистрированы")
    
    # Установка команд бота
    await set_bot_commands(bot)
    
    # Запуск бота
    logger.info("🚀 Бот запущен и готов к работе!")
    
    try:
        # Удаляем вебхуки если есть и запускаем polling
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        # Закрытие соединений
        logger.info("🛑 Остановка бота...")
        await close_db()
        await bot.session.close()
        logger.info("✅ Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("⚠️ Бот остановлен пользователем (Ctrl+C)")
    except Exception as e:
        logger.error(f"❌ Критическая ошибка: {e}", exc_info=True)




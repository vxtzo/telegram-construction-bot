"""
Подключение к базе данных и создание сессий
"""
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import NullPool
from bot.config import config
from database.models import Base


# Преобразуем DATABASE_URL для async работы
database_url = config.DATABASE_URL
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
elif database_url.startswith("postgres://"):
    database_url = database_url.replace("postgres://", "postgresql+asyncpg://", 1)

# Создаем async engine
engine = create_async_engine(
    database_url,
    echo=False,  # Установить True для debug SQL запросов
    poolclass=NullPool,  # Для Railway и других платформ с ограничениями на подключения
)

# Создаем фабрику сессий
async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_session() -> AsyncSession:
    """
    Получить сессию базы данных
    
    Использование:
        async with get_session() as session:
            # работа с БД
    """
    async with async_session_maker() as session:
        yield session


async def init_db():
    """Инициализация базы данных - создание всех таблиц"""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Fallback: добавляем enum значения если их нет
        await conn.execute(sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type t 
                    JOIN pg_enum e ON e.enumtypid = t.oid
                    WHERE t.typname = 'filetype' AND e.enumlabel = 'estimate'
                ) THEN
                    ALTER TYPE filetype ADD VALUE 'estimate';
                END IF;
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END;
            $$;
        """))
        
        await conn.execute(sa.text("""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_type t 
                    JOIN pg_enum e ON e.enumtypid = t.oid
                    WHERE t.typname = 'filetype' AND e.enumlabel = 'payroll'
                ) THEN
                    ALTER TYPE filetype ADD VALUE 'payroll';
                END IF;
            EXCEPTION WHEN duplicate_object THEN
                NULL;
            END;
            $$;
        """))
    print("✅ База данных инициализирована")


async def close_db():
    """Закрытие подключения к базе данных"""
    await engine.dispose()
    print("✅ Подключение к базе данных закрыто")



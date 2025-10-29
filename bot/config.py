"""
Конфигурация бота - загрузка переменных окружения
"""
import os
import json
from typing import List
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()


class Config:
    """Класс конфигурации приложения"""
    
    # Telegram Bot
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    
    # Database
    DATABASE_URL: str = os.getenv("DATABASE_URL", "postgresql://localhost/construction_bot")
    
    # Admin users
    ADMIN_TELEGRAM_IDS: List[int] = []
    
    def __init__(self):
        """Инициализация конфигурации"""
        # Парсинг admin IDs
        admin_ids_str = os.getenv("ADMIN_TELEGRAM_IDS", "")
        if admin_ids_str:
            try:
                self.ADMIN_TELEGRAM_IDS = [int(id.strip()) for id in admin_ids_str.split(",")]
            except ValueError:
                print("⚠️ Ошибка парсинга ADMIN_TELEGRAM_IDS")
                self.ADMIN_TELEGRAM_IDS = []
    
    def validate(self) -> bool:
        """Проверка наличия всех необходимых переменных"""
        errors = []
        
        if not self.BOT_TOKEN:
            errors.append("❌ BOT_TOKEN не установлен")
        
        if not self.OPENAI_API_KEY:
            errors.append("❌ OPENAI_API_KEY не установлен")
        
        if not self.DATABASE_URL:
            errors.append("❌ DATABASE_URL не установлен")
        
        if not self.ADMIN_TELEGRAM_IDS:
            errors.append("⚠️ ADMIN_TELEGRAM_IDS не установлен")
        
        if errors:
            print("\n".join(errors))
            return False
        
        return True


# Глобальный экземпляр конфигурации
config = Config()


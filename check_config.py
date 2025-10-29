"""
Скрипт для проверки конфигурации бота
Запустите перед первым запуском бота
"""
from bot.config import config


def check_config():
    """Проверка всех переменных конфигурации"""
    
    print("🔍 Проверка конфигурации бота...\n")
    print("=" * 60)
    
    # Проверка BOT_TOKEN
    if config.BOT_TOKEN:
        print("✅ BOT_TOKEN: установлен")
        print(f"   Значение: {config.BOT_TOKEN[:10]}...")
    else:
        print("❌ BOT_TOKEN: НЕ УСТАНОВЛЕН")
    
    # Проверка OPENAI_API_KEY
    if config.OPENAI_API_KEY:
        print("✅ OPENAI_API_KEY: установлен")
        print(f"   Значение: {config.OPENAI_API_KEY[:10]}...")
    else:
        print("❌ OPENAI_API_KEY: НЕ УСТАНОВЛЕН")
    
    # Проверка DATABASE_URL
    if config.DATABASE_URL:
        print("✅ DATABASE_URL: установлен")
        # Скрываем пароль в выводе
        db_url = config.DATABASE_URL
        if '@' in db_url:
            parts = db_url.split('@')
            if ':' in parts[0]:
                user_pass = parts[0].split(':')
                masked = f"{user_pass[0]}:****@{parts[1]}"
                print(f"   Значение: {masked}")
            else:
                print(f"   Значение: {db_url}")
        else:
            print(f"   Значение: {db_url}")
    else:
        print("❌ DATABASE_URL: НЕ УСТАНОВЛЕН")
    
    # Проверка Google Drive
    if config.GOOGLE_DRIVE_CREDENTIALS:
        print("✅ GOOGLE_DRIVE_CREDENTIALS: установлен")
        print(f"   Project ID: {config.GOOGLE_DRIVE_CREDENTIALS.get('project_id', 'не указан')}")
        print(f"   Client Email: {config.GOOGLE_DRIVE_CREDENTIALS.get('client_email', 'не указан')}")
    else:
        print("⚠️  GOOGLE_DRIVE_CREDENTIALS: не установлен (опционально)")
    
    if config.GOOGLE_DRIVE_FOLDER_ID:
        print("✅ GOOGLE_DRIVE_FOLDER_ID: установлен")
        print(f"   Значение: {config.GOOGLE_DRIVE_FOLDER_ID}")
    else:
        print("⚠️  GOOGLE_DRIVE_FOLDER_ID: не установлен (опционально)")
    
    # Проверка ADMIN_TELEGRAM_IDS
    if config.ADMIN_TELEGRAM_IDS:
        print("✅ ADMIN_TELEGRAM_IDS: установлен")
        print(f"   Администраторы: {', '.join(map(str, config.ADMIN_TELEGRAM_IDS))}")
    else:
        print("⚠️  ADMIN_TELEGRAM_IDS: не установлен")
    
    print("=" * 60)
    
    # Итоговая валидация
    if config.validate():
        print("\n✅ Конфигурация валидна! Можно запускать бота.")
        print("\nЗапуск бота: python -m bot.main")
    else:
        print("\n❌ Конфигурация содержит ошибки!")
        print("\nПожалуйста, заполните все обязательные поля в файле .env")
        print("См. .env.example для примера")


if __name__ == "__main__":
    check_config()



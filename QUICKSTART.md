# ⚡ Быстрый старт

## 1️⃣ Установка зависимостей

```bash
cd C:\Users\Admin\Desktop\telegram-construction-bot
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

## 2️⃣ Получение API ключей

### Telegram Bot Token
1. @BotFather → `/newbot`
2. Введите название и username
3. Скопируйте токен

### OpenAI API Key
1. platform.openai.com → API Keys
2. Create new secret key
3. Скопируйте ключ
4. **Пополните баланс!**

### Google Drive (опционально)
1. console.cloud.google.com → New Project
2. Enable Google Drive API
3. Create Service Account → Download JSON
4. Создайте папку на Drive → Share с email Service Account
5. Скопируйте folder ID из URL

### Telegram ID
1. @userinfobot → отправьте любое сообщение
2. Скопируйте ваш ID

## 3️⃣ Настройка .env

Откройте файл `.env` и заполните:

```env
BOT_TOKEN=ваш_токен_от_BotFather
OPENAI_API_KEY=ваш_ключ_OpenAI
DATABASE_URL=postgresql://localhost/construction_bot
GOOGLE_DRIVE_CREDENTIALS={"весь":"json","в":"одну","строку":"..."}
GOOGLE_DRIVE_FOLDER_ID=id_папки
ADMIN_TELEGRAM_IDS=ваш_telegram_id
```

## 4️⃣ Инициализация БД

```bash
# Если PostgreSQL установлен локально
createdb construction_bot

# Инициализация таблиц
python init_db.py
```

## 5️⃣ Запуск бота

```bash
python -m bot.main
```

Должно появиться:
```
✅ Конфигурация валидна
✅ База данных инициализирована
🚀 Бот запущен и готов к работе!
```

## 6️⃣ Проверка

1. Откройте Telegram
2. Найдите вашего бота
3. Отправьте `/start`
4. Должно появиться главное меню

---

## 🚀 Деплой на Railway (рекомендуется)

1. Создайте репозиторий на GitHub
2. Push код:
```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin <ваш-репозиторий>
git push -u origin main
```

3. Railway.app → New Project → Deploy from GitHub
4. Add PostgreSQL service
5. Add environment variables (BOT_TOKEN, OPENAI_API_KEY, etc.)
6. Deploy!

Railway автоматически:
- Установит зависимости
- Запустит миграции
- Запустит бота

---

## 📖 Полная документация

См. [README.md](README.md) для детальных инструкций.

---

## ❓ Проблемы?

### Бот не отвечает
- Проверьте, что ваш ID в `ADMIN_TELEGRAM_IDS`
- Проверьте логи бота

### Ошибка БД
```bash
# Пересоздайте базу
dropdb construction_bot
createdb construction_bot
python init_db.py
```

### OpenAI не работает
- Проверьте баланс на platform.openai.com
- Убедитесь, что ключ правильный

---

**Готово! Удачи! 🎉**


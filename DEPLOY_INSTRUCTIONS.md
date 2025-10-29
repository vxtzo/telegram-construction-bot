# 🚀 Инструкции по деплою на Railway

## ✅ Что исправлено:

1. ✅ Изменён `Procfile` - теперь использует `worker` вместо `web`
2. ✅ Создан `nixpacks.toml` - конфигурация для Railway
3. ✅ Создан `start.sh` - стартовый скрипт
4. ✅ Обновлён `railway.json` - правильные команды сборки
5. ✅ Создан `runtime.txt` - указание версии Python
6. ✅ Исправлен `.gitignore` - alembic.ini теперь включён в git

---

## 📦 Шаги для деплоя:

### 1. Закоммитьте и запушьте изменения на GitHub

```bash
cd C:\Users\Admin\Desktop\telegram-construction-bot
git add .
git commit -m "Fix Railway deployment configuration"
git push
```

### 2. В Railway:

1. **Если проект уже создан:**
   - Railway автоматически задеплоит новую версию
   - Следите за логами в разделе "Deployments"

2. **Если создаёте новый проект:**
   - New Project → Deploy from GitHub repo
   - Выберите `telegram-construction-bot`
   - Railway начнёт деплой

### 3. Добавьте PostgreSQL:

1. В проекте нажмите "New"
2. "Database" → "PostgreSQL"
3. Подождите создания
4. **ВАЖНО:** Railway автоматически добавит переменную `DATABASE_URL` в ваш сервис

### 4. Добавьте переменные окружения:

Кликните на сервис БОТА (не PostgreSQL) → Variables → добавьте:

```
BOT_TOKEN
<ваш_bot_token_от_BotFather>

OPENAI_API_KEY
<ваш_openai_api_key>

ADMIN_TELEGRAM_IDS
<ваш_telegram_id>
```

### 5. Проверьте логи:

В разделе "Deployments" → кликните на текущий деплой → смотрите логи.

Должно быть:
```
Running database migrations...
✅ База данных инициализирована
✅ Создан администратор с ID: 436999551
🚀 Бот запущен и готов к работе!
```

### 6. Тестируйте в Telegram:

1. Откройте Telegram
2. Найдите вашего бота
3. Отправьте `/start`
4. Должно появиться главное меню!

---

## 🐛 Возможные проблемы:

### "alembic: command not found"
- Решение: уже исправлено в `requirements.txt` (alembic включён)

### "DATABASE_URL not set"
- Решение: убедитесь, что PostgreSQL service добавлен и связан с ботом

### "OPENAI_API_KEY not set"
- Решение: добавьте переменную в Railway Variables

### Бот не отвечает
- Проверьте логи - возможно нужно пополнить баланс OpenAI
- Убедитесь, что BOT_TOKEN правильный

---

## ✅ Всё готово к деплою!

После push на GitHub Railway автоматически задеплоит обновлённую версию.


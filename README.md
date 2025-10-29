# 🏗️ Telegram Construction Bot

Telegram бот для управления строительными объектами с функциями учета расходов, генерации отчетов и расчета прибыли.

## 📋 Возможности

- ✅ Управление строительными объектами (текущие/завершенные)
- 💰 Учет расходов (расходники, транспорт, накладные) с AI-парсингом текста и голоса
- 💵 Учет авансов рабочим
- 📊 Автоматический расчет прибыли и рентабельности
- 📈 Генерация детальных отчетов
- 📁 Интеграция с Google Drive для хранения документов и фото
- 🎤 Голосовой ввод через Whisper API
- 👥 Система ролей (Админ/Прораб)

## 🛠️ Технологии

- Python 3.11+
- aiogram 3.x (Telegram Bot API)
- PostgreSQL + SQLAlchemy 2.0
- OpenAI API (GPT-4 + Whisper)
- Google Drive API
- Railway.app (деплой)

---

## 📦 Установка и настройка

### 1. Клонирование репозитория

```bash
git clone <ваш-репозиторий>
cd telegram-construction-bot
```

### 2. Создание виртуального окружения

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate
```

### 3. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 4. Настройка переменных окружения

Создайте файл `.env` на основе `.env.example`:

```bash
cp .env.example .env
```

Заполните переменные окружения (инструкции ниже).

---

## 🔑 Получение API ключей

### 1. Telegram Bot Token

1. Откройте Telegram и найдите бота [@BotFather](https://t.me/BotFather)
2. Отправьте команду `/newbot`
3. Введите название бота (например: `Construction Manager`)
4. Введите username бота (должен заканчиваться на `bot`, например: `construction_manager_bot`)
5. Скопируйте полученный токен и вставьте в `.env` как `BOT_TOKEN`

### 2. OpenAI API Key

1. Зарегистрируйтесь на [platform.openai.com](https://platform.openai.com)
2. Перейдите в раздел [API Keys](https://platform.openai.com/api-keys)
3. Нажмите "Create new secret key"
4. Скопируйте ключ и вставьте в `.env` как `OPENAI_API_KEY`

⚠️ **Важно**: Пополните баланс аккаунта OpenAI для использования API.

### 3. Google Drive API

#### 3.1. Создание проекта в Google Cloud Console

1. Откройте [Google Cloud Console](https://console.cloud.google.com/)
2. Нажмите "Select a project" → "New Project"
3. Введите название проекта (например: `Construction Bot`)
4. Нажмите "Create"

#### 3.2. Включение Google Drive API

1. В меню слева выберите "APIs & Services" → "Library"
2. Найдите "Google Drive API"
3. Нажмите "Enable"

#### 3.3. Создание Service Account

1. В меню слева выберите "APIs & Services" → "Credentials"
2. Нажмите "Create Credentials" → "Service Account"
3. Введите имя (например: `construction-bot`)
4. Нажмите "Create and Continue"
5. Выберите роль "Editor" или "Owner"
6. Нажмите "Continue" → "Done"

#### 3.4. Создание и скачивание JSON ключа

1. Найдите созданный Service Account в списке
2. Нажмите на него
3. Перейдите на вкладку "Keys"
4. Нажмите "Add Key" → "Create new key"
5. Выберите формат "JSON"
6. Файл автоматически скачается

#### 3.5. Настройка Google Drive папки

1. Откройте [Google Drive](https://drive.google.com)
2. Создайте новую папку (например: `Строительные объекты`)
3. Правой кнопкой на папку → "Share"
4. Добавьте email вашего Service Account (найдете в JSON файле, поле `client_email`)
5. Дайте права "Editor"
6. Скопируйте ID папки из URL (после `/folders/`)

#### 3.6. Добавление credentials в .env

Откройте скачанный JSON файл и скопируйте **всё содержимое** в одну строку в `.env`:

```env
GOOGLE_DRIVE_CREDENTIALS={"type":"service_account","project_id":"...","private_key_id":"...","private_key":"-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n","client_email":"...","client_id":"...","auth_uri":"...","token_uri":"...","auth_provider_x509_cert_url":"...","client_x509_cert_url":"..."}

GOOGLE_DRIVE_FOLDER_ID=ваш_folder_id
```

### 4. PostgreSQL Database

#### Для локальной разработки:

1. Установите PostgreSQL
2. Создайте базу данных:
```sql
CREATE DATABASE construction_bot;
```
3. В `.env` укажите:
```env
DATABASE_URL=postgresql://username:password@localhost:5432/construction_bot
```

#### Для Railway (рекомендуется):

База данных создастся автоматически при деплое. Railway предоставит `DATABASE_URL`.

### 5. Telegram ID администраторов

1. Откройте Telegram и найдите бота [@userinfobot](https://t.me/userinfobot)
2. Отправьте любое сообщение
3. Скопируйте ваш ID
4. В `.env` укажите (через запятую, если несколько):
```env
ADMIN_TELEGRAM_IDS=123456789,987654321
```

---

## 🚀 Запуск локально

### 1. Создание миграций БД

```bash
alembic revision --autogenerate -m "Initial migration"
alembic upgrade head
```

### 2. Запуск бота

```bash
python -m bot.main
```

Бот должен запуститься и вывести:
```
✅ Конфигурация валидна
✅ База данных инициализирована
✅ Создан администратор с ID: ...
🚀 Бот запущен и готов к работе!
```

### 3. Проверка работы

1. Откройте Telegram
2. Найдите вашего бота по username
3. Отправьте `/start`
4. Должно появиться главное меню

---

## ☁️ Деплой на Railway

### 1. Создание аккаунта

1. Откройте [railway.app](https://railway.app)
2. Зарегистрируйтесь через GitHub

### 2. Создание проекта

1. Нажмите "New Project"
2. Выберите "Deploy from GitHub repo"
3. Выберите ваш репозиторий

### 3. Добавление PostgreSQL

1. В проекте нажмите "New"
2. Выберите "Database" → "PostgreSQL"
3. Railway автоматически создаст БД и установит `DATABASE_URL`

### 4. Настройка переменных окружения

1. Перейдите в настройки вашего сервиса (не БД)
2. Откройте вкладку "Variables"
3. Добавьте все переменные из `.env`:
   - `BOT_TOKEN`
   - `OPENAI_API_KEY`
   - `GOOGLE_DRIVE_CREDENTIALS` (вся строка JSON)
   - `GOOGLE_DRIVE_FOLDER_ID`
   - `ADMIN_TELEGRAM_IDS`

⚠️ `DATABASE_URL` добавится автоматически при подключении PostgreSQL.

### 5. Деплой

1. Railway автоматически задеплоит бот после push в GitHub
2. Проверьте логи в разделе "Deployments"
3. Бот должен запуститься автоматически

### 6. Миграции

Railway выполнит миграции автоматически благодаря команде в `Procfile`:
```
release: alembic upgrade head
```

---

## 📖 Использование бота

### Для администраторов:

#### Создание объекта
1. Нажмите "➕ Добавить объект"
2. Следуйте пошаговым инструкциям (11 шагов)
3. Подтвердите данные

#### Добавление расходов
1. Откройте "🏗️ Объекты" → "Текущие объекты"
2. Выберите объект
3. Нажмите нужную кнопку (расходники/транспорт/накладные)
4. Опишите расход текстом или голосом
5. Подтвердите распарсенные данные
6. При желании добавьте фото чека

#### Генерация отчетов
1. Нажмите "📊 Создать отчёт"
2. Выберите тип отчёта:
   - За период (год/месяц/диапазон)
   - За завершенный объект
3. Следуйте инструкциям

#### Управление пользователями
```
/add_user <telegram_id> <role>
/remove_user <telegram_id>
/block_user <telegram_id>
/unblock_user <telegram_id>
/list_users
```

### Для прорабов:

- Просмотр всех объектов
- Добавление расходов (текст/голос)
- Добавление авансов рабочим

---

## 🎤 Голосовой ввод

Бот поддерживает голосовой ввод для:
- Добавления расходов
- Добавления авансов

Просто отправьте голосовое сообщение вместо текста, например:
> "Купил цемент на пять тысяч рублей двадцать пятого октября"

Бот автоматически распознает речь и извлечет:
- Дату
- Сумму
- Описание

---

## 📊 Формулы расчета

### Прибыль объекта:

```
Прибыль = (С3_смета - С3_скидка) + 
          (0.45 × Работы_смета) + 
          (Расходники_смета - Расходники_факт) +
          (Накладные_смета - Накладные_факт) +
          (Транспорт_смета - Транспорт_факт)
```

### ФЗП:
- ФЗП мастера = 45% от работ по смете
- ФЗП бригадира = 10% от работ по смете

### Рентабельность:
```
Рентабельность = (Прибыль / Всего_поступлений) × 100%
```

---

## 🐛 Отладка

### Проблема: Бот не отвечает
- Проверьте, что бот запущен
- Проверьте логи
- Убедитесь, что ваш Telegram ID добавлен в `ADMIN_TELEGRAM_IDS`

### Проблема: Ошибка БД
- Проверьте `DATABASE_URL`
- Выполните миграции: `alembic upgrade head`

### Проблема: Не работает AI парсинг
- Проверьте `OPENAI_API_KEY`
- Убедитесь, что на балансе OpenAI есть средства

### Проблема: Не загружаются файлы на Google Drive
- Проверьте `GOOGLE_DRIVE_CREDENTIALS`
- Убедитесь, что Service Account имеет доступ к папке
- Проверьте `GOOGLE_DRIVE_FOLDER_ID`

---

## 📝 Структура проекта

```
telegram-construction-bot/
├── bot/
│   ├── handlers/       # Обработчики команд и callback
│   ├── keyboards/      # Клавиатуры
│   ├── services/       # Бизнес-логика (AI, расчеты, отчеты)
│   ├── states/         # FSM состояния
│   ├── middlewares/    # Middleware (авторизация)
│   ├── config.py       # Конфигурация
│   └── main.py         # Точка входа
├── database/
│   ├── models.py       # SQLAlchemy модели
│   ├── database.py     # Подключение к БД
│   └── crud.py         # CRUD операции
├── alembic/            # Миграции БД
├── requirements.txt
├── .env.example
├── Procfile           # Для Railway
└── README.md
```

---

## 📄 Лицензия

MIT License

---

## 👨‍💻 Автор

Разработано для управления строительными объектами

---

## 🆘 Поддержка

Если возникли вопросы или проблемы:
1. Проверьте раздел "Отладка"
2. Проверьте логи бота
3. Убедитесь, что все API ключи настроены правильно

---

**Успешного использования! 🚀**



# 🛠️ Руководство по разработке

## Структура проекта

### bot/
- `config.py` - Загрузка конфигурации из .env
- `main.py` - Точка входа, инициализация бота

#### bot/handlers/
- `start.py` - Команда /start и главное меню
- `objects.py` - Просмотр и управление объектами
- `add_object.py` - FSM для создания объекта (11 шагов)
- `expenses.py` - Добавление расходов и авансов (с AI)
- `reports.py` - Генерация отчетов
- `admin.py` - Админ-команды для управления пользователями

#### bot/keyboards/
- `main_menu.py` - Главное меню и базовые клавиатуры
- `objects_kb.py` - Клавиатуры для объектов
- `reports_kb.py` - Клавиатуры для отчетов

#### bot/states/
- `add_object_states.py` - FSM состояния для создания объекта
- `expense_states.py` - FSM для расходов/авансов/отчетов

#### bot/services/
- `ai_parser.py` - OpenAI парсинг текста и Whisper для голоса
- `calculations.py` - Формулы расчета прибыли
- `report_generator.py` - Генерация текстовых отчетов
- `gdrive_service.py` - Работа с Google Drive API

#### bot/middlewares/
- `auth_middleware.py` - Проверка авторизации пользователей

### database/
- `models.py` - SQLAlchemy ORM модели
- `database.py` - Подключение к БД, создание сессий
- `crud.py` - CRUD операции для всех моделей

### alembic/
- Миграции базы данных
- `env.py` - Конфигурация Alembic
- `versions/` - История миграций

---

## Добавление нового функционала

### 1. Новая команда/handler

**Пример: Добавление команды для экспорта в Excel**

1. Создайте новый файл в `bot/handlers/`:
```python
# bot/handlers/export.py
from aiogram import Router, F
from aiogram.filters import Command

router = Router()

@router.message(Command("export"))
async def cmd_export(message: Message, user: User):
    # Ваша логика
    pass
```

2. Зарегистрируйте router в `bot/main.py`:
```python
from bot.handlers import export

# В функции main():
dp.include_router(export.router)
```

### 2. Новая модель БД

**Пример: Добавление таблицы для хранения комментариев**

1. Добавьте модель в `database/models.py`:
```python
class Comment(Base):
    __tablename__ = "comments"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("objects.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

2. Добавьте CRUD операции в `database/crud.py`:
```python
async def create_comment(session: AsyncSession, object_id: int, text: str):
    comment = Comment(object_id=object_id, text=text)
    session.add(comment)
    await session.commit()
    return comment
```

3. Создайте миграцию:
```bash
alembic revision --autogenerate -m "Add comments table"
alembic upgrade head
```

### 3. Новый сервис

**Пример: Добавление отправки уведомлений**

Создайте файл `bot/services/notifications.py`:
```python
from aiogram import Bot

async def send_notification(bot: Bot, user_id: int, text: str):
    await bot.send_message(user_id, text)
```

---

## Работа с базой данных

### Получение сессии

Сессия автоматически добавляется в контекст через middleware:

```python
@router.message(Command("test"))
async def test_handler(message: Message, session: AsyncSession):
    # session уже доступна
    objects = await get_objects_by_status(session, ObjectStatus.ACTIVE)
```

### CRUD операции

Все CRUD операции находятся в `database/crud.py`:

```python
# Создание пользователя
user = await create_user(session, telegram_id=123, role=UserRole.ADMIN)

# Получение объекта
obj = await get_object_by_id(session, object_id=1)

# Обновление статуса
obj = await update_object_status(session, object_id=1, status=ObjectStatus.COMPLETED)
```

---

## Работа с AI

### Парсинг текста

```python
from bot.services.ai_parser import parse_expense_text

# Парсинг текста расхода
data = await parse_expense_text("Купил цемент на 5000р 25 октября")
# Результат: {"date": "2025-10-25", "amount": Decimal("5000"), "description": "Цемент"}
```

### Парсинг голоса

```python
from bot.services.ai_parser import parse_voice_expense

# Парсинг голосового сообщения
data = await parse_voice_expense(file_path, "расходники")
```

---

## Работа с Google Drive

```python
from bot.services.gdrive_service import gdrive_service

# Создание папок для объекта
folders = gdrive_service.create_object_folders("Название объекта")
# Результат: (main_folder_id, receipts_id, photos_id, docs_id)

# Загрузка файла
result = gdrive_service.upload_file(
    file_content=bytes_data,
    filename="receipt.jpg",
    folder_id=folder_id,
    mime_type="image/jpeg"
)
# Результат: (file_id, web_link)
```

---

## Расчеты

### Прибыль объекта

```python
from bot.services.calculations import calculate_profit_data, format_currency

# Рассчитать все показатели
data = calculate_profit_data(obj)

# Использование
print(f"Прибыль: {format_currency(data['total_profit'])}")
print(f"Рентабельность: {format_percentage(data['profitability'])}")
```

---

## Генерация отчетов

```python
from bot.services.report_generator import generate_object_report

# Генерация детального отчета
report = generate_object_report(obj, files)
await message.answer(report)
```

---

## Тестирование

### Локальное тестирование

1. Запустите бота локально:
```bash
python -m bot.main
```

2. Откройте Telegram и найдите вашего бота

3. Проверьте основные функции:
   - /start - главное меню
   - Создание объекта
   - Добавление расходов
   - Генерация отчетов

### Тестирование AI парсинга

```bash
# Создайте тестовый скрипт test_ai.py
python test_ai.py
```

---

## Отладка

### Включение debug логов SQLAlchemy

В `database/database.py`:
```python
engine = create_async_engine(
    database_url,
    echo=True,  # Включить вывод SQL запросов
    poolclass=NullPool,
)
```

### Вывод debug информации

```python
import logging

logger = logging.getLogger(__name__)
logger.info("Debug информация")
logger.error("Ошибка", exc_info=True)
```

---

## Миграции базы данных

### Создание новой миграции

```bash
# Автоматическая генерация на основе изменений в models.py
alembic revision --autogenerate -m "Описание изменений"

# Применить миграции
alembic upgrade head

# Откатить последнюю миграцию
alembic downgrade -1
```

---

## Best Practices

### 1. Обработка ошибок

Всегда оборачивайте критичные операции в try-except:

```python
try:
    obj = await create_object(session, ...)
except Exception as e:
    logger.error(f"Ошибка создания объекта: {e}")
    await message.answer("❌ Произошла ошибка")
```

### 2. Асинхронность

Используйте `async/await` для всех IO операций:

```python
# ✅ Правильно
result = await get_object_by_id(session, 1)

# ❌ Неправильно
result = get_object_by_id(session, 1)  # Вернет coroutine
```

### 3. Middleware

Для добавления данных в контекст используйте middleware:

```python
class MyMiddleware:
    async def __call__(self, handler, event, data):
        data["my_data"] = "value"
        return await handler(event, data)
```

### 4. FSM States

Для многошаговых диалогов используйте FSM:

```python
class MyStates(StatesGroup):
    step1 = State()
    step2 = State()

# Установка состояния
await state.set_state(MyStates.step1)

# Сохранение данных
await state.update_data(key="value")

# Получение данных
data = await state.get_data()

# Очистка состояния
await state.clear()
```

---

## Деплой

### Перед деплоем

1. Проверьте конфигурацию:
```bash
python check_config.py
```

2. Убедитесь, что .env не попал в git:
```bash
git status
```

3. Запушьте код:
```bash
git add .
git commit -m "Your message"
git push
```

### Railway автоматически:

1. Установит зависимости из requirements.txt
2. Выполнит миграции (alembic upgrade head)
3. Запустит бота (python -m bot.main)

---

## Полезные ссылки

- [aiogram документация](https://docs.aiogram.dev/)
- [SQLAlchemy документация](https://docs.sqlalchemy.org/)
- [OpenAI API](https://platform.openai.com/docs/)
- [Google Drive API](https://developers.google.com/drive)
- [Railway документация](https://docs.railway.app/)

---

## Вопросы?

Проверьте:
1. Логи бота
2. README.md
3. QUICKSTART.md
4. Этот файл (DEVELOPMENT.md)


"""
Обработчики для добавления расходов и авансов
"""
import os
import tempfile
from datetime import datetime
from decimal import Decimal
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, ExpenseType, FileType
from database.crud import (
    create_expense,
    create_advance,
    get_object_by_id,
    create_file
)
from bot.states.expense_states import AddExpenseStates, AddAdvanceStates
from bot.keyboards.main_menu import get_cancel_button, get_confirm_keyboard
from bot.services.ai_parser import (
    parse_expense_text,
    parse_advance_text,
    parse_voice_expense,
    parse_voice_advance
)
from bot.services.gdrive_service import gdrive_service
from bot.services.calculations import format_currency

router = Router()


# ============ РАСХОДЫ ============

@router.callback_query(F.data.startswith("expense:add:"))
async def start_add_expense(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """
    Начать добавление расхода
    
    Format: expense:add:<type>:<object_id>
    """
    
    parts = callback.data.split(":")
    expense_type = parts[2]  # supplies, transport, overhead
    object_id = int(parts[3])
    
    # Проверяем объект
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return
    
    # Определяем текст в зависимости от типа расхода
    type_names = {
        "supplies": "расходников",
        "transport": "транспортных расходов",
        "overhead": "накладных расходов"
    }
    type_emoji = {
        "supplies": "🧰",
        "transport": "🚚",
        "overhead": "🧾"
    }
    
    type_name = type_names.get(expense_type, "расходов")
    emoji = type_emoji.get(expense_type, "💰")
    
    await state.update_data(
        expense_type=expense_type,
        object_id=object_id,
        object_name=obj.name
    )
    await state.set_state(AddExpenseStates.waiting_input)
    
    await callback.message.edit_text(
        f"{emoji} <b>Добавление {type_name}</b>\n\n"
        f"Объект: <b>{obj.name}</b>\n\n"
        f"Опишите расход в свободной форме (текстом или голосом):\n\n"
        f"Примеры:\n"
        f"• \"Купил цемент на 5000 рублей 25 октября\"\n"
        f"• \"Доставка материалов 3500р\"\n"
        f"• \"Вчера потратил 2000 на инструменты\"\n\n"
        f"Я автоматически определю дату, сумму и описание.",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.message(AddExpenseStates.waiting_input, F.text)
async def process_expense_text(message: Message, state: FSMContext):
    """Обработка текстового ввода расхода"""
    
    data = await state.get_data()
    expense_type = data['expense_type']
    
    # Парсим текст через AI
    await message.answer("⏳ Обрабатываю...")
    
    type_names = {
        "supplies": "расходники",
        "transport": "транспорт",
        "overhead": "накладные"
    }
    
    parsed = await parse_expense_text(message.text, type_names.get(expense_type, "расход"))
    
    # Сохраняем распарсенные данные
    await state.update_data(
        parsed_date=parsed['date'],
        parsed_amount=parsed['amount'],
        parsed_description=parsed['description']
    )
    await state.set_state(AddExpenseStates.confirm_expense)
    
    # Показываем что получилось
    date_obj = datetime.strptime(parsed['date'], "%Y-%m-%d")
    
    confirm_text = f"""
✅ <b>Проверьте данные:</b>

📅 Дата: {date_obj.strftime("%d.%m.%Y")}
💰 Сумма: {format_currency(parsed['amount'])}
📝 Описание: {parsed['description']}

Все верно?
"""
    
    await message.answer(
        confirm_text.strip(),
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard("expense:confirm", "expense:retry")
    )


@router.message(AddExpenseStates.waiting_input, F.voice)
async def process_expense_voice(message: Message, state: FSMContext):
    """Обработка голосового ввода расхода"""
    
    data = await state.get_data()
    expense_type = data['expense_type']
    
    await message.answer("🎤 Распознаю голос...")
    
    # Скачиваем голосовое сообщение
    try:
        voice = message.voice
        file = await message.bot.get_file(voice.file_id)
        
        # Сохраняем во временный файл
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_path = tmp_file.name
            await message.bot.download_file(file.file_path, tmp_path)
        
        # Парсим голос через AI
        type_names = {
            "supplies": "расходники",
            "transport": "транспорт",
            "overhead": "накладные"
        }
        
        parsed = await parse_voice_expense(tmp_path, type_names.get(expense_type, "расход"))
        
        # Удаляем временный файл
        os.unlink(tmp_path)
        
        # Сохраняем распарсенные данные
        await state.update_data(
            parsed_date=parsed['date'],
            parsed_amount=parsed['amount'],
            parsed_description=parsed['description']
        )
        await state.set_state(AddExpenseStates.confirm_expense)
        
        # Показываем что получилось
        date_obj = datetime.strptime(parsed['date'], "%Y-%m-%d")
        
        confirm_text = f"""
✅ <b>Проверьте данные:</b>

📅 Дата: {date_obj.strftime("%d.%m.%Y")}
💰 Сумма: {format_currency(parsed['amount'])}
📝 Описание: {parsed['description']}

Все верно?
"""
        
        await message.answer(
            confirm_text.strip(),
            parse_mode="HTML",
            reply_markup=get_confirm_keyboard("expense:confirm", "expense:retry")
        )
        
    except Exception as e:
        print(f"❌ Ошибка обработки голоса: {e}")
        await message.answer(
            "❌ Не удалось распознать голос. Попробуйте ввести текстом.",
            reply_markup=get_cancel_button()
        )


@router.callback_query(F.data == "expense:retry", AddExpenseStates.confirm_expense)
async def retry_expense_input(callback: CallbackQuery, state: FSMContext):
    """Повторить ввод расхода"""
    
    await state.set_state(AddExpenseStates.waiting_input)
    data = await state.get_data()
    
    await callback.message.edit_text(
        f"📝 Попробуйте описать расход ещё раз:\n\n"
        f"Объект: <b>{data['object_name']}</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.callback_query(F.data == "expense:confirm", AddExpenseStates.confirm_expense)
async def confirm_expense(callback: CallbackQuery, user: User, state: FSMContext):
    """Подтверждение расхода - предложить добавить фото"""
    
    await state.set_state(AddExpenseStates.waiting_photo)
    
    await callback.message.edit_text(
        "📸 Хотите добавить фото чека?\n\n"
        "Отправьте фото или нажмите 'Пропустить'",
        reply_markup=get_confirm_keyboard("expense:skip_photo", "cancel")
    )
    await callback.answer()


@router.message(AddExpenseStates.waiting_photo, F.photo)
async def process_expense_photo(message: Message, user: User, session: AsyncSession, state: FSMContext):
    """Обработка фото чека"""
    
    data = await state.get_data()
    
    # Получаем фото (берем самое большое)
    photo = message.photo[-1]
    
    # Сохраняем расход в БД
    expense_type = ExpenseType[data['expense_type'].upper()]
    date_obj = datetime.strptime(data['parsed_date'], "%Y-%m-%d")
    
    photo_url = None
    
    # Загружаем на Google Drive (если настроено)
    if gdrive_service.service:
        try:
            # Получаем объект для folder_id
            obj = await get_object_by_id(session, data['object_id'], load_relations=False)
            
            if obj and obj.gdrive_folder_id:
                # Скачиваем фото
                file = await message.bot.get_file(photo.file_id)
                photo_bytes = await message.bot.download_file(file.file_path)
                
                # Генерируем имя файла
                filename = f"receipt_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
                
                # Загружаем на Google Drive (в подпапку Чеки)
                # TODO: получить receipts_folder_id
                result = gdrive_service.upload_file(
                    photo_bytes.read(),
                    filename,
                    obj.gdrive_folder_id,  # Загружаем в главную папку объекта
                    'image/jpeg'
                )
                
                if result:
                    photo_url = result[1]
                    
                    # Сохраняем в БД файл
                    await create_file(
                        session,
                        object_id=data['object_id'],
                        file_type=FileType.RECEIPT,
                        telegram_file_id=photo.file_id,
                        gdrive_file_id=result[0],
                        gdrive_url=result[1],
                        filename=filename
                    )
        except Exception as e:
            print(f"⚠️ Не удалось загрузить фото на Google Drive: {e}")
    
    # Создаем расход
    expense = await create_expense(
        session=session,
        object_id=data['object_id'],
        expense_type=expense_type,
        amount=data['parsed_amount'],
        description=data['parsed_description'],
        date=date_obj,
        added_by=user.id,
        photo_url=photo_url
    )
    
    await state.clear()
    
    await message.answer(
        f"✅ <b>Расход добавлен!</b>\n\n"
        f"Объект: {data['object_name']}\n"
        f"Сумма: {format_currency(data['parsed_amount'])}\n"
        f"Дата: {date_obj.strftime('%d.%m.%Y')}\n"
        f"{'📸 Фото чека добавлено' if photo_url else ''}",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "expense:skip_photo", AddExpenseStates.waiting_photo)
async def skip_expense_photo(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Пропустить добавление фото и сохранить расход"""
    
    data = await state.get_data()
    
    # Создаем расход без фото
    expense_type = ExpenseType[data['expense_type'].upper()]
    date_obj = datetime.strptime(data['parsed_date'], "%Y-%m-%d")
    
    expense = await create_expense(
        session=session,
        object_id=data['object_id'],
        expense_type=expense_type,
        amount=data['parsed_amount'],
        description=data['parsed_description'],
        date=date_obj,
        added_by=user.id
    )
    
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ <b>Расход добавлен!</b>\n\n"
        f"Объект: {data['object_name']}\n"
        f"Сумма: {format_currency(data['parsed_amount'])}\n"
        f"Дата: {date_obj.strftime('%d.%m.%Y')}",
        parse_mode="HTML"
    )
    await callback.answer("✅ Расход добавлен")


# ============ АВАНСЫ ============

@router.callback_query(F.data.startswith("advance:add:"))
async def start_add_advance(callback: CallbackQuery, state: FSMContext, session: AsyncSession):
    """Начать добавление аванса"""
    
    object_id = int(callback.data.split(":")[2])
    
    # Проверяем объект
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return
    
    await state.update_data(
        object_id=object_id,
        object_name=obj.name
    )
    await state.set_state(AddAdvanceStates.waiting_input)
    
    await callback.message.edit_text(
        f"💵 <b>Добавление аванса</b>\n\n"
        f"Объект: <b>{obj.name}</b>\n\n"
        f"Опишите аванс в свободной форме (текстом или голосом):\n\n"
        f"Примеры:\n"
        f"• \"Иванов, кладка кирпича, 15000 рублей, 20 октября\"\n"
        f"• \"Аванс Петрову 10000р на облицовку\"\n"
        f"• \"Сидоров получил 8000 за штукатурку\"\n\n"
        f"Я автоматически определю имя рабочего, вид работ, сумму и дату.",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.message(AddAdvanceStates.waiting_input, F.text)
async def process_advance_text(message: Message, state: FSMContext):
    """Обработка текстового ввода аванса"""
    
    await message.answer("⏳ Обрабатываю...")
    
    # Парсим через AI
    parsed = await parse_advance_text(message.text)
    
    # Сохраняем данные
    await state.update_data(
        parsed_worker_name=parsed['worker_name'],
        parsed_work_type=parsed['work_type'],
        parsed_amount=parsed['amount'],
        parsed_date=parsed['date']
    )
    await state.set_state(AddAdvanceStates.confirm_advance)
    
    # Показываем результат
    date_obj = datetime.strptime(parsed['date'], "%Y-%m-%d")
    
    confirm_text = f"""
✅ <b>Проверьте данные:</b>

👤 Рабочий: {parsed['worker_name'] or '(не указано)'}
⚒ Вид работ: {parsed['work_type'] or '(не указано)'}
💰 Сумма: {format_currency(parsed['amount'])}
📅 Дата: {date_obj.strftime("%d.%m.%Y")}

Все верно?
"""
    
    await message.answer(
        confirm_text.strip(),
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard("advance:confirm", "advance:retry")
    )


@router.message(AddAdvanceStates.waiting_input, F.voice)
async def process_advance_voice(message: Message, state: FSMContext):
    """Обработка голосового ввода аванса"""
    
    await message.answer("🎤 Распознаю голос...")
    
    try:
        voice = message.voice
        file = await message.bot.get_file(voice.file_id)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_path = tmp_file.name
            await message.bot.download_file(file.file_path, tmp_path)
        
        # Парсим голос
        parsed = await parse_voice_advance(tmp_path)
        
        os.unlink(tmp_path)
        
        # Сохраняем данные
        await state.update_data(
            parsed_worker_name=parsed['worker_name'],
            parsed_work_type=parsed['work_type'],
            parsed_amount=parsed['amount'],
            parsed_date=parsed['date']
        )
        await state.set_state(AddAdvanceStates.confirm_advance)
        
        # Показываем результат
        date_obj = datetime.strptime(parsed['date'], "%Y-%m-%d")
        
        confirm_text = f"""
✅ <b>Проверьте данные:</b>

👤 Рабочий: {parsed['worker_name'] or '(не указано)'}
⚒ Вид работ: {parsed['work_type'] or '(не указано)'}
💰 Сумма: {format_currency(parsed['amount'])}
📅 Дата: {date_obj.strftime("%d.%m.%Y")}

Все верно?
"""
        
        await message.answer(
            confirm_text.strip(),
            parse_mode="HTML",
            reply_markup=get_confirm_keyboard("advance:confirm", "advance:retry")
        )
        
    except Exception as e:
        print(f"❌ Ошибка обработки голоса: {e}")
        await message.answer(
            "❌ Не удалось распознать голос. Попробуйте ввести текстом.",
            reply_markup=get_cancel_button()
        )


@router.callback_query(F.data == "advance:retry", AddAdvanceStates.confirm_advance)
async def retry_advance_input(callback: CallbackQuery, state: FSMContext):
    """Повторить ввод аванса"""
    
    await state.set_state(AddAdvanceStates.waiting_input)
    data = await state.get_data()
    
    await callback.message.edit_text(
        f"📝 Попробуйте описать аванс ещё раз:\n\n"
        f"Объект: <b>{data['object_name']}</b>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )
    await callback.answer()


@router.callback_query(F.data == "advance:confirm", AddAdvanceStates.confirm_advance)
async def confirm_advance(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Подтверждение и сохранение аванса"""
    
    data = await state.get_data()
    
    # Создаем аванс
    date_obj = datetime.strptime(data['parsed_date'], "%Y-%m-%d")
    
    advance = await create_advance(
        session=session,
        object_id=data['object_id'],
        worker_name=data['parsed_worker_name'] or "Не указан",
        work_type=data['parsed_work_type'] or "Не указан",
        amount=data['parsed_amount'],
        date=date_obj,
        added_by=user.id
    )
    
    await state.clear()
    
    await callback.message.edit_text(
        f"✅ <b>Аванс добавлен!</b>\n\n"
        f"Объект: {data['object_name']}\n"
        f"Рабочий: {data['parsed_worker_name']}\n"
        f"Вид работ: {data['parsed_work_type']}\n"
        f"Сумма: {format_currency(data['parsed_amount'])}\n"
        f"Дата: {date_obj.strftime('%d.%m.%Y')}",
        parse_mode="HTML"
    )
    await callback.answer("✅ Аванс добавлен")


"""
Обработчики для создания нового объекта (FSM)
"""
from decimal import Decimal, InvalidOperation
from datetime import datetime
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole
from database.crud import create_object
from bot.states.add_object_states import AddObjectStates
from bot.keyboards.main_menu import get_cancel_button, get_skip_or_cancel, get_confirm_keyboard
from bot.services.gdrive_service import gdrive_service

router = Router()


@router.message(F.text == "➕ Добавить объект")
@router.message(Command("add_object"))
async def start_add_object(message: Message, user: User, state: FSMContext):
    """Начать процесс создания объекта"""
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для создания объектов.")
        return
    
    await state.clear()
    await state.set_state(AddObjectStates.enter_name)
    
    await message.answer(
        "📝 <b>Создание нового объекта</b>\n\n"
        "Шаг 1/11: Введите название объекта\n\n"
        "Например: <i>Вячеслав С поворотом</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка названия объекта"""
    
    await state.update_data(name=message.text.strip())
    await state.set_state(AddObjectStates.enter_address)
    
    await message.answer(
        "📝 Шаг 2/11: Введите адрес объекта\n\n"
        "Или нажмите 'Пропустить', если адрес неизвестен",
        reply_markup=get_skip_or_cancel()
    )


@router.message(AddObjectStates.enter_address)
async def process_address(message: Message, state: FSMContext):
    """Обработка адреса"""
    
    await state.update_data(address=message.text.strip())
    await state.set_state(AddObjectStates.enter_foreman)
    
    await message.answer(
        "📝 Шаг 3/11: Введите имя бригадира/ответственного\n\n"
        "Или нажмите 'Пропустить'",
        reply_markup=get_skip_or_cancel()
    )


@router.message(AddObjectStates.enter_foreman)
async def process_foreman(message: Message, state: FSMContext):
    """Обработка имени бригадира"""
    
    await state.update_data(foreman_name=message.text.strip())
    await state.set_state(AddObjectStates.enter_dates)
    
    await message.answer(
        "📝 Шаг 4/11: Введите даты работ\n\n"
        "Формат: <code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>\n"
        "Например: <code>01.11.2025 - 30.11.2025</code>\n\n"
        "Или нажмите 'Пропустить'",
        parse_mode="HTML",
        reply_markup=get_skip_or_cancel()
    )


@router.message(AddObjectStates.enter_dates)
async def process_dates(message: Message, state: FSMContext):
    """Обработка дат"""
    
    start_date = None
    end_date = None
    
    text = message.text.strip()
    if " - " in text or " — " in text:
        try:
            dates = text.replace(" — ", " - ").split(" - ")
            start_date = datetime.strptime(dates[0].strip(), "%d.%m.%Y")
            end_date = datetime.strptime(dates[1].strip(), "%d.%m.%Y")
        except:
            await message.answer(
                "❌ Неверный формат дат. Попробуйте еще раз:\n"
                "Формат: <code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>",
                parse_mode="HTML"
            )
            return
    
    await state.update_data(start_date=start_date, end_date=end_date)
    await state.set_state(AddObjectStates.enter_prepayment)
    
    await message.answer(
        "💸 Шаг 5/11: Введите сумму предоплаты (в рублях)\n\n"
        "Например: <code>150000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_prepayment)
async def process_prepayment(message: Message, state: FSMContext):
    """Обработка предоплаты"""
    
    try:
        prepayment = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if prepayment < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число (например: 150000):"
        )
        return
    
    await state.update_data(prepayment=prepayment)
    await state.set_state(AddObjectStates.enter_final_payment)
    
    await message.answer(
        "💸 Шаг 6/11: Введите сумму окончательной оплаты (в рублях)\n\n"
        "Например: <code>350000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_final_payment)
async def process_final_payment(message: Message, state: FSMContext):
    """Обработка окончательной оплаты"""
    
    try:
        final_payment = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if final_payment < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число (например: 350000):"
        )
        return
    
    await state.update_data(final_payment=final_payment)
    await state.set_state(AddObjectStates.enter_estimate_s3)
    
    await message.answer(
        "🧱 Шаг 7/11: Введите сумму С3 по смете (в рублях)\n\n"
        "Например: <code>200000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_estimate_s3)
async def process_estimate_s3(message: Message, state: FSMContext):
    """Обработка С3 по смете"""
    
    try:
        estimate_s3 = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if estimate_s3 < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число:"
        )
        return
    
    await state.update_data(estimate_s3=estimate_s3)
    await state.set_state(AddObjectStates.enter_estimate_works)
    
    await message.answer(
        "⚒ Шаг 8/11: Введите сумму работ по смете (в рублях)\n\n"
        "Например: <code>150000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_estimate_works)
async def process_estimate_works(message: Message, state: FSMContext):
    """Обработка работ по смете"""
    
    try:
        estimate_works = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if estimate_works < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число:"
        )
        return
    
    await state.update_data(estimate_works=estimate_works)
    await state.set_state(AddObjectStates.enter_estimate_supplies)
    
    await message.answer(
        "🧰 Шаг 9/11: Введите сумму расходников по смете (в рублях)\n\n"
        "Например: <code>50000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_estimate_supplies)
async def process_estimate_supplies(message: Message, state: FSMContext):
    """Обработка расходников по смете"""
    
    try:
        estimate_supplies = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if estimate_supplies < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число:"
        )
        return
    
    await state.update_data(estimate_supplies=estimate_supplies)
    await state.set_state(AddObjectStates.enter_estimate_overhead)
    
    await message.answer(
        "💰 Шаг 10/11: Введите сумму накладных расходов по смете (в рублях)\n\n"
        "Например: <code>30000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_estimate_overhead)
async def process_estimate_overhead(message: Message, state: FSMContext):
    """Обработка накладных по смете"""
    
    try:
        estimate_overhead = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if estimate_overhead < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число:"
        )
        return
    
    await state.update_data(estimate_overhead=estimate_overhead)
    await state.set_state(AddObjectStates.enter_estimate_transport)
    
    await message.answer(
        "🚚 Шаг 11/11: Введите сумму транспортных расходов по смете (в рублях)\n\n"
        "Например: <code>40000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_estimate_transport)
async def process_estimate_transport(message: Message, state: FSMContext):
    """Обработка транспортных расходов и показ резюме"""
    
    try:
        estimate_transport = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if estimate_transport < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число:"
        )
        return
    
    await state.update_data(estimate_transport=estimate_transport)
    await state.set_state(AddObjectStates.confirm_object)
    
    # Получаем все данные
    data = await state.get_data()
    
    # Формируем резюме
    from bot.services.calculations import format_currency
    
    start_date_str = data['start_date'].strftime("%d.%m.%Y") if data.get('start_date') else "—"
    end_date_str = data['end_date'].strftime("%d.%m.%Y") if data.get('end_date') else "—"
    total_income = data['prepayment'] + data['final_payment']
    
    summary = f"""
✅ <b>Проверка данных объекта</b>

🏗️ Объект: <b>{data['name']}</b>
📍 Адрес: {data.get('address', '—')}
👷 Бригадир: {data.get('foreman_name', '—')}
📅 Период: {start_date_str} — {end_date_str}

💸 <b>Финансы:</b>
Предоплата: {format_currency(data['prepayment'])}
Окончательная оплата: {format_currency(data['final_payment'])}
Всего поступлений: {format_currency(total_income)}

📊 <b>Смета:</b>
🧱 С3: {format_currency(data['estimate_s3'])}
⚒ Работы: {format_currency(data['estimate_works'])}
🧰 Расходники: {format_currency(data['estimate_supplies'])}
💰 Накладные: {format_currency(data['estimate_overhead'])}
🚚 Транспорт: {format_currency(estimate_transport)}

Все верно?
"""
    
    await message.answer(
        summary.strip(),
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard("object:save", "cancel")
    )


@router.callback_query(F.data == "object:save", AddObjectStates.confirm_object)
async def save_object(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Сохранить объект в базу данных"""
    
    data = await state.get_data()
    
    # Создаем объект в БД
    try:
        obj = await create_object(
            session=session,
            name=data['name'],
            created_by=user.id,
            address=data.get('address'),
            foreman_name=data.get('foreman_name'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
            prepayment=data['prepayment'],
            final_payment=data['final_payment'],
            estimate_s3=data['estimate_s3'],
            estimate_works=data['estimate_works'],
            estimate_supplies=data['estimate_supplies'],
            estimate_overhead=data['estimate_overhead'],
            estimate_transport=data['estimate_transport']
        )
        
        # Создаем папки на Google Drive (если настроено)
        if gdrive_service.service:
            try:
                folders = gdrive_service.create_object_folders(obj.name)
                if folders:
                    from database.crud import update_object_gdrive_folder
                    await update_object_gdrive_folder(session, obj.id, folders[0])
            except Exception as e:
                print(f"⚠️ Не удалось создать папки на Google Drive: {e}")
        
        await state.clear()
        
        await callback.message.edit_text(
            f"✅ <b>Объект успешно добавлен!</b>\n\n"
            f"Объект <b>'{obj.name}'</b> добавлен в Текущие объекты.\n\n"
            f"ID объекта: {obj.id}",
            parse_mode="HTML"
        )
        await callback.answer("✅ Объект создан")
        
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при создании объекта:\n{str(e)}"
        )
        await callback.answer("❌ Ошибка")


@router.callback_query(F.data == "skip")
async def skip_step(callback: CallbackQuery, state: FSMContext):
    """Пропустить необязательный шаг"""
    
    current_state = await state.get_state()
    
    if current_state == AddObjectStates.enter_address.state:
        await state.update_data(address=None)
        await state.set_state(AddObjectStates.enter_foreman)
        await callback.message.edit_text(
            "📝 Шаг 3/11: Введите имя бригадира/ответственного\n\n"
            "Или нажмите 'Пропустить'",
            reply_markup=get_skip_or_cancel()
        )
    
    elif current_state == AddObjectStates.enter_foreman.state:
        await state.update_data(foreman_name=None)
        await state.set_state(AddObjectStates.enter_dates)
        await callback.message.edit_text(
            "📝 Шаг 4/11: Введите даты работ\n\n"
            "Формат: <code>ДД.ММ.ГГГГ - ДД.ММ.ГГГГ</code>\n"
            "Например: <code>01.11.2025 - 30.11.2025</code>\n\n"
            "Или нажмите 'Пропустить'",
            parse_mode="HTML",
            reply_markup=get_skip_or_cancel()
        )
    
    elif current_state == AddObjectStates.enter_dates.state:
        await state.update_data(start_date=None, end_date=None)
        await state.set_state(AddObjectStates.enter_prepayment)
        await callback.message.edit_text(
            "💸 Шаг 5/11: Введите сумму предоплаты (в рублях)\n\n"
            "Например: <code>150000</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_button()
        )
    
    await callback.answer("Пропущено")


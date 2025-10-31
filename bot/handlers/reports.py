"""
Обработчики для генерации отчетов
"""
from datetime import datetime, timedelta
import calendar
from aiogram import Router, F
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole, ObjectStatus
from database.crud import (
    get_objects_by_status,
    get_object_by_id,
    get_files_by_object,
    get_objects_by_period,
    get_company_expenses_for_period,
    get_financial_years,
)
from bot.keyboards.reports_kb import (
    get_period_selection,
    get_completed_objects_list,
    get_years_keyboard,
    get_months_keyboard,
)
from bot.states.expense_states import ReportPeriodStates
from bot.services.report_generator import (
    generate_object_report,
    generate_period_report
)
from bot.utils.messaging import delete_message, send_new_message, get_bot_username
from bot.keyboards.main_menu import get_cancel_button

router = Router()

MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]


@router.callback_query(F.data == "report:object")
async def select_object_for_report(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Выбор завершенного объекта для отчета"""
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    await state.clear()
    
    # Получаем завершенные объекты
    objects = await get_objects_by_status(session, ObjectStatus.COMPLETED)
    
    await send_new_message(
        callback,
        "📄 <b>Отчёт за завершённый объект</b>\n\n"
        "Выберите объект:",
        parse_mode="HTML",
        reply_markup=get_completed_objects_list(objects),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("report:generate:"))
async def generate_object_report_callback(callback: CallbackQuery, user: User, session: AsyncSession):
    """Генерация отчета по объекту"""
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    object_id = int(callback.data.split(":")[2])
    
    # Получаем объект с загруженными связями
    obj = await get_object_by_id(session, object_id, load_relations=True)
    
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return
    
    # Получаем файлы
    files = await get_files_by_object(session, object_id)
    
    # Генерируем отчет
    bot_username = None
    if callback.message:
        bot_username = await get_bot_username(callback.message.bot)

    report = generate_object_report(obj, files, bot_username)
    
    await delete_message(callback.message)

    # Отправляем отчет (если он длинный, можем разбить на несколько сообщений)
    if len(report) > 4096:
        # Telegram ограничивает длину сообщения 4096 символами
        # Разбиваем на части
        parts = [report[i:i+4000] for i in range(0, len(report), 4000)]
        for part in parts:
            await callback.message.answer(part, parse_mode="HTML")
    else:
        await callback.message.answer(report, parse_mode="HTML")
    
    await callback.answer("✅ Отчёт сгенерирован")


@router.callback_query(F.data == "report:period")
async def select_report_period(callback: CallbackQuery, user: User, state: FSMContext):
    """Выбор периода для отчета"""
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    await state.clear()
    
    await send_new_message(
        callback,
        "📅 <b>Отчёт за период</b>\n\n"
        "Выберите период:",
        parse_mode="HTML",
        reply_markup=get_period_selection(),
    )
    await callback.answer()


@router.callback_query(F.data == "report:period:year")
async def report_period_year(callback: CallbackQuery, user: User, session: AsyncSession):
    """Выбор года для отчета"""

    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    years = await get_financial_years(session)
    if not years:
        years = [datetime.utcnow().year]

    await send_new_message(
        callback,
        "📅 <b>Отчёт за год</b>\n\nВыберите год:",
        parse_mode="HTML",
        reply_markup=get_years_keyboard(years, "report:period:year", "report:period"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("report:period:year:"))
async def generate_year_report(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    year = int(parts[3])

    start_date = datetime(year, 1, 1)
    end_date = datetime(year, 12, 31, 23, 59, 59)

    objects = await get_objects_by_period(session, start_date, end_date)
    company_totals = await get_company_expenses_for_period(session, start_date, end_date)
    report = generate_period_report(objects, f"{year} год", company_totals)

    await send_new_message(callback, report, parse_mode="HTML")
    await callback.answer("✅ Отчёт готов")


@router.callback_query(F.data == "report:period:month")
async def report_period_month(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    years = await get_financial_years(session)
    if not years:
        years = [datetime.utcnow().year]

    await send_new_message(
        callback,
        "📅 <b>Отчёт за месяц</b>\n\nВыберите год:",
        parse_mode="HTML",
        reply_markup=get_years_keyboard(years, "report:period:month:year", "report:period"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("report:period:month:year:"))
async def select_month_for_year(callback: CallbackQuery, user: User):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    year = int(parts[4])

    await send_new_message(
        callback,
        f"📅 <b>{year}</b> — выберите месяц:",
        parse_mode="HTML",
        reply_markup=get_months_keyboard(year, "report:period:month:select", "report:period:month"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("report:period:month:select:"))
async def generate_month_report(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    year = int(parts[4])
    month = int(parts[5])

    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)

    objects = await get_objects_by_period(session, start_date, end_date)
    company_totals = await get_company_expenses_for_period(session, start_date, end_date)
    report = generate_period_report(objects, f"{MONTH_NAMES[month - 1]} {year}", company_totals)

    await send_new_message(callback, report, parse_mode="HTML")
    await callback.answer("✅ Отчёт готов")


@router.callback_query(F.data == "report:period:range")
async def report_period_range(callback: CallbackQuery, user: User, state: FSMContext):
    """Запрос диапазона дат для отчета"""
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    await state.set_state(ReportPeriodStates.waiting_date_from)
    
    await send_new_message(
        callback,
        f"📅 <b>Отчёт за диапазон дат</b>\n\n"
        f"Введите дату начала в формате <code>ДД.ММ.ГГГГ</code>\n"
        f"Например: <code>01.10.2025</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.message(ReportPeriodStates.waiting_date_from)
async def process_date_from(message: Message, state: FSMContext):
    """Обработка даты начала"""
    
    try:
        date_from = datetime.strptime(message.text.strip(), "%d.%m.%Y")
    except:
        await message.answer(
            "❌ Неверный формат даты. Введите в формате <code>ДД.ММ.ГГГГ</code>:",
            parse_mode="HTML"
        )
        return
    
    await state.update_data(date_from=date_from)
    await state.set_state(ReportPeriodStates.waiting_date_to)
    
    await message.answer(
        f"📅 Дата начала: {date_from.strftime('%d.%m.%Y')}\n\n"
        f"Теперь введите дату окончания в формате <code>ДД.ММ.ГГГГ</code>:",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(ReportPeriodStates.waiting_date_to)
async def process_date_to(message: Message, user: User, session: AsyncSession, state: FSMContext):
    """Обработка даты окончания и генерация отчета"""
    
    try:
        date_to = datetime.strptime(message.text.strip(), "%d.%m.%Y")
        date_to = date_to.replace(hour=23, minute=59, second=59)  # До конца дня
    except:
        await message.answer(
            "❌ Неверный формат даты. Введите в формате <code>ДД.ММ.ГГГГ</code>:",
            parse_mode="HTML"
        )
        return
    
    data = await state.get_data()
    date_from = data['date_from']
    
    if date_to < date_from:
        await message.answer(
            "❌ Дата окончания не может быть раньше даты начала. Попробуйте снова:"
        )
        return
    
    await state.clear()
    
    # Получаем объекты за период
    objects = await get_objects_by_period(session, date_from, date_to)
    
    # Генерируем отчет
    period_str = f"{date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}"
    company_totals = await get_company_expenses_for_period(session, date_from, date_to)

    report = generate_period_report(objects, period_str, company_totals)
    
    await message.answer(report, parse_mode="HTML")



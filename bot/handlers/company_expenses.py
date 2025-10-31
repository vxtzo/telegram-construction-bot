"""Обработчики для управления расходами фирмы"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional
from urllib.parse import quote_plus, unquote_plus

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_menu import get_cancel_button
from bot.services.calculations import format_currency
from bot.states.company_expense_states import CompanyExpenseStates, CompanyRecurringExpenseStates
from bot.utils.messaging import send_new_message
from database.crud import (
    create_company_expense,
    create_company_recurring_expense,
    get_company_expense_categories,
    get_company_expenses_by_category,
    get_company_recurring_categories,
    get_company_recurring_by_category,
    delete_company_expense,
    delete_company_recurring_expense,
    create_company_expense_log,
)
from database.models import User, UserRole


router = Router()


ONE_TIME_LOG_TYPE = "one_time"
RECURRING_LOG_TYPE = "recurring"


def _format_user_name(user: Optional[User]) -> str:
    if not user:
        return "—"
    return user.full_name or user.username or f"ID {user.telegram_id}"


def _encode_token(value: str) -> str:
    return quote_plus(value, safe="")


def _decode_token(value: str) -> str:
    return unquote_plus(value)


def _company_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💸 Разовые расходы", callback_data="company:one_time"))
    builder.row(InlineKeyboardButton(text="♻️ Ежемесячные расходы", callback_data="company:recurring"))
    builder.row(InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu"))
    return builder.as_markup()


async def _send_one_time_overview(message_or_callback, session: AsyncSession) -> None:
    categories = await get_company_expense_categories(session)

    if isinstance(message_or_callback, CallbackQuery):
        sender = message_or_callback
        send = send_new_message
    else:
        sender = message_or_callback
        async def send(sender, text, **kwargs):
            await sender.answer(text, **kwargs)
    
    if not categories:
        await send(
            sender,
            "💸 <b>Разовые расходы</b>\n\nПока нет записей.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить", callback_data="company:one_time:add")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu")],
                ]
            ),
        )
        return

    overall_total = sum(total for _, total, _ in categories)
    overall_count = sum(count for _, _, count in categories)

    lines = [
        "💸 <b>Разовые расходы</b>",
        f"Всего суммой: {format_currency(overall_total)}",
        f"Записей: {overall_count}",
        "",
        "Категории:",
    ]
    keyboard = InlineKeyboardBuilder()

    for idx, (category, total, count) in enumerate(categories, start=1):
        token = _encode_token(category)
        lines.append(
            f"\n{idx}. <b>{category}</b>\n"
            f"   💰 {format_currency(total)} • записей: {count}"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"{category} • {format_currency(total)}",
                callback_data=f"company:one_time:category:{token}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="➕ Добавить", callback_data="company:one_time:add"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu"))

    await send(
        sender,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


async def _send_recurring_overview(message_or_callback, session: AsyncSession) -> None:
    categories = await get_company_recurring_categories(session)

    if isinstance(message_or_callback, CallbackQuery):
        sender = message_or_callback
        send = send_new_message
    else:
        sender = message_or_callback
        async def send(sender, text, **kwargs):
            await sender.answer(text, **kwargs)

    if not categories:
        await send(
            sender,
            "♻️ <b>Ежемесячные расходы</b>\n\nПока нет записей.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu")],
                ]
            ),
        )
        return

    overall_total = sum(total for _, total, _ in categories)
    overall_count = sum(count for _, _, count in categories)

    lines = [
        "♻️ <b>Ежемесячные расходы</b>",
        f"Всего суммой: {format_currency(overall_total)}",
        f"Записей: {overall_count}",
        "",
        "Категории:",
    ]
    keyboard = InlineKeyboardBuilder()

    for idx, (category, total, count) in enumerate(categories, start=1):
        token = _encode_token(category)
        lines.append(
            f"\n{idx}. <b>{category}</b>\n"
            f"   💰 {format_currency(total)} • записей: {count}"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"{category} • {format_currency(total)}",
                callback_data=f"company:recurring:category:{token}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu"))

    await send(
        sender,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


async def _send_one_time_category(callback: CallbackQuery, session: AsyncSession, category: str) -> None:
    expenses = await get_company_expenses_by_category(session, category)
    token = _encode_token(category)

    if not expenses:
        await send_new_message(
            callback,
            f"💸 <b>{category}</b>\n\nЗаписей нет.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить", callback_data="company:one_time:add")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="company:one_time")],
                ]
            ),
        )
        return

    total = sum(exp.amount for exp in expenses)
    lines = [
        f"💸 <b>{category}</b>",
        f"Всего: {format_currency(total)}",
        "",
        "📄 Записи:",
    ]

    keyboard = InlineKeyboardBuilder()
    for exp in expenses:
        date_str = exp.date.strftime("%d.%m.%Y")
        user_name = _format_user_name(exp.user)
        lines.append(
            f"\n• {date_str} — {format_currency(exp.amount)}\n"
            f"  Добавил: {user_name}\n"
            f"  {exp.description or '—'}"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"🗑 {date_str} • {format_currency(exp.amount)}",
                callback_data=f"company:one_time:delete:{exp.id}:{token}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="➕ Добавить", callback_data="company:one_time:add"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="company:one_time"))

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


async def _send_recurring_category(callback: CallbackQuery, session: AsyncSession, category: str) -> None:
    expenses = await get_company_recurring_by_category(session, category)
    token = _encode_token(category)

    if not expenses:
        await send_new_message(
            callback,
            f"♻️ <b>{category}</b>\n\nЗаписей нет.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="company:recurring")],
                ]
            ),
        )
        return

    total = sum(exp.amount for exp in expenses)
    lines = [
        f"♻️ <b>{category}</b>",
        f"Всего: {format_currency(total)}",
        "",
        "📄 Записи:",
    ]

    keyboard = InlineKeyboardBuilder()
    for exp in expenses:
        period_str = f"{exp.period_month:02d}.{exp.period_year}"
        user_name = _format_user_name(exp.user)
        lines.append(
            f"\n• {period_str} — {format_currency(exp.amount)}\n"
            f"  Добавил: {user_name}\n"
            f"  {exp.description or '—'}"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"🗑 {period_str} • {format_currency(exp.amount)}",
                callback_data=f"company:recurring:delete:{exp.id}:{token}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="company:recurring"))

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


@router.message(F.text == "💼 Расходы фирмы")
async def company_expenses_menu(message: Message, user: User, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для управления расходами фирмы.")
        return

    await state.clear()
    await message.answer(
        "💼 <b>Расходы фирмы</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=_company_menu_keyboard(),
    )


@router.callback_query(F.data == "company:menu")
async def company_menu_callback(callback: CallbackQuery, user: User, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.clear()
    await send_new_message(
        callback,
        "💼 <b>Расходы фирмы</b>\n\nВыберите раздел:",
        parse_mode="HTML",
        reply_markup=_company_menu_keyboard(),
    )


@router.callback_query(F.data == "company:one_time")
async def company_one_time_overview(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.clear()
    await _send_one_time_overview(callback, session)
    await callback.answer()


@router.callback_query(F.data == "company:recurring")
async def company_recurring_overview(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.clear()
    await _send_recurring_overview(callback, session)
    await callback.answer()


@router.callback_query(F.data.startswith("company:one_time:category:"))
async def company_one_time_category(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    category = _decode_token(callback.data.split(":")[-1])
    await _send_one_time_category(callback, session, category)
    await callback.answer()


@router.callback_query(F.data.startswith("company:recurring:category:"))
async def company_recurring_category(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    category = _decode_token(callback.data.split(":")[-1])
    await _send_recurring_category(callback, session, category)
    await callback.answer()


@router.callback_query(F.data == "company:one_time:add")
async def company_add_one_time(callback: CallbackQuery, user: User, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.set_state(CompanyExpenseStates.choosing_category)
    await state.update_data(flow="one_time")
    await send_new_message(
        callback,
        "🆕 <b>Разовый расход</b>\n\nВведите категорию (например: 'Офис', 'Налоги').",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.callback_query(F.data == "company:recurring:add")
async def company_add_recurring(callback: CallbackQuery, user: User, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.set_state(CompanyRecurringExpenseStates.choosing_category)
    await state.update_data(flow="recurring")
    await send_new_message(
        callback,
        "🆕 <b>Ежемесячный расход</b>\n\nВведите категорию (например: 'Аренда', 'Зарплаты').",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.message(CompanyExpenseStates.choosing_category)
async def process_one_time_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("⚠️ Категория не может быть пустой. Попробуйте снова.")
        return

    await state.update_data(category=category)
    await state.set_state(CompanyExpenseStates.waiting_amount)
    await message.answer(
        "Введите сумму (например: 25000)",
        reply_markup=get_cancel_button(),
    )


@router.message(CompanyExpenseStates.waiting_amount)
async def process_one_time_amount(message: Message, state: FSMContext):
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError, AttributeError):
        await message.answer("❌ Некорректная сумма. Пример: 25000")
        return

    await state.update_data(amount=amount)
    await state.set_state(CompanyExpenseStates.waiting_date)
    await message.answer(
        "Введите дату расхода в формате <code>ДД.ММ.ГГГГ</code> (по умолчанию сегодня)",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(CompanyExpenseStates.waiting_date)
async def process_one_time_date(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        date = datetime.utcnow()
    else:
        try:
            date = datetime.strptime(text, "%d.%m.%Y")
        except ValueError:
            await message.answer("❌ Неверная дата. Используйте формат ДД.ММ.ГГГГ")
            return

    await state.update_data(date=date)
    await state.set_state(CompanyExpenseStates.waiting_description)
    await message.answer(
        "Добавьте описание или отправьте '-' для пропуска.",
        reply_markup=get_cancel_button(),
    )


@router.message(CompanyExpenseStates.waiting_description)
async def finalize_one_time(message: Message, user: User, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    amount: Decimal = data.get("amount")
    date: datetime = data.get("date")
    description_input = message.text.strip()
    description = None if description_input == "-" else description_input

    expense = await create_company_expense(
        session=session,
        category=category,
        amount=amount,
        date=date,
        description=description,
        added_by=user.id,
    )

    await create_company_expense_log(
        session=session,
        expense_type=ONE_TIME_LOG_TYPE,
        entity_id=expense.id,
        action="create",
        description=f"Добавлен расход {category}: {format_currency(amount)}",
        user_id=user.id,
    )

    await state.clear()
    await message.answer(
        "✅ Разовый расход добавлен.",
        parse_mode="HTML",
    )
    await _send_one_time_overview(message, session)


@router.message(CompanyRecurringExpenseStates.choosing_category)
async def process_recurring_category(message: Message, state: FSMContext):
    category = message.text.strip()
    if not category:
        await message.answer("⚠️ Категория не может быть пустой. Попробуйте снова.")
        return

    await state.update_data(category=category)
    await state.set_state(CompanyRecurringExpenseStates.waiting_amount)
    await message.answer("Введите сумму (например: 40000)", reply_markup=get_cancel_button())


@router.message(CompanyRecurringExpenseStates.waiting_amount)
async def process_recurring_amount(message: Message, state: FSMContext):
    try:
        amount = Decimal(message.text.replace(" ", "").replace(",", "."))
        if amount <= 0:
            raise InvalidOperation
    except (InvalidOperation, ValueError, AttributeError):
        await message.answer("❌ Некорректная сумма. Пример: 40000")
        return

    await state.update_data(amount=amount)
    await state.set_state(CompanyRecurringExpenseStates.waiting_period)
    await message.answer(
        "Введите месяц и год в формате <code>ММ.ГГГГ</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )


@router.message(CompanyRecurringExpenseStates.waiting_period)
async def process_recurring_period(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        period = datetime.strptime(text, "%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте ММ.ГГГГ")
        return

    await state.update_data(period_month=period.month, period_year=period.year)
    await state.set_state(CompanyRecurringExpenseStates.waiting_description)
    await message.answer("Добавьте описание или отправьте '-' для пропуска.", reply_markup=get_cancel_button())


@router.message(CompanyRecurringExpenseStates.waiting_description)
async def finalize_recurring(message: Message, user: User, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    category = data.get("category")
    amount: Decimal = data.get("amount")
    month = data.get("period_month")
    year = data.get("period_year")
    description_input = message.text.strip()
    description = None if description_input == "-" else description_input

    expense = await create_company_recurring_expense(
        session=session,
        category=category,
        amount=amount,
        period_month=month,
        period_year=year,
        description=description,
        added_by=user.id,
    )

    await create_company_expense_log(
        session=session,
        expense_type=RECURRING_LOG_TYPE,
        entity_id=expense.id,
        action="create",
        description=f"Добавлен ежемесячный расход {category}: {format_currency(amount)} за {month:02d}.{year}",
        user_id=user.id,
    )

    await state.clear()
    await message.answer("✅ Ежемесячный расход добавлен.", parse_mode="HTML")
    await _send_recurring_overview(message, session)


@router.callback_query(F.data.startswith("company:one_time:delete:"))
async def delete_one_time(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[3])
    token = parts[4]
    category = _decode_token(token)

    success = await delete_company_expense(session, expense_id)
    if not success:
        await callback.answer("❌ Не удалось удалить расход", show_alert=True)
        return

    await create_company_expense_log(
        session=session,
        expense_type=ONE_TIME_LOG_TYPE,
        entity_id=expense_id,
        action="delete",
        description=f"Удалён разовый расход ID {expense_id}",
        user_id=user.id,
    )

    await _send_one_time_category(callback, session, category)
    await callback.answer("🗑 Удалено")


@router.callback_query(F.data.startswith("company:recurring:delete:"))
async def delete_recurring(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[3])
    token = parts[4]
    category = _decode_token(token)

    success = await delete_company_recurring_expense(session, expense_id)
    if not success:
        await callback.answer("❌ Не удалось удалить расход", show_alert=True)
        return

    await create_company_expense_log(
        session=session,
        expense_type=RECURRING_LOG_TYPE,
        entity_id=expense_id,
        action="delete",
        description=f"Удалён ежемесячный расход ID {expense_id}",
        user_id=user.id,
    )

    await _send_recurring_category(callback, session, category)
    await callback.answer("🗑 Удалено")

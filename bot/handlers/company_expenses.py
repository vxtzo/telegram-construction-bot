"""Обработчики для управления расходами фирмы"""
from __future__ import annotations

import calendar
import hashlib
import os
import tempfile
from collections import OrderedDict
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional, Union
from urllib.parse import quote_plus, unquote_plus

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.main_menu import get_cancel_button
from bot.services.ai_parser import (
    parse_company_expense_text,
    parse_voice_company_expense,
)
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

Sender = Union[Message, CallbackQuery]

ONE_TIME_LOG_TYPE = "one_time"
RECURRING_LOG_TYPE = "recurring"

MONTH_NAMES = [
    "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

_TOKEN_CACHE: OrderedDict[str, str] = OrderedDict()
_TOKEN_CACHE_LIMIT = 512
_TOKEN_HASH_PREFIX = "h:"


def _format_user_name(user: Optional[User]) -> str:
    if not user:
        return "—"
    return user.full_name or user.username or f"ID {user.telegram_id}"


def _encode_token(value: str, max_length: int = 28) -> str:
    encoded = quote_plus(value, safe="")
    if len(encoded) <= max_length:
        return encoded

    hash_length = max(6, max_length - len(_TOKEN_HASH_PREFIX))
    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:hash_length]
    token = f"{_TOKEN_HASH_PREFIX}{digest}"

    _TOKEN_CACHE[token] = value
    _TOKEN_CACHE.move_to_end(token)
    while len(_TOKEN_CACHE) > _TOKEN_CACHE_LIMIT:
        _TOKEN_CACHE.popitem(last=False)

    return token


async def _decode_token(token: str, session: AsyncSession, *, recurring: bool = False) -> str:
    if token in _TOKEN_CACHE:
        _TOKEN_CACHE.move_to_end(token)
        return _TOKEN_CACHE[token]

    if token.startswith(_TOKEN_HASH_PREFIX):
        digest = token[len(_TOKEN_HASH_PREFIX):]
        categories_source = (
            await get_company_recurring_categories(session)
            if recurring
            else await get_company_expense_categories(session)
        )

        for category_name, *_ in categories_source:
            candidate = hashlib.sha1(category_name.encode("utf-8")).hexdigest()[: len(digest)]
            if candidate == digest:
                _TOKEN_CACHE[token] = category_name
                _TOKEN_CACHE.move_to_end(token)
                while len(_TOKEN_CACHE) > _TOKEN_CACHE_LIMIT:
                    _TOKEN_CACHE.popitem(last=False)
                return category_name

        raise ValueError("Категория не найдена для токена")

    return unquote_plus(token)


async def _reply(sender: Sender, text: str, **kwargs) -> None:
    if isinstance(sender, CallbackQuery):
        await send_new_message(sender, text, **kwargs)
    else:
        await sender.answer(text, **kwargs)


def _company_menu_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💸 Разовые расходы", callback_data="company:one_time"))
    builder.row(InlineKeyboardButton(text="♻️ Ежемесячные расходы", callback_data="company:recurring"))
    builder.row(InlineKeyboardButton(text="🔙 В главное меню", callback_data="main_menu"))
    return builder.as_markup()


def _one_time_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Сохранить", callback_data="company:one_time:save"))
    builder.row(
        InlineKeyboardButton(text="📅 Сегодня", callback_data="company:one_time:date:today"),
        InlineKeyboardButton(text="📅 Вчера", callback_data="company:one_time:date:yesterday"),
    )
    builder.row(InlineKeyboardButton(text="📆 Указать дату", callback_data="company:one_time:date:manual"))
    builder.row(InlineKeyboardButton(text="🔁 Ввести заново", callback_data="company:one_time:retry"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="company:cancel"))
    return builder.as_markup()


def _recurring_confirm_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="✅ Сохранить", callback_data="company:recurring:save"))
    builder.row(InlineKeyboardButton(text="📅 День оплаты", callback_data="company:recurring:day"))
    builder.row(InlineKeyboardButton(text="📆 Начало", callback_data="company:recurring:start"))
    builder.row(InlineKeyboardButton(text="🔁 Ввести заново", callback_data="company:recurring:retry"))
    builder.row(InlineKeyboardButton(text="❌ Отмена", callback_data="company:cancel"))
    return builder.as_markup()


async def _send_one_time_overview(sender: Sender, session: AsyncSession) -> None:
    # Получаем все разовые расходы без группировки по категориям
    from database.crud import get_company_expenses_by_category, get_company_expense_categories
    
    categories = await get_company_expense_categories(session)

    if not categories:
        await _reply(
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

    # Собираем все расходы из всех категорий
    all_expenses = []
    for category, _, _ in categories:
        expenses = await get_company_expenses_by_category(session, category)
        all_expenses.extend(expenses)
    
    if not all_expenses:
        await _reply(
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

    # Сортируем по дате (новые сверху)
    all_expenses.sort(key=lambda x: x.date, reverse=True)
    
    overall_total = sum(exp.amount for exp in all_expenses)

    lines = [
        "💸 <b>Разовые расходы</b>",
        f"Всего: {format_currency(overall_total)}",
        f"Записей: {len(all_expenses)}",
        "",
        "📄 Список:",
    ]

    keyboard = InlineKeyboardBuilder()

    for exp in all_expenses:
        date_str = exp.date.strftime("%d.%m.%Y")
        lines.append(
            f"\n• {exp.category} — {format_currency(exp.amount)}\n"
            f"  📅 {date_str}"
        )
        # Создаём короткий токен для callback
        token = _encode_token(exp.category)
        keyboard.row(
            InlineKeyboardButton(
                text=f"📄 {date_str} • {exp.category} • {format_currency(exp.amount)}",
                callback_data=f"company:one_time:view:{exp.id}:{token}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="➕ Добавить", callback_data="company:one_time:add"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu"))

    await _reply(
        sender,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


async def _send_recurring_overview(sender: Sender, session: AsyncSession) -> None:
    # Получаем все активные постоянные расходы без группировки по категориям
    from database.crud import get_company_recurring_by_category, get_company_recurring_categories
    
    # Сначала получим все категории, потом все расходы
    categories = await get_company_recurring_categories(session)
    
    if not categories:
        await _reply(
            sender,
            "♻️ <b>Постоянные расходы</b>\n\nПока нет записей.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu")],
                ]
            ),
        )
        return

    # Собираем все расходы из всех категорий
    all_expenses = []
    for category, _, _ in categories:
        expenses = await get_company_recurring_by_category(session, category)
        all_expenses.extend(expenses)
    
    if not all_expenses:
        await _reply(
            sender,
            "♻️ <b>Постоянные расходы</b>\n\nПока нет записей.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu")],
                ]
            ),
        )
        return

    overall_total = sum(exp.amount for exp in all_expenses)

    lines = [
        "♻️ <b>Постоянные расходы</b>",
        f"Всего ежемесячно: {format_currency(overall_total)}",
        f"Записей: {len(all_expenses)}",
        "",
        "📄 Список:",
    ]

    keyboard = InlineKeyboardBuilder()

    for exp in all_expenses:
        first_payment = _first_payment_date(exp.start_year, exp.start_month, exp.day_of_month)
        lines.append(
            f"\n• {exp.category} — {format_currency(exp.amount)}\n"
            f"  📅 {exp.day_of_month}-го числа с {first_payment.strftime('%d.%m.%Y')}"
        )
        # Создаём короткий токен для callback
        token = _encode_token(exp.category)
        keyboard.row(
            InlineKeyboardButton(
                text=f"📄 {exp.category} • {format_currency(exp.amount)}",
                callback_data=f"company:recurring:view:{exp.id}:{token}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add"))
    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data="company:menu"))

    await _reply(
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
        lines.append(
            f"\n• {date_str} — {format_currency(exp.amount)}\n"
            f"  👤 { _format_user_name(exp.user) }\n"
            f"  {exp.description or '—'}"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"📄 {date_str} • {format_currency(exp.amount)}",
                callback_data=f"company:one_time:view:{exp.id}:{token}"
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


def _first_payment_date(year: int, month: int, day: int) -> datetime:
    last_day = calendar.monthrange(year, month)[1]
    safe_day = min(day, last_day)
    return datetime(year, month, safe_day)


async def _send_recurring_category(callback: CallbackQuery, session: AsyncSession, category: str) -> None:
    templates = await get_company_recurring_by_category(session, category)
    token = _encode_token(category)

    if not templates:
        await send_new_message(
            callback,
            f"♻️ <b>{category}</b>\n\nАктивных шаблонов нет.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="➕ Добавить", callback_data="company:recurring:add")],
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="company:recurring")],
                ]
            ),
        )
        return

    total = sum(exp.amount for exp in templates)
    lines = [
        f"♻️ <b>{category}</b>",
        f"Общая сумма: {format_currency(total)}",
        "",
        "📄 Постоянные расходы:",
    ]

    keyboard = InlineKeyboardBuilder()
    for exp in templates:
        first_payment = _first_payment_date(exp.start_year, exp.start_month, exp.day_of_month)
        end_label = (
            f"до {exp.end_month:02d}.{exp.end_year}"
            if exp.end_month and exp.end_year
            else "бессрочно"
        )
        lines.append(
            f"\n• {format_currency(exp.amount)} — {exp.day_of_month}-го числа\n"
            f"  Старт: {first_payment.strftime('%d.%m.%Y')} ({end_label})\n"
            f"  👤 { _format_user_name(exp.user) }\n"
            f"  {exp.description or '—'}"
        )
        keyboard.row(
            InlineKeyboardButton(
                text=f"📄 {format_currency(exp.amount)} • {exp.day_of_month}-го",
                callback_data=f"company:recurring:view:{exp.id}:{token}"
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


def _ensure_positive(amount: Decimal) -> bool:
    try:
        return Decimal(amount) > 0
    except Exception:
        return False


def _format_rub(value: Decimal) -> str:
    return format_currency(Decimal(value))


async def _show_one_time_confirmation(sender: Sender, data: dict) -> None:
    date_value = data.get("date")
    try:
        date_obj = datetime.strptime(date_value, "%Y-%m-%d")
        date_label = date_obj.strftime("%d.%m.%Y")
    except Exception:
        date_label = date_value

    lines = [
        "✅ <b>Проверьте данные разового расхода</b>",
        "",
        f"📂 Категория: {data['category']}",
        f"📅 Дата: {date_label}",
        f"💰 Сумма: {_format_rub(data['amount'])}",
        f"📝 Описание: {data['description'] or '—'}",
    ]

    await _reply(
        sender,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_one_time_confirm_keyboard(),
    )


async def _show_recurring_confirmation(sender: Sender, data: dict) -> None:
    day = int(data['day_of_month'])
    start_month = int(data['start_month'])
    start_year = int(data['start_year'])
    first_payment = _first_payment_date(start_year, start_month, day)

    lines = [
        "✅ <b>Проверьте данные ежемесячного расхода</b>",
        "",
        f"📂 Категория: {data['category']}",
        f"💰 Ежемесячно: {_format_rub(data['amount'])}",
        f"📅 День оплаты: {day}-го числа",
        f"📆 Начало: {first_payment.strftime('%d.%m.%Y')}",
        f"📝 Описание: {data['description'] or '—'}",
    ]

    await _reply(
        sender,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=_recurring_confirm_keyboard(),
    )


# ===== Меню и навигация =====


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
    await callback.answer()


@router.callback_query(F.data == "company:cancel")
async def cancel_company_flow(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await send_new_message(
        callback,
        "❌ Действие отменено.",
        reply_markup=_company_menu_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer("Отменено")


# ===== Разовые расходы =====


@router.callback_query(F.data == "company:one_time")
async def company_one_time_overview(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.clear()
    await _send_one_time_overview(callback, session)
    await callback.answer()


@router.callback_query(F.data == "company:one_time:add")
async def company_add_one_time(callback: CallbackQuery, user: User, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.set_state(CompanyExpenseStates.waiting_input)
    await state.update_data(flow="one_time")
    await send_new_message(
        callback,
        "🆕 <b>Разовый расход</b>\n\nОпишите расход текстом или пришлите голосовое сообщение — ИИ заполнит карточку автоматически.",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.message(CompanyExpenseStates.waiting_input, F.text)
async def process_one_time_text(message: Message, user: User, session: AsyncSession, state: FSMContext):
    parsed = await parse_company_expense_text(message.text)

    if not _ensure_positive(parsed["amount"]):
        await message.answer(
            "⚠️ Не удалось определить сумму. Попробуйте описать расход подробнее.",
            reply_markup=get_cancel_button(),
        )
        return

    await state.update_data(
        category=parsed["category"].strip() or "Разовый расход",
        amount=parsed["amount"],
        date=parsed["date"],
        description=parsed.get("description", "").strip(),
    )
    await state.set_state(CompanyExpenseStates.confirm)

    await _show_one_time_confirmation(message, await state.get_data())


@router.message(CompanyExpenseStates.waiting_input, F.voice)
async def process_one_time_voice(message: Message, user: User, session: AsyncSession, state: FSMContext):
    await message.answer("🎤 Распознаю голос...")

    try:
        voice = message.voice
        file = await message.bot.get_file(voice.file_id)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_path = tmp_file.name
            await message.bot.download_file(file.file_path, tmp_path)

        parsed = await parse_voice_company_expense(tmp_path, kind="one_time")
        os.unlink(tmp_path)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Ошибка обработки голоса (company expense): {exc}")
        await message.answer("❌ Не удалось распознать голос. Попробуйте ввести текстом.", reply_markup=get_cancel_button())
        return

    if not _ensure_positive(parsed["amount"]):
        await message.answer(
            "⚠️ Не удалось определить сумму. Попробуйте повторить голосовое сообщение или введите текстом.",
            reply_markup=get_cancel_button(),
        )
        return

    await state.update_data(
        category=parsed["category"].strip() or "Разовый расход",
        amount=parsed["amount"],
        date=parsed["date"],
        description=parsed.get("description", "").strip(),
    )
    await state.set_state(CompanyExpenseStates.confirm)

    await _show_one_time_confirmation(message, await state.get_data())


@router.callback_query(F.data == "company:one_time:retry")
async def retry_one_time(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CompanyExpenseStates.waiting_input)
    await send_new_message(
        callback,
        "📝 Попробуйте описать расход ещё раз:",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.callback_query(F.data == "company:one_time:date:today")
async def set_one_time_today(callback: CallbackQuery, state: FSMContext):
    await state.update_data(date=datetime.utcnow().strftime("%Y-%m-%d"))
    await _show_one_time_confirmation(callback, await state.get_data())
    await callback.answer()


@router.callback_query(F.data == "company:one_time:date:yesterday")
async def set_one_time_yesterday(callback: CallbackQuery, state: FSMContext):
    yesterday = datetime.utcnow() - timedelta(days=1)
    await state.update_data(date=yesterday.strftime("%Y-%m-%d"))
    await _show_one_time_confirmation(callback, await state.get_data())
    await callback.answer()


@router.callback_query(F.data == "company:one_time:date:manual")
async def ask_one_time_date(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CompanyExpenseStates.waiting_date_manual)
    await send_new_message(
        callback,
        "📅 Введите дату в формате <code>ДД.ММ.ГГГГ</code>.",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.message(CompanyExpenseStates.waiting_date_manual)
async def set_one_time_manual_date(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        parsed = datetime.strptime(text, "%d.%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте <code>ДД.ММ.ГГГГ</code>.", parse_mode="HTML")
        return

    await state.update_data(date=parsed.strftime("%Y-%m-%d"))
    await state.set_state(CompanyExpenseStates.confirm)
    await _show_one_time_confirmation(message, await state.get_data())


@router.callback_query(F.data == "company:one_time:save")
async def save_one_time_expense(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    expense = await create_company_expense(
        session=session,
        category=data["category"],
        amount=Decimal(data["amount"]),
        date=datetime.strptime(data["date"], "%Y-%m-%d"),
        description=data.get("description"),
        added_by=user.id,
    )

    await create_company_expense_log(
        session=session,
        expense_type=ONE_TIME_LOG_TYPE,
        entity_id=expense.id,
        action="create",
        description=f"Добавлен разовый расход {expense.category}: {_format_rub(expense.amount)}",
        user_id=user.id,
    )

    await send_new_message(
        callback,
        "✅ Разовый расход добавлен.",
        parse_mode="HTML",
    )
    await _send_one_time_overview(callback, session)
    await callback.answer("Сохранено")


@router.callback_query(F.data.startswith("company:one_time:category:"))
async def company_one_time_category(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    token = callback.data.split(":")[-1]
    try:
        category = await _decode_token(token, session=session)
    except ValueError:
        await callback.answer("❌ Не удалось определить категорию. Обновите список.", show_alert=True)
        return

    await _send_one_time_category(callback, session, category)
    await callback.answer()


@router.callback_query(F.data.startswith("company:one_time:view:"))
async def view_one_time_expense(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[3])
    token = parts[4]
    
    try:
        category = await _decode_token(token, session=session)
    except ValueError:
        await callback.answer("❌ Не удалось определить категорию. Обновите список.", show_alert=True)
        return

    # Получаем расход из БД
    from database.crud import get_company_expenses_by_category
    expenses = await get_company_expenses_by_category(session, category)
    expense = next((e for e in expenses if e.id == expense_id), None)
    
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return

    # Формируем детальную карточку
    date_str = expense.date.strftime("%d.%m.%Y")
    lines = [
        f"💸 <b>Разовый расход</b>",
        "",
        f"📂 Категория: {category}",
        f"📅 Дата: {date_str}",
        f"💰 Сумма: {format_currency(expense.amount)}",
        f"👤 Добавил: {_format_user_name(expense.user)}",
        f"📝 Описание: {expense.description or '—'}",
    ]

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"company:one_time:delete:{expense_id}:{token}"
        )
    )
    keyboard.row(
        InlineKeyboardButton(
            text="🔙 К списку",
            callback_data=f"company:one_time:category:{token}"
        )
    )

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("company:one_time:delete:"))
async def delete_one_time(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[3])
    token = parts[4]
    try:
        category = await _decode_token(token, session=session)
    except ValueError:
        await callback.answer("❌ Не удалось определить категорию. Обновите список.", show_alert=True)
        return

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


# ===== Ежемесячные расходы =====


@router.callback_query(F.data == "company:recurring")
async def company_recurring_overview(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.clear()
    await _send_recurring_overview(callback, session)
    await callback.answer()


@router.callback_query(F.data == "company:recurring:add")
async def company_add_recurring(callback: CallbackQuery, user: User, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    await state.set_state(CompanyRecurringExpenseStates.waiting_input)
    await state.update_data(flow="recurring")
    await send_new_message(
        callback,
        "🆕 <b>Ежемесячный расход</b>\n\nОпишите платеж текстом или голосом. Укажите сумму и, по возможности, дату/день оплаты.",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


async def _store_recurring_data(state: FSMContext, parsed: dict) -> None:
    start_dt = datetime.strptime(parsed["start_date"], "%Y-%m-%d")
    day = max(1, min(int(parsed["day_of_month"]), 31))

    await state.update_data(
        category=parsed["category"].strip() or "Ежемесячный расход",
        amount=parsed["amount"],
        day_of_month=day,
        start_month=start_dt.month,
        start_year=start_dt.year,
        description=parsed.get("description", "").strip(),
    )


@router.message(CompanyRecurringExpenseStates.waiting_input, F.text)
async def process_recurring_text(message: Message, user: User, session: AsyncSession, state: FSMContext):
    parsed = await parse_company_expense_text(message.text, kind="recurring")

    if not _ensure_positive(parsed["amount"]):
        await message.answer(
            "⚠️ Не удалось определить сумму. Опишите платеж подробнее.",
            reply_markup=get_cancel_button(),
        )
        return

    await _store_recurring_data(state, parsed)
    await state.set_state(CompanyRecurringExpenseStates.confirm)

    await _show_recurring_confirmation(message, await state.get_data())


@router.message(CompanyRecurringExpenseStates.waiting_input, F.voice)
async def process_recurring_voice(message: Message, user: User, session: AsyncSession, state: FSMContext):
    await message.answer("🎤 Распознаю голос...")

    try:
        voice = message.voice
        file = await message.bot.get_file(voice.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as tmp_file:
            tmp_path = tmp_file.name
            await message.bot.download_file(file.file_path, tmp_path)

        parsed = await parse_voice_company_expense(tmp_path, kind="recurring")
        os.unlink(tmp_path)
    except Exception as exc:  # noqa: BLE001
        print(f"❌ Ошибка обработки голоса (company recurring): {exc}")
        await message.answer("❌ Не удалось распознать голос. Попробуйте текстом.", reply_markup=get_cancel_button())
        return

    if not _ensure_positive(parsed["amount"]):
        await message.answer(
            "⚠️ Не удалось определить сумму. Попробуйте повторить голосовое сообщение или опишите текстом.",
            reply_markup=get_cancel_button(),
        )
        return

    await _store_recurring_data(state, parsed)
    await state.set_state(CompanyRecurringExpenseStates.confirm)

    await _show_recurring_confirmation(message, await state.get_data())


@router.callback_query(F.data == "company:recurring:retry")
async def retry_recurring(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CompanyRecurringExpenseStates.waiting_input)
    await send_new_message(
        callback,
        "📝 Опишите ежемесячный расход ещё раз:",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.callback_query(F.data == "company:recurring:day")
async def ask_recurring_day(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CompanyRecurringExpenseStates.waiting_day_manual)
    await send_new_message(
        callback,
        "📅 Введите день месяца (1-31), когда оплачивается расход.",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.message(CompanyRecurringExpenseStates.waiting_day_manual)
async def set_recurring_day(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text.isdigit():
        await message.answer("❌ Введите число от 1 до 31.")
        return

    day = max(1, min(int(text), 31))
    await state.update_data(day_of_month=day)
    await state.set_state(CompanyRecurringExpenseStates.confirm)

    await _show_recurring_confirmation(message, await state.get_data())


@router.callback_query(F.data == "company:recurring:start")
async def ask_recurring_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(CompanyRecurringExpenseStates.waiting_start_manual)
    await send_new_message(
        callback,
        "📆 Укажите месяц начала в формате <code>ММ.ГГГГ</code>.",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.message(CompanyRecurringExpenseStates.waiting_start_manual)
async def set_recurring_start(message: Message, state: FSMContext):
    text = message.text.strip()
    try:
        parsed = datetime.strptime(text, "%m.%Y")
    except ValueError:
        await message.answer("❌ Неверный формат. Используйте <code>ММ.ГГГГ</code>.", parse_mode="HTML")
        return

    await state.update_data(start_month=parsed.month, start_year=parsed.year)
    await state.set_state(CompanyRecurringExpenseStates.confirm)

    await _show_recurring_confirmation(message, await state.get_data())


@router.callback_query(F.data == "company:recurring:save")
async def save_recurring_expense(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    await state.clear()

    expense = await create_company_recurring_expense(
        session=session,
        category=data["category"],
        amount=Decimal(data["amount"]),
        day_of_month=int(data["day_of_month"]),
        start_month=int(data["start_month"]),
        start_year=int(data["start_year"]),
        description=data.get("description"),
        added_by=user.id,
    )

    await create_company_expense_log(
        session=session,
        expense_type=RECURRING_LOG_TYPE,
        entity_id=expense.id,
        action="create",
        description=(
            f"Добавлен ежемесячный расход {expense.category}: {_format_rub(expense.amount)} "
            f"каждого {expense.day_of_month}-го"
        ),
        user_id=user.id,
    )

    await send_new_message(
        callback,
        "✅ Ежемесячный расход добавлен.",
        parse_mode="HTML",
    )
    await _send_recurring_overview(callback, session)
    await callback.answer("Сохранено")


@router.callback_query(F.data.startswith("company:recurring:category:"))
async def company_recurring_category(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    token = callback.data.split(":")[-1]
    try:
        category = await _decode_token(token, session=session, recurring=True)
    except ValueError:
        await callback.answer("❌ Не удалось определить категорию. Обновите список.", show_alert=True)
        return

    await _send_recurring_category(callback, session, category)
    await callback.answer()


@router.callback_query(F.data.startswith("company:recurring:view:"))
async def view_recurring_expense(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[3])
    token = parts[4]
    
    try:
        category = await _decode_token(token, session=session, recurring=True)
    except ValueError:
        await callback.answer("❌ Не удалось определить категорию. Обновите список.", show_alert=True)
        return

    # Получаем расход из БД
    expenses = await get_company_recurring_by_category(session, category)
    expense = next((e for e in expenses if e.id == expense_id), None)
    
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return

    # Формируем детальную карточку
    first_payment = _first_payment_date(expense.start_year, expense.start_month, expense.day_of_month)
    end_label = (
        f"до {expense.end_month:02d}.{expense.end_year}"
        if expense.end_month and expense.end_year
        else "бессрочно"
    )
    
    lines = [
        f"♻️ <b>Постоянный расход</b>",
        "",
        f"📂 Категория: {category}",
        f"💰 Ежемесячно: {format_currency(expense.amount)}",
        f"📅 День оплаты: {expense.day_of_month}-го числа",
        f"📆 Дата начала: {first_payment.strftime('%d.%m.%Y')}",
        f"⏱ Период: {end_label}",
        f"👤 Добавил: {_format_user_name(expense.user)}",
        f"📝 Описание: {expense.description or '—'}",
    ]

    keyboard = InlineKeyboardBuilder()
    keyboard.row(
        InlineKeyboardButton(
            text="🗑 Удалить",
            callback_data=f"company:recurring:delete:{expense_id}:{token}"
        )
    )
    keyboard.row(
        InlineKeyboardButton(
            text="🔙 К списку",
            callback_data=f"company:recurring:category:{token}"
        )
    )

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("company:recurring:delete:"))
async def delete_recurring(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[3])
    token = parts[4]
    try:
        category = await _decode_token(token, session=session, recurring=True)
    except ValueError:
        await callback.answer("❌ Не удалось определить категорию. Обновите список.", show_alert=True)
        return

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

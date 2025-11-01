"""
Обработчики для просмотра объектов
"""
import math
import hashlib
from collections import defaultdict
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Optional

from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, Message
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import (
    User,
    ObjectStatus,
    UserRole,
    PaymentSource,
    CompensationStatus,
    ExpenseType,
    ObjectLogType,
    FileType,
)
from database.crud import (
    get_objects_by_status,
    get_object_by_id,
    update_object_status,
    get_expenses_by_object,
    get_expense_by_id,
    update_compensation_status,
    get_file_by_id,
    get_advances_by_object,
    delete_expense,
    update_expense,
    get_advance_by_id,
    update_advance,
    delete_advance,
    create_object_log,
    get_object_logs,
    delete_object,
    get_files_by_object,
)
from bot.keyboards.objects_kb import (
    get_objects_list_keyboard,
    get_object_card_keyboard
)
from bot.keyboards.main_menu import get_confirm_keyboard, get_cancel_button
from bot.services.report_generator import generate_object_report
from bot.services.calculations import format_currency
from bot.states.expense_states import EditExpenseStates, EditAdvanceStates
from bot.states.object_document_states import ObjectDocumentStates
from bot.utils.messaging import delete_message, send_new_message, get_bot_username
from bot.services.file_service import FileService

router = Router()


EXPENSES_PAGE_SIZE = 10
ADVANCES_WORK_PAGE_SIZE = 10
LOGS_PAGE_SIZE = 10
UNSPECIFIED_WORK_TYPE_LABEL = "Без указания вида работ"
DEFAULT_WORK_TYPE_TOKEN = "default"
DEFAULT_EXPENSE_TYPE_TOKEN = "all"


EXPENSE_TYPE_ICONS = {
    ExpenseType.SUPPLIES: "🧰",
    ExpenseType.TRANSPORT: "🚚",
    ExpenseType.OVERHEAD: "🧾",
}


EXPENSE_TYPE_TOKENS = {
    ExpenseType.SUPPLIES: "supplies",
    ExpenseType.TRANSPORT: "transport",
    ExpenseType.OVERHEAD: "overhead",
}

EXPENSE_TOKEN_TO_TYPE = {value: key for key, value in EXPENSE_TYPE_TOKENS.items()}


DOCUMENT_TYPES_ORDER = ["estimate", "payroll"]

DOCUMENT_TYPE_INFO = {
    "estimate": {
        "icon": "📑",
        "label": "Сметы",
        "singular": "смету",
        "file_type": FileType.ESTIMATE,
    },
    "payroll": {
        "icon": "👷‍♂️",
        "label": "ФЗП",
        "singular": "ФЗП",
        "file_type": FileType.PAYROLL,
    },
}

FILE_TYPE_TO_DOCUMENT_TOKEN = {
    info["file_type"]: token for token, info in DOCUMENT_TYPE_INFO.items()
}


def _expense_type_label(expense_type: ExpenseType) -> str:
    mapping = {
        ExpenseType.SUPPLIES: "Расходники",
        ExpenseType.TRANSPORT: "Транспорт",
        ExpenseType.OVERHEAD: "Накладные",
    }
    return mapping.get(expense_type, expense_type.value)


def _expense_type_token(expense_type: ExpenseType) -> str:
    return EXPENSE_TYPE_TOKENS.get(expense_type, DEFAULT_EXPENSE_TYPE_TOKEN)


def _expense_type_from_token(token: str) -> ExpenseType | None:
    return EXPENSE_TOKEN_TO_TYPE.get(token)


def _document_info(token: str) -> dict | None:
    return DOCUMENT_TYPE_INFO.get(token)


def _document_file_type(token: str) -> FileType | None:
    info = _document_info(token)
    if not info:
        return None
    return info["file_type"]


def group_document_files(files) -> dict[str, list]:
    grouped: dict[str, list] = {token: [] for token in DOCUMENT_TYPES_ORDER}
    for file in files or []:
        token = FILE_TYPE_TO_DOCUMENT_TOKEN.get(file.file_type)
        if token:
            grouped.setdefault(token, []).append(file)
    return grouped


def document_counts(grouped: dict[str, list]) -> dict[str, int]:
    return {token: len(grouped.get(token, [])) for token in DOCUMENT_TYPES_ORDER}


def _format_file_size(size: Optional[int]) -> str:
    if not size or size <= 0:
        return "—"
    units = ["Б", "КБ", "МБ", "ГБ"]
    value = float(size)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            return f"{value:.1f} {unit}" if unit != "Б" else f"{int(value)} {unit}"
        value /= 1024
    return f"{value:.1f} ГБ"


def _get_expense_status(expense):
    if expense.payment_source == PaymentSource.PERSONAL:
        if expense.compensation_status == CompensationStatus.COMPENSATED:
            return "✅", "Компенсация выполнена"
        return "⏳", "К возмещению прорабу"
    return "💳", "Оплачено с карты ИП"


def _normalize_page(page: int, total_pages: int) -> int:
    if total_pages <= 0:
        return 1
    return max(1, min(page, total_pages))


def _build_navigation_buttons(prefix: str, object_id: int, page: int, total_pages: int) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"{prefix}:{object_id}:{page - 1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="➡️ Следующая", callback_data=f"{prefix}:{object_id}:{page + 1}"))
    return buttons


def _build_token_navigation(prefix: str, object_id: int, page: int, total_pages: int, token: str) -> list[InlineKeyboardButton]:
    buttons: list[InlineKeyboardButton] = []
    if page > 1:
        buttons.append(InlineKeyboardButton(text="⬅️ Предыдущая", callback_data=f"{prefix}:{object_id}:{page - 1}:{token}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton(text="➡️ Следующая", callback_data=f"{prefix}:{object_id}:{page + 1}:{token}"))
    return buttons


def _normalize_work_type(value: str | None) -> str:
    return (_display_work_type(value)).lower()


def _display_work_type(value: str | None) -> str:
    cleaned = (value or "").strip()
    return cleaned or UNSPECIFIED_WORK_TYPE_LABEL


def _make_work_type_token(value: str | None) -> str:
    normalized = _normalize_work_type(value)
    if not normalized:
        return DEFAULT_WORK_TYPE_TOKEN
    digest = hashlib.sha1(normalized.encode("utf-8")).hexdigest()
    return digest[:16]


def _is_default_work_type_token(token: str | None) -> bool:
    return not token or token == DEFAULT_WORK_TYPE_TOKEN


def _format_user_name(user: User | None) -> str:
    if not user:
        return "Система"
    return user.full_name or user.username or f"ID {user.telegram_id}"


async def _log_object_action(
    session: AsyncSession,
    object_id: int,
    action: ObjectLogType,
    description: str,
    user_id: Optional[int] = None,
) -> None:
    await create_object_log(
        session=session,
        object_id=object_id,
        action=action,
        description=description,
        user_id=user_id,
    )


def build_documents_menu_content(
    object_id: int,
    object_name: str,
    counts: dict[str, int],
) -> tuple[str, InlineKeyboardMarkup]:
    lines = [
        "📁 <b>Документы объекта</b>",
        f"🏗️ {object_name}",
        "",
        "Выберите категорию для просмотра или загрузите новый файл:",
        "",
    ]

    for token in DOCUMENT_TYPES_ORDER:
        info = DOCUMENT_TYPE_INFO[token]
        count = counts.get(token, 0)
        lines.append(f"{info['icon']} {info['label']}: {count} шт.")

    keyboard = InlineKeyboardBuilder()

    for token in DOCUMENT_TYPES_ORDER:
        info = DOCUMENT_TYPE_INFO[token]
        count = counts.get(token, 0)
        keyboard.row(
            InlineKeyboardButton(
                text=f"{info['icon']} {info['label']} ({count})",
                callback_data=f"object:documents:list:{object_id}:{token}"
            )
        )

    for token in DOCUMENT_TYPES_ORDER:
        info = DOCUMENT_TYPE_INFO[token]
        keyboard.row(
            InlineKeyboardButton(
                text=f"➕ {info['icon']} Добавить {info['singular']}",
                callback_data=f"object:documents:add:{object_id}:{token}"
            )
        )

    keyboard.row(
        InlineKeyboardButton(
            text="🔙 Назад к карточке",
            callback_data=f"object:view:{object_id}"
        )
    )

    return "\n".join(lines), keyboard.as_markup()


async def _send_expenses_overview(callback: CallbackQuery, session: AsyncSession, object_id: int) -> None:
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    expenses = await get_expenses_by_object(session, object_id)

    if not expenses:
        await send_new_message(
            callback,
            f"📋 <b>Расходы объекта</b>\n\n🏗️ {obj.name}\n\nПока нет добавленных расходов.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}")]]
            ),
        )
        return

    overall_total = sum((expense.amount for expense in expenses), Decimal(0))

    grouped: dict[ExpenseType, dict[str, object]] = {}
    for expense in expenses:
        bucket = grouped.setdefault(
            expense.type,
            {
                "total": Decimal(0),
                "count": 0,
                "personal_pending": 0,
                "personal_total": Decimal(0),
                "company_total": Decimal(0),
            },
        )
        bucket["total"] += expense.amount
        bucket["count"] += 1
        if expense.payment_source == PaymentSource.PERSONAL:
            bucket["personal_total"] += expense.amount
            if expense.compensation_status == CompensationStatus.PENDING:
                bucket["personal_pending"] += 1
        else:
            bucket["company_total"] += expense.amount

    type_rows = []
    for expense_type in [ExpenseType.SUPPLIES, ExpenseType.TRANSPORT, ExpenseType.OVERHEAD]:
        bucket = grouped.get(expense_type)
        if not bucket:
            continue
        label = EXPENSE_TYPE_TITLES.get(expense_type, expense_type.value)
        token = _expense_type_token(expense_type)
        total = bucket["total"]
        count = bucket["count"]
        pending = bucket["personal_pending"]
        personal_total = bucket["personal_total"]
        company_total = bucket["company_total"]

        summary_lines = [
            f"\n⚙️ <b>{label}</b>",
            f"   💰 Потрачено: {format_currency(total)}",
            f"   📄 Записей: {count}",
        ]
        if personal_total > 0 or pending:
            summary_lines.append(
                f"   👤 Оплачено прорабом: {format_currency(personal_total)}"
                + (f" • к компенсации: {pending}" if pending else "")
            )
        if company_total > 0:
            summary_lines.append(f"   💳 Оплачено фирмой: {format_currency(company_total)}")

        type_rows.append((label, token, summary_lines, total))

    lines = [
        "📋 <b>Расходы объекта</b>",
        f"🏗️ {obj.name}",
        f"Всего расходов: {len(expenses)}",
        f"Общая сумма: {format_currency(overall_total)}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>По категориям:</b>",
    ]

    keyboard = InlineKeyboardBuilder()
    for label, token, summary_lines, total in type_rows:
        lines.extend(summary_lines)
        keyboard.row(
            InlineKeyboardButton(
                text=f"{label} • {format_currency(total)}",
                callback_data=f"expense:type:{object_id}:1:{token}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}"))

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


async def _send_expenses_type_page(
    callback: CallbackQuery,
    session: AsyncSession,
    object_id: int,
    expense_token: str,
    page: int,
) -> None:
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    expense_type = _expense_type_from_token(expense_token)
    if expense_type is None:
        await _send_expenses_overview(callback, session, object_id)
        return

    expenses = await get_expenses_by_object(session, object_id)
    filtered = [expense for expense in expenses if expense.type == expense_type]

    if not filtered:
        await _send_expenses_overview(callback, session, object_id)
        return

    total = len(filtered)
    total_pages = math.ceil(total / EXPENSES_PAGE_SIZE)
    page = _normalize_page(page, total_pages)
    start = (page - 1) * EXPENSES_PAGE_SIZE
    current_items = filtered[start:start + EXPENSES_PAGE_SIZE]

    total_amount = sum((expense.amount for expense in filtered), Decimal(0))
    personal_total = sum((expense.amount for expense in filtered if expense.payment_source == PaymentSource.PERSONAL), Decimal(0))
    company_total = total_amount - personal_total
    pending_count = sum(
        1
        for expense in filtered
        if expense.payment_source == PaymentSource.PERSONAL and expense.compensation_status == CompensationStatus.PENDING
    )

    label = EXPENSE_TYPE_TITLES.get(expense_type, expense_type.value)

    lines = [
        f"📋 <b>{label}</b>",
        f"🏗️ {obj.name}",
        f"Страница {page}/{total_pages}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Всего расходов: {total}",
        f"Сумма расходов: {format_currency(total_amount)}",
        f"💳 Оплачено фирмой: {format_currency(company_total)}",
        f"👤 Оплачено прорабом: {format_currency(personal_total)}",
    ]
    if pending_count:
        lines.append(f"⏳ К компенсации: {pending_count}")

    lines.append("\n📄 Записи:")

    keyboard = InlineKeyboardBuilder()
    for idx, expense in enumerate(current_items, start=start + 1):
        status_icon, status_text = _get_expense_status(expense)
        date_str = expense.date.strftime("%d.%m.%Y")
        amount_str = format_currency(expense.amount)
        has_receipt = bool(expense.photo_url and expense.photo_url.startswith("file_"))
        receipt_note = " • 📎 Чек" if has_receipt else ""

        lines.append(
            f"\n{idx}. {status_icon} {date_str} • {amount_str}\n"
            f"   {expense.description[:80]}{receipt_note}\n"
            f"   <i>{status_text}</i>"
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f"{status_icon} {amount_str} • {date_str}",
                callback_data=f"expense:detail:{expense.id}:{object_id}:{page}:{expense_token}"
            )
        )

    nav_buttons = _build_token_navigation("expense:type", object_id, page, total_pages, expense_token)
    if nav_buttons:
        keyboard.row(*nav_buttons)

    keyboard.row(
        InlineKeyboardButton(
            text="🔙 К типам расходов",
            callback_data=f"object:view_expenses:{object_id}"
        )
    )

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


async def _send_advances_overview(callback: CallbackQuery, session: AsyncSession, object_id: int) -> None:
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    advances = await get_advances_by_object(session, object_id)

    if not advances:
        await send_new_message(
            callback,
            f"📄 <b>Авансы по объекту</b>\n\n🏗️ {obj.name}\n\nПока нет добавленных авансов.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}")]]
            ),
        )
        return

    overall_total = sum((advance.amount for advance in advances), Decimal(0))

    grouped: dict[str, dict[str, object]] = {}
    for advance in advances:
        normalized = _normalize_work_type(advance.work_type)
        display = _display_work_type(advance.work_type)
        token = _make_work_type_token(advance.work_type)
        bucket = grouped.setdefault(
            token,
            {
                "label": display,
                "total": Decimal(0),
                "count": 0,
                "min_date": None,
                "max_date": None,
                "token": token,
                "normalized": normalized,
            }
        )
        bucket["total"] += advance.amount
        bucket["count"] += 1
        if advance.date:
            if bucket["min_date"] is None or advance.date < bucket["min_date"]:
                bucket["min_date"] = advance.date
            if bucket["max_date"] is None or advance.date > bucket["max_date"]:
                bucket["max_date"] = advance.date

    groups = sorted(
        grouped.values(),
        key=lambda item: (item["label"].lower(), item["label"])
    )

    lines = [
        "📄 <b>Авансы по объекту</b>",
        f"🏗️ {obj.name}",
        f"Всего выдано: {format_currency(overall_total)}",
        f"Количество выплат: {len(advances)}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📊 <b>По видам работ:</b>",
    ]

    keyboard = InlineKeyboardBuilder()
    for idx, bucket in enumerate(groups, start=1):
        label = str(bucket["label"])
        total = bucket["total"]
        count = bucket["count"]
        min_date = bucket["min_date"]
        max_date = bucket["max_date"]

        if min_date and max_date:
            period = f"{min_date.strftime('%d.%m.%Y')} — {max_date.strftime('%d.%m.%Y')}"
        else:
            period = "—"

        lines.append(
            f"\n{idx}. ⚒ <b>{label}</b>\n"
            f"   💰 {format_currency(total)} • выплат: {count}\n"
            f"   📅 {period}"
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f"⚒ {label} • {format_currency(total)}",
                callback_data=f"advance:worktype:{object_id}:1:{bucket['token']}"
            )
        )

    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}"))

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )


async def _send_advances_worktype_page(
    callback: CallbackQuery,
    session: AsyncSession,
    object_id: int,
    work_type_token: str,
    page: int,
) -> None:
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    advances = await get_advances_by_object(session, object_id)

    grouped: dict[str, dict[str, object]] = {}
    for advance in advances:
        token = _make_work_type_token(advance.work_type)
        bucket = grouped.setdefault(
            token,
            {
                "label": _display_work_type(advance.work_type),
                "advances": [],
                "min_date": None,
                "max_date": None,
            }
        )
        bucket["advances"].append(advance)
        if advance.date:
            if bucket["min_date"] is None or advance.date < bucket["min_date"]:
                bucket["min_date"] = advance.date
            if bucket["max_date"] is None or advance.date > bucket["max_date"]:
                bucket["max_date"] = advance.date

    bucket = grouped.get(work_type_token)
    if not bucket:
        await _send_advances_overview(callback, session, object_id)
        return

    filtered = bucket["advances"]
    label = bucket["label"]
    total = len(filtered)
    total_pages = math.ceil(total / ADVANCES_WORK_PAGE_SIZE)
    page = _normalize_page(page, total_pages)
    start = (page - 1) * ADVANCES_WORK_PAGE_SIZE
    current_items = filtered[start:start + ADVANCES_WORK_PAGE_SIZE]

    total_amount = sum((advance.amount for advance in filtered), Decimal(0))
    min_date = bucket["min_date"]
    max_date = bucket["max_date"]

    worker_totals: defaultdict[str, Decimal] = defaultdict(Decimal)
    worker_counts: defaultdict[str, int] = defaultdict(int)
    for advance in filtered:
        name = (advance.worker_name or "Не указан").strip() or "Не указан"
        worker_totals[name] += advance.amount
        worker_counts[name] += 1

    worker_summary = sorted(
        worker_totals.items(),
        key=lambda item: item[1],
        reverse=True
    )

    if min_date and max_date:
        period = f"{min_date.strftime('%d.%m.%Y')} — {max_date.strftime('%d.%m.%Y')}"
    else:
        period = "—"

    lines = [
        f"⚒ <b>{label}</b>",
        f"🏗️ {obj.name}",
        f"Страница {page}/{total_pages}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Всего выплат: {total}",
        f"Выдано: {format_currency(total_amount)}",
        f"Период: {period}",
        "",
        "👥 <b>По исполнителям:</b>",
    ]

    if worker_summary:
        for name, amount in worker_summary:
            count = worker_counts[name]
            lines.append(f"   • {name}: {format_currency(amount)} ({count} выплат)")
    else:
        lines.append("   данных нет")

    lines.append("\n━━━━━━━━━━━━━━━━━━━━━━")
    lines.append("📄 Выплаты:")

    keyboard = InlineKeyboardBuilder()
    for idx, advance in enumerate(current_items, start=start + 1):
        date_str = advance.date.strftime("%d.%m.%Y")
        amount_str = format_currency(advance.amount)
        worker = advance.worker_name or "Не указан"

        lines.append(
            f"\n{idx}. 👤 {worker}\n"
            f"   💰 {amount_str}\n"
            f"   📅 {date_str}"
        )

        keyboard.row(
            InlineKeyboardButton(
                text=f"👤 {worker[:16]} • {amount_str}",
                callback_data=f"advance:detail:{advance.id}:{object_id}:{page}:{work_type_token}"
            )
        )

    nav_buttons = _build_token_navigation("advance:worktype", object_id, page, total_pages, work_type_token)
    if nav_buttons:
        keyboard.row(*nav_buttons)

    keyboard.row(
        InlineKeyboardButton(
            text="🔙 К видам работ",
            callback_data=f"object:view_advances:{object_id}"
        )
    )

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup()
    )


EXPENSE_TYPE_TITLES = {
    ExpenseType.SUPPLIES: "Расходники",
    ExpenseType.TRANSPORT: "Транспорт",
    ExpenseType.OVERHEAD: "Накладные расходы",
}


def _build_expense_detail_view(
    expense,
    user_role: UserRole,
    object_id: int,
    page: int,
    expense_token: str = DEFAULT_EXPENSE_TYPE_TOKEN,
):
    status_icon, status_text = _get_expense_status(expense)
    type_icon = EXPENSE_TYPE_ICONS.get(expense.type, "💰")
    type_title = EXPENSE_TYPE_TITLES.get(expense.type, "Расход")

    has_receipt = bool(expense.photo_url and expense.photo_url.startswith("file_"))
    can_compensate = (
        expense.payment_source == PaymentSource.PERSONAL
        and expense.compensation_status == CompensationStatus.PENDING
    )

    lines = [
        f"{status_icon} <b>Детали расхода</b>",
        "",
        f"Тип: {type_icon} {type_title}",
        f"💰 Сумма: {format_currency(expense.amount)}",
        f"📅 Дата: {expense.date.strftime('%d.%m.%Y')}",
        f"📝 Описание: {expense.description}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"Статус: <b>{status_text}</b>",
    ]

    if has_receipt:
        lines.append("📎 Чек прикреплён — см. ниже")

    keyboard = InlineKeyboardBuilder()

    if can_compensate and user_role == UserRole.ADMIN:
        keyboard.row(
            InlineKeyboardButton(
                text="✅ Отметить как компенсировано",
                callback_data=f"expense:compensate:{expense.id}:{object_id}:{page}:{expense_token}"
            )
        )

    if user_role == UserRole.ADMIN:
        keyboard.row(
            InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=f"expense:edit:{expense.id}:{object_id}:{page}:{expense_token}"
            )
        )
        keyboard.row(
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"expense:delete_request:{expense.id}:{object_id}:{page}:{expense_token}"
            )
        )

    if expense_token == DEFAULT_EXPENSE_TYPE_TOKEN:
        back_callback = f"object:view_expenses:{object_id}"
    else:
        back_callback = f"expense:type:{object_id}:{page}:{expense_token}"

    keyboard.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=back_callback
        )
    )

    return "\n".join(lines), keyboard.as_markup(), has_receipt


async def _send_expense_receipt(message: Message, session: AsyncSession, expense) -> None:
    receipt_id = None
    try:
        receipt_id = int(expense.photo_url.split("_", 1)[1]) if expense.photo_url else None
    except (ValueError, IndexError):
        receipt_id = None

    if not receipt_id:
        return

    receipt_file = await get_file_by_id(session, receipt_id)
    if not receipt_file or not receipt_file.file_data:
        await message.answer("⚠️ Чек был прикреплён, но не найден в базе данных")
        return

    size_kb = (receipt_file.file_size or 0) // 1024
    caption = (
        f"📎 <b>Чек по расходу</b>\n"
        f"📅 Загружен: {receipt_file.uploaded_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"📦 Размер: {size_kb} КБ"
    )

    photo = BufferedInputFile(
        receipt_file.file_data,
        filename=receipt_file.filename or "receipt.jpg"
    )
    await message.answer_photo(photo=photo, caption=caption, parse_mode="HTML")


def _build_advance_detail_view(
    advance,
    user_role: UserRole,
    object_id: int,
    page: int,
    work_type_token: str = "-",
) -> tuple[str, InlineKeyboardMarkup]:
    work_type_display = _display_work_type(advance.work_type)

    lines = [
        "💵 <b>Детали аванса</b>",
        "",
        f"👤 Рабочий: {advance.worker_name}",
        f"⚒ Вид работ: {work_type_display}",
        f"💰 Сумма: {format_currency(advance.amount)}",
        f"📅 Дата: {advance.date.strftime('%d.%m.%Y')}",
        "━━━━━━━━━━━━━━━━━━━━━━",
        f"ID пользователя: {advance.added_by}",
    ]

    keyboard = InlineKeyboardBuilder()

    if user_role == UserRole.ADMIN:
        keyboard.row(
            InlineKeyboardButton(
                text="✏️ Редактировать",
                callback_data=f"advance:edit:{advance.id}:{object_id}:{page}:{work_type_token}"
            )
        )
        keyboard.row(
            InlineKeyboardButton(
                text="🗑 Удалить",
                callback_data=f"advance:delete_request:{advance.id}:{object_id}:{page}:{work_type_token}"
            )
        )

    if work_type_token and work_type_token != "-":
        back_callback = f"advance:worktype:{object_id}:1:{work_type_token}"
    else:
        back_callback = f"object:view_advances:{object_id}"

    keyboard.row(
        InlineKeyboardButton(
            text="🔙 Назад",
            callback_data=back_callback
        )
    )

    return "\n".join(lines), keyboard.as_markup()


LOG_ACTION_TITLES = {
    ObjectLogType.EXPENSE_CREATED: "Добавлен расход",
    ObjectLogType.EXPENSE_UPDATED: "Изменён расход",
    ObjectLogType.EXPENSE_DELETED: "Удалён расход",
    ObjectLogType.EXPENSE_COMPENSATED: "Компенсация по расходу",
    ObjectLogType.ADVANCE_CREATED: "Добавлен аванс",
    ObjectLogType.ADVANCE_UPDATED: "Изменён аванс",
    ObjectLogType.ADVANCE_DELETED: "Удалён аванс",
    ObjectLogType.OBJECT_COMPLETED: "Объект завершён",
    ObjectLogType.OBJECT_RESTORED: "Объект возвращён в работу",
}


async def _send_logs_page(
    callback: CallbackQuery,
    session: AsyncSession,
    object_id: int,
    page: int,
) -> None:
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    logs, total = await get_object_logs(session, object_id, page, LOGS_PAGE_SIZE)

    if total == 0:
        await send_new_message(
            callback,
            f"📜 <b>Логи объекта</b>\n\n🏗️ {obj.name}\n\nПока нет записей.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}")]]
            ),
        )
        return

    total_pages = math.ceil(total / LOGS_PAGE_SIZE)
    page = _normalize_page(page, total_pages)

    lines = [
        "📜 <b>Логи объекта</b>",
        f"🏗️ {obj.name}",
        f"Страница {page}/{total_pages}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    for idx, log in enumerate(logs, start=1 + (page - 1) * LOGS_PAGE_SIZE):
        timestamp = log.created_at.strftime("%d.%m.%Y %H:%M")
        actor = _format_user_name(log.user)
        title = LOG_ACTION_TITLES.get(log.action, log.action.value)
        lines.append(
            f"\n{idx}. {timestamp}\n"
            f"👤 {actor}\n"
            f"🔖 {title}\n"
            f"📝 {log.description}"
        )

    keyboard = InlineKeyboardBuilder()
    nav_buttons = _build_navigation_buttons("object:view_logs", object_id, page, total_pages)
    if nav_buttons:
        keyboard.row(*nav_buttons)

    keyboard.row(InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}"))

    await send_new_message(
        callback,
        "\n".join(lines),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )


@router.callback_query(F.data.in_(["objects:active", "objects:completed"]))
async def show_objects_list(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    """
    Показать список объектов (текущих или завершенных)
    """
    await state.clear()
    
    # Определяем статус из callback_data
    status = ObjectStatus.ACTIVE if callback.data == "objects:active" else ObjectStatus.COMPLETED
    status_text = "Текущие" if status == ObjectStatus.ACTIVE else "Завершённые"
    
    # Получаем объекты из БД
    objects = await get_objects_by_status(session, status)
    
    if not objects:
        text = f"📋 <b>{status_text} объекты</b>\n\nНет объектов в этой категории."
    else:
        text = f"📋 <b>{status_text} объекты</b>\n\nВсего объектов: {len(objects)}\n\nВыберите объект для просмотра:"
    
    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=get_objects_list_keyboard(objects, status),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:view:"))
async def show_object_card(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """
    Показать карточку объекта
    """
    await state.clear()
    
    # Извлекаем ID объекта из callback_data
    object_id = int(callback.data.split(":")[2])
    
    # Получаем объект из БД с загруженными связями
    obj = await get_object_by_id(session, object_id, load_relations=True)
    
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return
    
    # Получаем файлы из объекта (relation подгружена при load_relations=True)
    files = getattr(obj, "files", []) or []
    
    # Генерируем отчет
    bot_username = None
    if callback.message:
        bot_username = await get_bot_username(callback.message.bot)

    report_text = generate_object_report(obj, files, bot_username)
    
    # Отправляем отчет с клавиатурой
    await send_new_message(
        callback,
        report_text,
        parse_mode="HTML",
        reply_markup=get_object_card_keyboard(object_id, obj.status, user.role),
    )
    await callback.answer()


@router.callback_query(F.data.regex(r"^object:documents:\d+$"))
async def show_object_documents(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer()
        return

    object_id = int(parts[2])
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    files = await get_files_by_object(session, object_id)
    grouped = group_document_files(files)
    counts = document_counts(grouped)

    text, markup = build_documents_menu_content(object_id, obj.name, counts)

    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:documents:list:"))
async def list_object_documents(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer()
        return

    object_id = int(parts[3])
    token = parts[4]
    info = _document_info(token)
    file_type = _document_file_type(token)

    if not info or not file_type:
        await callback.answer()
        return

    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    files = await get_files_by_object(session, object_id, file_type=file_type)

    lines = [
        f"{info['icon']} <b>{info['label']}</b>",
        f"🏗️ {obj.name}",
        "",
    ]

    keyboard = InlineKeyboardBuilder()

    if files:
        lines.append(f"Всего файлов: {len(files)}")
        lines.append("")

        for idx, file in enumerate(files, 1):
            uploaded = file.uploaded_at.strftime("%d.%m.%Y %H:%M") if file.uploaded_at else "—"
            filename = file.filename or f"{info['label']} #{file.id}"
            size = _format_file_size(file.file_size)
            lines.append(f"{idx}. {filename}")
            lines.append(f"   📅 {uploaded} • 📦 {size}")
            lines.append("")

            keyboard.row(
                InlineKeyboardButton(
                    text=f"{info['icon']} {filename}",
                    callback_data=f"object:documents:file:{file.id}:{object_id}:{token}"
                )
            )
    else:
        lines.append("Пока нет загруженных файлов.")
        lines.append("")

    keyboard.row(
        InlineKeyboardButton(
            text=f"➕ {info['icon']} Добавить {info['singular']}",
            callback_data=f"object:documents:add:{object_id}:{token}"
        )
    )
    keyboard.row(
        InlineKeyboardButton(
            text="🔙 Назад к документам",
            callback_data=f"object:documents:{object_id}"
        )
    )

    await send_new_message(
        callback,
        "\n".join(lines).strip(),
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:documents:add:"))
async def add_object_document(callback: CallbackQuery, session: AsyncSession, state: FSMContext):
    parts = callback.data.split(":")
    if len(parts) < 5:
        await callback.answer()
        return

    object_id = int(parts[3])
    token = parts[4]
    info = _document_info(token)
    file_type = _document_file_type(token)

    if not info or not file_type:
        await callback.answer()
        return

    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    await state.clear()
    await state.update_data(
        document_object_id=object_id,
        document_token=token,
        document_object_name=obj.name,
    )
    await state.set_state(ObjectDocumentStates.waiting_document)

    await send_new_message(
        callback,
        f"{info['icon']} <b>Загрузка файла</b>\n\n"
        f"Объект: <b>{obj.name}</b>\n"
        f"Категория: <b>{info['label']}</b>\n\n"
        "Отправьте PDF-файл в ответ на это сообщение.\n"
        "Можно прикрепить файл из проводника или переслать из другого чата.\n\n"
        "Если передумали, нажмите Отмена.",
        parse_mode="HTML",
        reply_markup=get_cancel_button(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:documents:file:"))
async def send_object_document(callback: CallbackQuery, session: AsyncSession):
    parts = callback.data.split(":")
    if len(parts) < 6:
        await callback.answer()
        return

    file_id = int(parts[3])
    object_id = int(parts[4])
    token = parts[5]
    info = _document_info(token)

    file = await get_file_by_id(session, file_id)
    if not file or file.object_id != object_id:
        await callback.answer("❌ Файл не найден", show_alert=True)
        return

    caption = f"{info['icon'] if info else '📄'} {file.filename or 'Документ'}"

    file_service = FileService(callback.message.bot)
    file_data = await file_service.get_file_data(session, file_id)

    try:
        if file_data:
            await callback.message.answer_document(
                document=BufferedInputFile(file_data, filename=file.filename or "document.pdf"),
                caption=caption,
            )
        else:
            await callback.message.answer_document(
                document=file.telegram_file_id,
                caption=caption,
            )
        await callback.answer("📄 Файл отправлен")
    except Exception as exc:
        await callback.answer("❌ Не удалось отправить файл", show_alert=True)
        print(f"Ошибка отправки файла {file_id}: {exc}")


@router.message(ObjectDocumentStates.waiting_document, F.document)
async def process_object_document(message: Message, user: User, session: AsyncSession, state: FSMContext):
    data = await state.get_data()
    object_id = data.get("document_object_id")
    token = data.get("document_token")
    object_name = data.get("document_object_name", "—")

    info = _document_info(token) if token else None
    file_type = _document_file_type(token) if token else None

    if not object_id or not info or not file_type:
        await state.clear()
        await message.answer("⚠️ Не удалось определить категорию документа. Попробуйте снова.")
        return

    document = message.document
    mime = (document.mime_type or "").lower() if document.mime_type else ""
    if "pdf" not in mime:
        await message.answer("⚠️ Поддерживаются только PDF-файлы. Загрузите документ в формате PDF или нажмите Отмена.")
        return

    file_service = FileService(message.bot)

    saved_file = await file_service.save_document(
        session=session,
        document=document,
        object_id=object_id,
        file_type=file_type,
    )

    if not saved_file:
        await message.answer("❌ Не удалось сохранить файл. Попробуйте снова")
        return

    await state.clear()

    size = _format_file_size(document.file_size)
    await message.answer(
        f"✅ <b>Файл загружен</b>\n\n"
        f"Объект: <b>{object_name}</b>\n"
        f"Категория: <b>{info['label']}</b>\n"
        f"Название: <b>{document.file_name or saved_file.filename or 'Без имени'}</b>\n"
        f"Размер: {size}",
        parse_mode="HTML",
    )

    files = await get_files_by_object(session, object_id)
    grouped = group_document_files(files)
    counts = document_counts(grouped)
    text, markup = build_documents_menu_content(object_id, object_name, counts)

    await message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.message(ObjectDocumentStates.waiting_document)
async def expect_pdf_document(message: Message):
    await message.answer("📄 Пожалуйста, отправьте PDF-файл или нажмите Отмена.")


@router.callback_query(F.data.startswith("object:complete_request:"))
async def confirm_complete_object(callback: CallbackQuery, user: User, session: AsyncSession):
    """
    Запрос подтверждения завершения объекта
    """
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    object_id = int(callback.data.split(":")[2])
    
    # Получаем объект
    obj = await get_object_by_id(session, object_id, load_relations=False)
    
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return
    
    await send_new_message(
        callback,
        f"⚠️ <b>Завершение объекта</b>\n\n"
        f"Вы уверены, что хотите завершить объект:\n"
        f"<b>{obj.name}</b>?\n\n"
        f"Объект будет перемещен в раздел 'Завершённые объекты'.",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(f"object:complete:confirm:{object_id}", "object:complete:cancel"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:complete:confirm:"))
async def complete_object(callback: CallbackQuery, user: User, session: AsyncSession):
    """
    Завершить объект
    """
    await callback.answer()  # Сразу отвечаем, чтобы убрать индикатор загрузки
    
    if user.role != UserRole.ADMIN:
        await send_new_message(callback, "❌ Недостаточно прав")
        return
    
    object_id = int(callback.data.split(":")[3])
    
    # Обновляем статус объекта
    obj = await update_object_status(session, object_id, ObjectStatus.COMPLETED)
    
    if not obj:
        await send_new_message(callback, "❌ Ошибка завершения объекта")
        return
    
    await send_new_message(
        callback,
        f"✅ <b>Объект завершен</b>\n\n"
        f"Объект <b>{obj.name}</b> успешно перемещен в раздел 'Завершённые объекты'.",
        parse_mode="HTML",
    )

    await _log_object_action(
        session=session,
        object_id=obj.id,
        action=ObjectLogType.OBJECT_COMPLETED,
        description=f"Объект '{obj.name}' завершён",
        user_id=user.id,
    )


@router.callback_query(F.data == "object:complete:cancel")
async def cancel_complete_object(callback: CallbackQuery):
    """
    Отменить завершение объекта
    """
    await send_new_message(
        callback,
        "❌ Завершение объекта отменено.",
    )
    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("object:restore_request:"))
async def confirm_restore_object(callback: CallbackQuery, user: User, session: AsyncSession):
    """
    Запрос подтверждения возврата объекта в текущие
    """
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    object_id = int(callback.data.split(":")[2])
    
    # Получаем объект
    obj = await get_object_by_id(session, object_id, load_relations=False)
    
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return
    
    await send_new_message(
        callback,
        f"⚠️ <b>Возврат объекта в текущие</b>\n\n"
        f"Вы уверены, что хотите вернуть объект:\n"
        f"<b>{obj.name}</b>\n\n"
        f"в раздел 'Текущие объекты'?",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(f"object:restore:confirm:{object_id}", "object:restore:cancel"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:restore:confirm:"))
async def restore_object(callback: CallbackQuery, user: User, session: AsyncSession):
    """
    Вернуть объект в текущие
    """
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    object_id = int(callback.data.split(":")[3])
    
    # Обновляем статус объекта
    obj = await update_object_status(session, object_id, ObjectStatus.ACTIVE)
    
    if not obj:
        await callback.answer("❌ Ошибка возврата объекта", show_alert=True)
        return
    
    await send_new_message(
        callback,
        f"✅ <b>Объект возвращен</b>\n\n"
        f"Объект <b>{obj.name}</b> успешно перемещен в раздел 'Текущие объекты'.",
        parse_mode="HTML",
    )
    await callback.answer("✅ Объект возвращен")

    await _log_object_action(
        session=session,
        object_id=obj.id,
        action=ObjectLogType.OBJECT_RESTORED,
        description=f"Объект '{obj.name}' возвращён в работу",
        user_id=user.id,
    )


@router.callback_query(F.data == "object:restore:cancel")
async def cancel_restore_object(callback: CallbackQuery):
    """
    Отменить возврат объекта
    """
    await send_new_message(
        callback,
        "❌ Возврат объекта отменён.",
    )
    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("object:view_advances:"))
async def view_advances_list(callback: CallbackQuery, user: User, session: AsyncSession):
    """Просмотр списка авансов по объекту"""

    parts = callback.data.split(":")
    object_id = int(parts[2])

    await _send_advances_overview(callback, session, object_id)
    await callback.answer()


@router.callback_query(F.data.startswith("object:view_expenses:"))
async def view_expenses_list(callback: CallbackQuery, user: User, session: AsyncSession):
    """Просмотр списка расходов объекта"""
    parts = callback.data.split(":")
    object_id = int(parts[2])
    expense_token = parts[3] if len(parts) > 3 else DEFAULT_EXPENSE_TYPE_TOKEN

    await _send_expenses_overview(callback, session, object_id)
    await callback.answer()


@router.callback_query(F.data.startswith("expense:type:"))
async def view_expenses_by_type(callback: CallbackQuery, user: User, session: AsyncSession):
    parts = callback.data.split(":")
    object_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 1
    expense_token = parts[4] if len(parts) > 4 else DEFAULT_EXPENSE_TYPE_TOKEN

    await _send_expenses_type_page(callback, session, object_id, expense_token, page)
    await callback.answer()


@router.callback_query(F.data.startswith("object:view_logs:"))
async def view_object_logs(callback: CallbackQuery, user: User, session: AsyncSession):
    """Просмотр логов объекта (только для админа)"""

    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    object_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 1

    await _send_logs_page(callback, session, object_id, page)
    await callback.answer()


@router.callback_query(F.data.startswith("advance:worktype:"))
async def view_advances_by_worktype(callback: CallbackQuery, user: User, session: AsyncSession):
    """Просмотр авансов по конкретному виду работ"""
    parts = callback.data.split(":")
    object_id = int(parts[2])
    page = int(parts[3]) if len(parts) > 3 else 1
    work_type_token = parts[4] if len(parts) > 4 else DEFAULT_WORK_TYPE_TOKEN

    await _send_advances_worktype_page(callback, session, object_id, work_type_token, page)
    await callback.answer()


@router.callback_query(F.data.startswith("expense:detail:"))
async def view_expense_detail(callback: CallbackQuery, user: User, session: AsyncSession):
    """Детальный просмотр расхода"""
    parts = callback.data.split(":")
    expense_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else None
    page = int(parts[4]) if len(parts) > 4 else 1
    expense_token = parts[5] if len(parts) > 5 else DEFAULT_EXPENSE_TYPE_TOKEN

    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return

    object_id = object_id or expense.object_id

    text, reply_markup, has_receipt = _build_expense_detail_view(expense, user.role, object_id, page, expense_token)

    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )

    if has_receipt:
        await _send_expense_receipt(callback.message, session, expense)

    await callback.answer()


@router.callback_query(F.data.startswith("expense:compensate:"))
async def compensate_expense(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else 0
    page = int(parts[4]) if len(parts) > 4 else 1
    expense_token = parts[5] if len(parts) > 5 else DEFAULT_EXPENSE_TYPE_TOKEN

    expense = await update_compensation_status(session, expense_id, CompensationStatus.COMPENSATED)

    if not expense:
        await callback.answer("❌ Ошибка обновления статуса", show_alert=True)
        return

    await _log_object_action(
        session=session,
        object_id=expense.object_id,
        action=ObjectLogType.EXPENSE_COMPENSATED,
        description=f"Расход #{expense.id} помечен как компенсированный",
        user_id=user.id,
    )

    text, reply_markup, has_receipt = _build_expense_detail_view(expense, user.role, object_id or expense.object_id, page, expense_token)

    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )

    if has_receipt:
        await _send_expense_receipt(callback.message, session, expense)

    await callback.answer("✅ Компенсация отмечена!", show_alert=True)


@router.callback_query(F.data.startswith("expense:edit:"))
async def start_expense_edit(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else None
    page = int(parts[4]) if len(parts) > 4 else 1
    expense_token = parts[5] if len(parts) > 5 else DEFAULT_EXPENSE_TYPE_TOKEN

    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return

    object_id = object_id or expense.object_id

    await state.set_state(EditExpenseStates.choose_field)
    await state.update_data(
        expense_id=expense_id,
        object_id=object_id,
        page=page,
        expense_token=expense_token,
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="💰 Сумма", callback_data="expense:edit_field:amount"))
    keyboard.row(InlineKeyboardButton(text="📅 Дата", callback_data="expense:edit_field:date"))
    keyboard.row(InlineKeyboardButton(text="📝 Описание", callback_data="expense:edit_field:description"))
    keyboard.row(InlineKeyboardButton(text="💳 Источник оплаты", callback_data="expense:edit_field:payment_source"))
    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="expense:edit_cancel"))

    await send_new_message(
        callback,
        "✏️ <b>Редактирование расхода</b>\n\nВыберите поле, которое нужно изменить:",
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()


@router.callback_query(EditExpenseStates.choose_field, F.data.startswith("expense:edit_field:"))
async def choose_expense_field(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    field = parts[2]

    await state.update_data(field=field)

    if field == "payment_source":
        await state.set_state(EditExpenseStates.choose_payment_source)
        keyboard = InlineKeyboardBuilder()
        keyboard.row(InlineKeyboardButton(text="💳 Оплачено фирмой", callback_data="expense:edit_payment_source:company"))
        keyboard.row(InlineKeyboardButton(text="💰 Оплачено прорабом", callback_data="expense:edit_payment_source:personal"))
        keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="expense:edit_cancel"))

        await send_new_message(
            callback,
            "Выберите новый источник оплаты:",
            reply_markup=keyboard.as_markup(),
        )
        await callback.answer()
        return
    
    await state.set_state(EditExpenseStates.waiting_value)

    prompts = {
        "amount": "Введите новую сумму (например: 12500)",
        "date": "Введите новую дату в формате <code>ДД.ММ.ГГГГ</code>",
        "description": "Введите новое описание (минимум 3 символа)",
    }

    await send_new_message(
        callback,
        prompts.get(field, "Введите новое значение"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="expense:edit_cancel")]
        ]),
    )
    await callback.answer()


@router.message(EditExpenseStates.waiting_value)
async def apply_expense_edit(message: Message, session: AsyncSession, state: FSMContext, user: User):
    data = await state.get_data()
    expense_id = data.get("expense_id")
    object_id = data.get("object_id")
    page = data.get("page", 1)
    field = data.get("field")
    expense_token = data.get("expense_token", DEFAULT_EXPENSE_TYPE_TOKEN)

    if user.role != UserRole.ADMIN or not expense_id or not field:
        await message.answer("❌ Недостаточно прав или некорректное состояние. Попробуйте снова.")
        await state.clear()
        return
    
    value = message.text.strip()
    updates = {}

    if field == "amount":
        try:
            updates["amount"] = Decimal(value.replace(" ", "").replace(",", "."))
        except (InvalidOperation, AttributeError):
            await message.answer("❌ Неверный формат суммы. Пример: 12500")
            return
    elif field == "date":
        parsed_date = None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if not parsed_date:
            await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
            return
        updates["date"] = parsed_date
    elif field == "description":
        if len(value) < 3:
            await message.answer("❌ Описание должно содержать минимум 3 символа")
            return
        updates["description"] = value
    else:
        await message.answer("⚠️ Это поле нельзя изменить таким образом.")
        await state.clear()
        return

    expense = await update_expense(session, expense_id, **updates)
    if not expense:
        await message.answer("❌ Не удалось обновить расход. Попробуйте снова.")
        await state.clear()
        return

    await state.clear()

    text, reply_markup, has_receipt = _build_expense_detail_view(expense, user.role, object_id, page, expense_token)
    await message.answer("✅ Изменения сохранены.")
    await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)

    if has_receipt:
        await _send_expense_receipt(message, session, expense)

    field_labels = {
        "amount": "Сумма",
        "date": "Дата",
        "description": "Описание",
    }

    if field == "amount":
        new_value = format_currency(expense.amount)
    elif field == "date":
        new_value = expense.date.strftime("%d.%m.%Y") if expense.date else "—"
    elif field == "description":
        new_value = expense.description
    else:
        new_value = value

    await _log_object_action(
        session=session,
        object_id=expense.object_id,
        action=ObjectLogType.EXPENSE_UPDATED,
        description=(
            f"Обновлен расход #{expense.id}: {field_labels.get(field, field)} → {new_value}"
        ),
        user_id=user.id,
    )


@router.callback_query(EditExpenseStates.choose_payment_source, F.data.startswith("expense:edit_payment_source:"))
async def apply_expense_payment_source(callback: CallbackQuery, session: AsyncSession, state: FSMContext, user: User):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    new_value = parts[2]

    data = await state.get_data()
    expense_id = data.get("expense_id")
    object_id = data.get("object_id")
    page = data.get("page", 1)
    expense_token = data.get("expense_token", DEFAULT_EXPENSE_TYPE_TOKEN)

    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await state.clear()
        await callback.answer("❌ Расход не найден", show_alert=True)
        return

    updates = {}
    if new_value == "company":
        updates["payment_source"] = PaymentSource.COMPANY
        updates["compensation_status"] = None
    else:
        compensation_status = expense.compensation_status or CompensationStatus.PENDING
        updates["payment_source"] = PaymentSource.PERSONAL
        updates["compensation_status"] = compensation_status

    expense = await update_expense(session, expense_id, **updates)
    await state.clear()

    await callback.answer("✅ Источник оплаты обновлён", show_alert=True)

    text, reply_markup, has_receipt = _build_expense_detail_view(expense, user.role, object_id, page, expense_token)
    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )

    if has_receipt:
        await _send_expense_receipt(callback.message, session, expense)

    source_text = "Оплачено фирмой" if updates["payment_source"] == PaymentSource.COMPANY else "Оплачено прорабом"

    await _log_object_action(
        session=session,
        object_id=expense.object_id,
        action=ObjectLogType.EXPENSE_UPDATED,
        description=f"Источнику оплаты расхода #{expense.id} присвоено значение: {source_text}",
        user_id=user.id,
    )


@router.callback_query(F.data == "expense:edit_cancel")
async def cancel_expense_edit(callback: CallbackQuery, session: AsyncSession, state: FSMContext, user: User):
    data = await state.get_data()
    await state.clear()

    expense_id = data.get("expense_id")
    object_id = data.get("object_id")
    page = data.get("page", 1)
    expense_token = data.get("expense_token", DEFAULT_EXPENSE_TYPE_TOKEN)

    if not expense_id:
        await callback.answer("❌ Отмена", show_alert=True)
        return

    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return

    object_id = object_id or expense.object_id

    text, reply_markup, has_receipt = _build_expense_detail_view(expense, user.role, object_id, page, expense_token)
    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )

    if has_receipt:
        await _send_expense_receipt(callback.message, session, expense)

    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("expense:delete_request:"))
async def request_expense_delete(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else None
    page = int(parts[4]) if len(parts) > 4 else 1
    expense_token = parts[5] if len(parts) > 5 else DEFAULT_EXPENSE_TYPE_TOKEN

    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return
    
    object_id = object_id or expense.object_id

    await send_new_message(
        callback,
        "⚠️ Вы уверены, что хотите удалить этот расход?",
        reply_markup=get_confirm_keyboard(
            f"expense:delete_confirm:{expense_id}:{object_id}:{page}:{expense_token}",
            f"expense:detail:{expense_id}:{object_id}:{page}:{expense_token}"
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("expense:delete_confirm:"))
async def confirm_expense_delete(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    expense_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else 0
    page = int(parts[4]) if len(parts) > 4 else 1
    expense_token = parts[5] if len(parts) > 5 else DEFAULT_EXPENSE_TYPE_TOKEN

    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return
    
    object_id = object_id or expense.object_id

    success = await delete_expense(session, expense_id)
    if not success:
        await callback.answer("❌ Не удалось удалить расход", show_alert=True)
        return

    await state.clear()
    await callback.answer("🗑 Расход удалён", show_alert=True)

    if expense_token == DEFAULT_EXPENSE_TYPE_TOKEN:
        await _send_expenses_overview(callback, session, object_id)
    else:
        await _send_expenses_type_page(callback, session, object_id, expense_token, page)

    await _log_object_action(
        session=session,
        object_id=expense.object_id,
        action=ObjectLogType.EXPENSE_DELETED,
        description=(
            f"Удален расход #{expense.id}: {_expense_type_label(expense.type)} — "
            f"{format_currency(expense.amount)}"
        ),
        user_id=user.id,
    )


@router.callback_query(F.data.startswith("advance:detail:"))
async def view_advance_detail(callback: CallbackQuery, user: User, session: AsyncSession):
    parts = callback.data.split(":")
    advance_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else None
    page = int(parts[4]) if len(parts) > 4 else 1
    work_type_token = parts[5] if len(parts) > 5 else DEFAULT_WORK_TYPE_TOKEN

    advance = await get_advance_by_id(session, advance_id)
    if not advance:
        await callback.answer("❌ Аванс не найден", show_alert=True)
        return

    object_id = object_id or advance.object_id

    text, reply_markup = _build_advance_detail_view(advance, user.role, object_id, page, work_type_token)
    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("advance:edit:"))
async def start_advance_edit(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    advance_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else None
    page = int(parts[4]) if len(parts) > 4 else 1
    work_type_token = parts[5] if len(parts) > 5 else DEFAULT_WORK_TYPE_TOKEN

    advance = await get_advance_by_id(session, advance_id)
    if not advance:
        await callback.answer("❌ Аванс не найден", show_alert=True)
        return

    object_id = object_id or advance.object_id

    await state.set_state(EditAdvanceStates.choose_field)
    await state.update_data(
        advance_id=advance_id,
        object_id=object_id,
        page=page,
        work_token=work_type_token,
    )

    keyboard = InlineKeyboardBuilder()
    keyboard.row(InlineKeyboardButton(text="👤 Рабочий", callback_data="advance:edit_field:worker_name"))
    keyboard.row(InlineKeyboardButton(text="⚒ Вид работ", callback_data="advance:edit_field:work_type"))
    keyboard.row(InlineKeyboardButton(text="💰 Сумма", callback_data="advance:edit_field:amount"))
    keyboard.row(InlineKeyboardButton(text="📅 Дата", callback_data="advance:edit_field:date"))
    keyboard.row(InlineKeyboardButton(text="❌ Отмена", callback_data="advance:edit_cancel"))

    await send_new_message(
        callback,
        "✏️ <b>Редактирование аванса</b>\n\nВыберите поле для изменения:",
        parse_mode="HTML",
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()


@router.callback_query(EditAdvanceStates.choose_field, F.data.startswith("advance:edit_field:"))
async def choose_advance_field(callback: CallbackQuery, state: FSMContext):
    field = callback.data.split(":")[2]
    await state.update_data(field=field)
    await state.set_state(EditAdvanceStates.waiting_value)

    prompts = {
        "worker_name": "Введите новое имя рабочего",
        "work_type": "Введите новый вид работ",
        "amount": "Введите новую сумму (например: 8000)",
        "date": "Введите новую дату в формате <code>ДД.ММ.ГГГГ</code>",
    }

    await send_new_message(
        callback,
        prompts.get(field, "Введите новое значение"),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="❌ Отмена", callback_data="advance:edit_cancel")]
        ]),
    )
    await callback.answer()


@router.message(EditAdvanceStates.waiting_value)
async def apply_advance_edit(message: Message, session: AsyncSession, state: FSMContext, user: User):
    if user.role != UserRole.ADMIN:
        await message.answer("❌ Недостаточно прав.")
        await state.clear()
        return

    data = await state.get_data()
    advance_id = data.get("advance_id")
    object_id = data.get("object_id")
    page = data.get("page", 1)
    field = data.get("field")
    work_token = data.get("work_token", DEFAULT_WORK_TYPE_TOKEN)

    if not advance_id or not field:
        await message.answer("⚠️ Некорректное состояние. Попробуйте снова.")
        await state.clear()
        return

    value = message.text.strip()
    updates = {}

    if field == "amount":
        try:
            updates["amount"] = Decimal(value.replace(" ", "").replace(",", "."))
        except (InvalidOperation, AttributeError):
            await message.answer("❌ Неверный формат суммы. Пример: 8000")
            return
    elif field == "date":
        parsed_date = None
        for fmt in ("%d.%m.%Y", "%Y-%m-%d"):
            try:
                parsed_date = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
        if not parsed_date:
            await message.answer("❌ Неверный формат даты. Используйте ДД.ММ.ГГГГ")
            return
        updates["date"] = parsed_date
    elif field in {"worker_name", "work_type"}:
        if len(value) < 2:
            await message.answer("❌ Значение должно содержать минимум 2 символа")
            return
        updates[field] = value
    else:
        await message.answer("⚠️ Это поле нельзя изменить")
        await state.clear()
        return

    advance = await update_advance(session, advance_id, **updates)
    if not advance:
        await message.answer("❌ Не удалось обновить аванс")
        await state.clear()
        return

    await state.clear()

    new_token = _make_work_type_token(advance.work_type)
    text, reply_markup = _build_advance_detail_view(advance, user.role, object_id, page, new_token)
    await message.answer("✅ Изменения сохранены.")
    await message.answer(text, parse_mode="HTML", reply_markup=reply_markup)

    field_labels = {
        "worker_name": "Рабочий",
        "work_type": "Вид работ",
        "amount": "Сумма",
        "date": "Дата",
    }

    if field == "amount":
        new_value = format_currency(advance.amount)
    elif field == "date":
        new_value = advance.date.strftime("%d.%m.%Y") if advance.date else "—"
    elif field == "worker_name":
        new_value = advance.worker_name
    elif field == "work_type":
        new_value = _display_work_type(advance.work_type)
    else:
        new_value = value

    await _log_object_action(
        session=session,
        object_id=advance.object_id,
        action=ObjectLogType.ADVANCE_UPDATED,
        description=(
            f"Обновлен аванс #{advance.id}: {field_labels.get(field, field)} → {new_value}"
        ),
        user_id=user.id,
    )


@router.callback_query(F.data == "advance:edit_cancel")
async def cancel_advance_edit(callback: CallbackQuery, session: AsyncSession, state: FSMContext, user: User):
    data = await state.get_data()
    await state.clear()

    advance_id = data.get("advance_id")
    object_id = data.get("object_id")
    page = data.get("page", 1)
    work_token = data.get("work_token", DEFAULT_WORK_TYPE_TOKEN)

    if not advance_id:
        await callback.answer("Отменено")
        return

    advance = await get_advance_by_id(session, advance_id)
    if not advance:
        await callback.answer("❌ Аванс не найден", show_alert=True)
        return

    object_id = object_id or advance.object_id

    text, reply_markup = _build_advance_detail_view(advance, user.role, object_id, page, work_token)
    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=reply_markup,
    )
    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("advance:delete_request:"))
async def request_advance_delete(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    parts = callback.data.split(":")
    advance_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else 0
    page = int(parts[4]) if len(parts) > 4 else 1
    work_token = parts[5] if len(parts) > 5 else DEFAULT_WORK_TYPE_TOKEN

    advance = await get_advance_by_id(session, advance_id)
    if not advance:
        await callback.answer("❌ Аванс не найден", show_alert=True)
        return

    object_id = object_id or advance.object_id

    await send_new_message(
        callback,
        "⚠️ Удалить этот аванс?",
        reply_markup=get_confirm_keyboard(
            f"advance:delete_confirm:{advance_id}:{object_id}:{page}:{work_token}",
            f"advance:detail:{advance_id}:{object_id}:{page}:{work_token}"
        ),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("advance:delete_confirm:"))
async def confirm_advance_delete(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    parts = callback.data.split(":")
    advance_id = int(parts[2])
    object_id = int(parts[3]) if len(parts) > 3 else 0
    page = int(parts[4]) if len(parts) > 4 else 1
    work_token = parts[5] if len(parts) > 5 else DEFAULT_WORK_TYPE_TOKEN

    advance = await get_advance_by_id(session, advance_id)
    if not advance:
        await callback.answer("❌ Аванс не найден", show_alert=True)
        return

    object_id = object_id or advance.object_id

    success = await delete_advance(session, advance_id)
    if not success:
        await callback.answer("❌ Не удалось удалить аванс", show_alert=True)
        return

    await state.clear()
    await callback.answer("🗑 Аванс удалён", show_alert=True)

    if _is_default_work_type_token(work_token):
        await _send_advances_overview(callback, session, object_id)
    else:
        await _send_advances_worktype_page(callback, session, object_id, work_token, page)

    await _log_object_action(
        session=session,
        object_id=advance.object_id,
        action=ObjectLogType.ADVANCE_DELETED,
        description=(
            f"Удален аванс #{advance.id}: {_display_work_type(advance.work_type)} — "
            f"{format_currency(advance.amount)} для {advance.worker_name}"
        ),
        user_id=user.id,
    )


@router.callback_query(F.data.startswith("object:delete_request:"))
async def request_delete_object(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    object_id = int(callback.data.split(":")[2])
    obj = await get_object_by_id(session, object_id, load_relations=False)

    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return

    await send_new_message(
        callback,
        "🗑 <b>Удаление объекта</b>\n\n"
        f"Вы собираетесь удалить объект <b>{obj.name}</b>.\n"
        "Будут удалены все связанные данные: расходы, авансы, файлы и логи.\n\n"
        "Действие необратимо. Подтвердите, если уверены.",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(f"object:delete_confirm:{object_id}", f"object:view:{object_id}"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:delete_confirm:"))
async def confirm_delete_object(callback: CallbackQuery, user: User, session: AsyncSession):
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return

    parts = callback.data.split(":")
    if len(parts) < 3:
        await callback.answer("❌ Некорректные данные", show_alert=True)
        return

    object_id = int(parts[2])

    success = await delete_object(session, object_id)
    if not success:
        await callback.answer("❌ Не удалось удалить объект", show_alert=True)
        return

    objects = await get_objects_by_status(session, ObjectStatus.COMPLETED)
    if objects:
        text = (
            "🗑 <b>Объект удалён</b>\n\n"
            "Запись удалена без возможности восстановления.\n\n"
            "Выберите другой объект из списка завершённых:"
        )
    else:
        text = "🗑 <b>Объект удалён</b>\n\nВ списке завершённых объектов больше нет записей."

    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=get_objects_list_keyboard(objects, ObjectStatus.COMPLETED),
    )
    await callback.answer("🗑 Удалено")


"""
Обработчики для создания нового объекта (FSM)
"""
import contextlib
import os
import tempfile
from decimal import Decimal, InvalidOperation
from datetime import datetime
from typing import Any, Dict, Optional

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, Voice
from aiogram.fsm.context import FSMContext
from aiogram.filters import Command
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole
from database.crud import create_object
from bot.states.add_object_states import AddObjectStates
from bot.keyboards.main_menu import get_cancel_button, get_skip_or_cancel, get_confirm_keyboard
from bot.services.pdf_parser import (
    extract_text_from_pdf,
    parse_pdf_to_object_data,
    parse_object_correction,
)
from bot.services.ai_parser import transcribe_voice
from bot.services.calculations import format_currency

router = Router()


NUMERIC_FIELDS = {
    "prepayment",
    "final_payment",
    "estimate_s3",
    "actual_s3_discount",
    "estimate_works",
    "estimate_supplies",
    "estimate_overhead",
    "estimate_transport",
}

DATE_FIELDS = {"start_date", "end_date"}

TEXT_FIELDS = {"name", "address", "foreman_name"}

OBJECT_FIELDS = list(TEXT_FIELDS | DATE_FIELDS | NUMERIC_FIELDS)

FIELD_TITLES = {
    "name": "Название",
    "address": "Адрес",
    "foreman_name": "Бригадир",
    "start_date": "Дата начала",
    "end_date": "Дата завершения",
    "prepayment": "Предоплата",
    "final_payment": "Окончательная оплата",
    "estimate_s3": "С3 по смете",
    "actual_s3_discount": "С3 со скидкой",
    "estimate_works": "Работы по смете",
    "estimate_supplies": "Расходники по смете",
    "estimate_overhead": "Накладные по смете",
    "estimate_transport": "Транспорт по смете",
}


def _ensure_all_fields(data: Dict[str, Any]) -> Dict[str, Any]:
    return {field: data.get(field) for field in OBJECT_FIELDS}


def _convert_field_value(field: str, value: Any) -> Optional[Any]:
    if field in NUMERIC_FIELDS:
        return _to_decimal(value)
    if field in DATE_FIELDS:
        return _parse_date_value(value)
    if field in TEXT_FIELDS:
        if value is None:
            return None
        value_str = str(value).strip()
        return value_str or None
    return None


def _to_decimal(value: Any) -> Optional[Decimal]:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        value_str = str(value).strip()
        if not value_str:
            return None
        value_str = value_str.replace(" ", "").replace(",", ".")
        return Decimal(value_str)
    except Exception:
        return None


def _parse_date_value(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    value_str = str(value).strip()
    if not value_str:
        return None
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(value_str, fmt)
        except ValueError:
            continue
    return None


def _normalize_object_data(raw: Dict[str, Any]) -> Dict[str, Any]:
    data: Dict[str, Any] = {}
    for field in TEXT_FIELDS:
        value = raw.get(field)
        data[field] = value.strip() if isinstance(value, str) else value

    for field in DATE_FIELDS:
        data[field] = _parse_date_value(raw.get(field))

    for field in NUMERIC_FIELDS:
        data[field] = _to_decimal(raw.get(field))

    return data


def _decimal_or_zero(value: Optional[Decimal]) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(0)


def _format_date(value: Optional[datetime]) -> str:
    return value.strftime("%d.%m.%Y") if isinstance(value, datetime) else "—"


def _format_currency_optional(value: Optional[Decimal]) -> str:
    if value is None:
        return "—"
    return format_currency(value)


def _build_summary_text(data: Dict[str, Any]) -> str:
    normalized = _normalize_object_data(_ensure_all_fields(data))

    prepayment = _decimal_or_zero(normalized.get("prepayment"))
    final_payment = _decimal_or_zero(normalized.get("final_payment"))
    estimate_s3 = _decimal_or_zero(normalized.get("estimate_s3"))
    actual_s3_discount = _decimal_or_zero(normalized.get("actual_s3_discount"))
    estimate_works = _decimal_or_zero(normalized.get("estimate_works"))
    estimate_supplies = _decimal_or_zero(normalized.get("estimate_supplies"))
    estimate_overhead = _decimal_or_zero(normalized.get("estimate_overhead"))
    estimate_transport = _decimal_or_zero(normalized.get("estimate_transport"))

    total_income = prepayment + final_payment
    s3_difference = estimate_s3 - actual_s3_discount

    summary = f"""
✅ <b>Проверка данных объекта</b>

🏗️ Объект: <b>{normalized.get('name') or '—'}</b>
📍 Адрес: {normalized.get('address') or '—'}
👷 Бригадир: {normalized.get('foreman_name') or '—'}
📅 Период: {_format_date(normalized.get('start_date'))} — {_format_date(normalized.get('end_date'))}

💸 <b>Финансы:</b>
Предоплата: {_format_currency_optional(normalized.get('prepayment'))}
Окончательная оплата: {_format_currency_optional(normalized.get('final_payment'))}
Всего поступлений: {format_currency(total_income)}

📊 <b>Смета:</b>
🧱 С3: {_format_currency_optional(normalized.get('estimate_s3'))}
🧱 С3 со скидкой: {_format_currency_optional(normalized.get('actual_s3_discount'))}
🔻 Разница С3: {format_currency(s3_difference)}
⚒ Работы: {_format_currency_optional(normalized.get('estimate_works'))}
🧰 Расходники: {_format_currency_optional(normalized.get('estimate_supplies'))}
💰 Накладные: {_format_currency_optional(normalized.get('estimate_overhead'))}
🚚 Транспорт: {_format_currency_optional(normalized.get('estimate_transport'))}

Все верно?
"""

    return summary.strip()


async def _prompt_manual_name(message: Message) -> None:
    text = (
        "📝 <b>Создание нового объекта</b>\n\n"
        "Шаг 1/12: Введите название объекта\n\n"
        "Например: <i>Вячеслав С поворотом</i>"
    )
    markup = get_cancel_button()
    with contextlib.suppress(Exception):
        await message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        return
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


def _format_field_output(field: str, value: Any) -> str:
    if field in NUMERIC_FIELDS:
        return _format_currency_optional(_to_decimal(value))
    if field in DATE_FIELDS:
        return _format_date(_parse_date_value(value))
    return str(value).strip() if value else "—"


async def _apply_correction(message: Message, text: str, state: FSMContext) -> None:
    current_data = await state.get_data()
    parsed = await parse_object_correction(text, _ensure_all_fields(current_data))

    if not parsed or "field" not in parsed:
        await message.answer("❌ Не понял, какое поле нужно изменить. Попробуйте сформулировать иначе.")
        return

    field = parsed.get("field")
    if field not in OBJECT_FIELDS:
        await message.answer("⚠️ Не удалось сопоставить поле. Укажите, что именно исправить (например, 'С3 со скидкой 175000').")
        return

    confidence = parsed.get("confidence")
    if isinstance(confidence, (int, float)) and confidence < 0.4:
        await message.answer("⚠️ Не уверен, что понял. Уточните формулировку, пожалуйста.")
        return

    new_value = _convert_field_value(field, parsed.get("value"))

    if field in NUMERIC_FIELDS and new_value is None:
        await message.answer("❌ Неверный формат суммы. Укажите число, например 'расходники 50000'.")
        return

    if field in DATE_FIELDS and new_value is None:
        await message.answer("❌ Не удалось распознать дату. Используйте формат ДД.ММ.ГГГГ или ГГГГ-ММ-ДД.")
        return

    old_value = current_data.get(field)
    await state.update_data(**{field: new_value})

    updated_data = await state.get_data()
    summary = _build_summary_text(updated_data)

    field_title = FIELD_TITLES.get(field, field)
    await message.answer(
        f"✅ {field_title}: { _format_field_output(field, old_value) } → {_format_field_output(field, new_value)}"
    )
    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard("object:save", "cancel")
    )


def _mode_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✍️ Заполнить вручную", callback_data="object:create:mode:manual")],
        [InlineKeyboardButton(text="📄 Импорт сметы (PDF)", callback_data="object:create:mode:pdf")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")]
    ])

@router.message(F.text == "➕ Добавить объект")
@router.message(Command("add_object"))
async def start_add_object(message: Message, user: User, state: FSMContext):
    """Начать процесс создания объекта"""
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для создания объектов.")
        return
    
    await state.clear()
    await state.set_state(AddObjectStates.choose_mode)

    await message.answer(
        "📝 <b>Создание нового объекта</b>\n\n"
        "Выберите способ заполнения:\n"
        "• Импорт сметы из PDF с автозаполнением\n"
        "• Ввести данные вручную",
        parse_mode="HTML",
        reply_markup=_mode_keyboard()
    )


@router.callback_query(AddObjectStates.choose_mode, F.data == "object:create:mode:manual")
async def select_manual_mode(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddObjectStates.enter_name)
    await _prompt_manual_name(callback.message)


@router.callback_query(AddObjectStates.choose_mode, F.data == "object:create:mode:pdf")
async def select_pdf_mode(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.set_state(AddObjectStates.waiting_pdf)

    instructions = (
        "📄 <b>Импорт сметы</b>\n\n"
        "Отправьте PDF-файл сметы одним сообщением.\n"
        "Бот извлечёт основные данные и заполнит карточку автоматически.\n\n"
        "После загрузки вы сможете скорректировать значения текстом или голосом."
    )

    with contextlib.suppress(Exception):
        await callback.message.edit_text(
            instructions,
            parse_mode="HTML",
            reply_markup=get_cancel_button()
        )
        return

    await callback.message.answer(
        instructions,
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.choose_mode)
async def choose_mode_message(message: Message):
    await message.answer(
        "Выберите способ создания объекта через кнопки ниже.",
        reply_markup=_mode_keyboard()
    )


@router.message(AddObjectStates.waiting_pdf, F.document)
async def handle_pdf_upload(message: Message, state: FSMContext):
    document = message.document

    if document.mime_type != "application/pdf" and not (document.file_name or "").lower().endswith(".pdf"):
        await message.answer(
            "❌ Пожалуйста отправьте файл в формате PDF.",
            reply_markup=get_cancel_button()
        )
        return

    temp_path = None
    try:
        file = await message.bot.get_file(document.file_id)
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_path = temp_file.name
        await message.bot.download_file(file.file_path, temp_path)

        extracted_text = await extract_text_from_pdf(temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    if not extracted_text.strip():
        await message.answer(
            "❌ Не удалось извлечь текст из файла. Проверьте PDF или попробуйте другой файл.",
            reply_markup=get_cancel_button()
        )
        return

    parsed = await parse_pdf_to_object_data(extracted_text)

    if not parsed:
        await message.answer(
            "⚠️ Не удалось автоматически распознать смету. Попробуйте другой файл или заполните данные вручную.",
            reply_markup=get_cancel_button()
        )
        return

    normalized = _ensure_all_fields(_normalize_object_data(parsed))
    await state.update_data(**normalized, import_mode=True)
    await state.set_state(AddObjectStates.confirm_object)

    data = await state.get_data()
    summary = _build_summary_text(data)

    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard("object:save", "cancel")
    )

    await message.answer(
        "Если нужно что-то исправить, просто напишите сообщение (например: «адрес Зеленоград») или отправьте голосовое.",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.waiting_pdf)
async def handle_non_pdf(message: Message):
    await message.answer(
        "📄 Отправьте PDF-файл сметы или нажмите Отмена.",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_name)
async def process_name(message: Message, state: FSMContext):
    """Обработка названия объекта"""
    
    await state.update_data(name=message.text.strip())
    await state.set_state(AddObjectStates.enter_address)
    
    await message.answer(
        "📝 Шаг 2/12: Введите адрес объекта\n\n"
        "Или нажмите 'Пропустить', если адрес неизвестен",
        reply_markup=get_skip_or_cancel()
    )


@router.message(AddObjectStates.enter_address)
async def process_address(message: Message, state: FSMContext):
    """Обработка адреса"""
    
    await state.update_data(address=message.text.strip())
    await state.set_state(AddObjectStates.enter_foreman)
    
    await message.answer(
        "📝 Шаг 3/12: Введите имя бригадира/ответственного\n\n"
        "Или нажмите 'Пропустить'",
        reply_markup=get_skip_or_cancel()
    )


@router.message(AddObjectStates.enter_foreman)
async def process_foreman(message: Message, state: FSMContext):
    """Обработка имени бригадира"""
    
    await state.update_data(foreman_name=message.text.strip())
    await state.set_state(AddObjectStates.enter_dates)
    
    await message.answer(
        "📝 Шаг 4/12: Введите даты работ\n\n"
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
        "💸 Шаг 5/12: Введите сумму предоплаты (в рублях)\n\n"
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
        "💸 Шаг 6/12: Введите сумму окончательной оплаты (в рублях)\n\n"
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
        "🧱 Шаг 7/12: Введите сумму С3 по смете (в рублях)\n\n"
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
    await state.set_state(AddObjectStates.enter_actual_s3_discount)
    
    await message.answer(
        "🧱 Шаг 8/12: Введите сумму С3 со скидкой (фактическая стоимость) в рублях\n\n"
        "Например: <code>180000</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_button()
    )


@router.message(AddObjectStates.enter_actual_s3_discount)
async def process_actual_s3_discount(message: Message, state: FSMContext):
    """Обработка фактической стоимости С3 со скидкой"""

    try:
        actual_s3_discount = Decimal(message.text.strip().replace(" ", "").replace(",", "."))
        if actual_s3_discount < 0:
            raise ValueError
    except:
        await message.answer(
            "❌ Неверная сумма. Введите число:"
        )
        return

    await state.update_data(actual_s3_discount=actual_s3_discount)
    await state.set_state(AddObjectStates.enter_estimate_works)

    await message.answer(
        "⚒ Шаг 9/12: Введите сумму работ по смете (в рублях)\n\n"
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
        "🧰 Шаг 10/12: Введите сумму расходников по смете (в рублях)\n\n"
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
        "💰 Шаг 11/12: Введите сумму накладных расходов по смете (в рублях)\n\n"
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
        "🚚 Шаг 12/12: Введите сумму транспортных расходов по смете (в рублях)\n\n"
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
    
    data = await state.get_data()
    summary = _build_summary_text(data)

    await message.answer(
        summary,
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard("object:save", "cancel")
    )


@router.callback_query(F.data == "object:save", AddObjectStates.confirm_object)
async def save_object(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Сохранить объект в базу данных"""
    
    data = await state.get_data()
    normalized = _normalize_object_data(_ensure_all_fields(data))

    payload = normalized.copy()
    for field in NUMERIC_FIELDS:
        payload[field] = payload[field] if payload[field] is not None else Decimal(0)

    if not payload.get("name"):
        await callback.answer("❌ Укажите название объекта перед сохранением.", show_alert=True)
        return
    
    # Создаем объект в БД
    try:
        obj = await create_object(
            session=session,
            name=payload['name'],
            created_by=user.id,
            address=payload.get('address'),
            foreman_name=payload.get('foreman_name'),
            start_date=payload.get('start_date'),
            end_date=payload.get('end_date'),
            prepayment=payload['prepayment'],
            final_payment=payload['final_payment'],
            estimate_s3=payload['estimate_s3'],
            estimate_works=payload['estimate_works'],
            estimate_supplies=payload['estimate_supplies'],
            estimate_overhead=payload['estimate_overhead'],
            estimate_transport=payload['estimate_transport'],
            actual_s3_discount=payload['actual_s3_discount']
        )
        
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


@router.message(AddObjectStates.confirm_object, F.text)
async def handle_text_correction(message: Message, state: FSMContext):
    text = message.text.strip()
    if not text:
        await message.answer("⚠️ Сообщение пустое. Опишите, что нужно изменить.")
        return

    await _apply_correction(message, text, state)


@router.message(AddObjectStates.confirm_object, F.voice)
async def handle_voice_correction(message: Message, state: FSMContext):
    voice: Voice = message.voice
    file = await message.bot.get_file(voice.file_id)
    temp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_path = temp_file.name
        await message.bot.download_file(file.file_path, temp_path)
        text = await transcribe_voice(temp_path)
    finally:
        if temp_path and os.path.exists(temp_path):
            os.unlink(temp_path)

    if not text:
        await message.answer("❌ Не удалось распознать голос. Попробуйте произнести ещё раз.")
        return

    await _apply_correction(message, text, state)


@router.callback_query(F.data == "skip")
async def skip_step(callback: CallbackQuery, state: FSMContext):
    """Пропустить необязательный шаг"""
    
    current_state = await state.get_state()
    
    if current_state == AddObjectStates.enter_address.state:
        await state.update_data(address=None)
        await state.set_state(AddObjectStates.enter_foreman)
        await callback.message.edit_text(
            "📝 Шаг 3/12: Введите имя бригадира/ответственного\n\n"
            "Или нажмите 'Пропустить'",
            reply_markup=get_skip_or_cancel()
        )
    
    elif current_state == AddObjectStates.enter_foreman.state:
        await state.update_data(foreman_name=None)
        await state.set_state(AddObjectStates.enter_dates)
        await callback.message.edit_text(
            "📝 Шаг 4/12: Введите даты работ\n\n"
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
            "💸 Шаг 5/12: Введите сумму предоплаты (в рублях)\n\n"
            "Например: <code>150000</code>",
            parse_mode="HTML",
            reply_markup=get_cancel_button()
        )
    
    await callback.answer("Пропущено")


@router.callback_query(F.data == "cancel")
async def cancel_creation(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    with contextlib.suppress(Exception):
        await callback.message.edit_text("❌ Создание объекта отменено.")
    await callback.answer("Отменено")


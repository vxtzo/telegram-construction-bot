"""
Обработчики для просмотра объектов
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, ObjectStatus, UserRole, PaymentSource, CompensationStatus, ExpenseType
from database.crud import (
    get_objects_by_status,
    get_object_by_id,
    update_object_status,
    get_expenses_by_object,
    get_expense_by_id,
    update_compensation_status,
    get_file_by_id
)
from bot.keyboards.objects_kb import (
    get_objects_list_keyboard,
    get_object_card_keyboard
)
from bot.keyboards.main_menu import get_confirm_keyboard
from bot.services.report_generator import generate_object_report

router = Router()


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
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_objects_list_keyboard(objects, status)
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
    report_text = generate_object_report(obj, files)
    
    # Отправляем отчет с клавиатурой
    await callback.message.edit_text(
        report_text,
        parse_mode="HTML",
        reply_markup=get_object_card_keyboard(object_id, obj.status, user.role)
    )
    await callback.answer()


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
    
    await callback.message.edit_text(
        f"⚠️ <b>Завершение объекта</b>\n\n"
        f"Вы уверены, что хотите завершить объект:\n"
        f"<b>{obj.name}</b>?\n\n"
        f"Объект будет перемещен в раздел 'Завершённые объекты'.",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(f"object:complete:confirm:{object_id}", "object:complete:cancel")
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:complete:confirm:"))
async def complete_object(callback: CallbackQuery, user: User, session: AsyncSession):
    """
    Завершить объект
    """
    await callback.answer()  # Сразу отвечаем, чтобы убрать индикатор загрузки
    
    if user.role != UserRole.ADMIN:
        await callback.message.answer("❌ Недостаточно прав")
        return
    
    object_id = int(callback.data.split(":")[3])
    
    # Обновляем статус объекта
    obj = await update_object_status(session, object_id, ObjectStatus.COMPLETED)
    
    if not obj:
        await callback.message.answer("❌ Ошибка завершения объекта")
        return
    
    await callback.message.edit_text(
        f"✅ <b>Объект завершен</b>\n\n"
        f"Объект <b>{obj.name}</b> успешно перемещен в раздел 'Завершённые объекты'.",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "object:complete:cancel")
async def cancel_complete_object(callback: CallbackQuery):
    """
    Отменить завершение объекта
    """
    await callback.message.edit_text(
        "❌ Завершение объекта отменено."
    )
    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("object:restore:"))
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
    
    await callback.message.edit_text(
        f"⚠️ <b>Возврат объекта в текущие</b>\n\n"
        f"Вы уверены, что хотите вернуть объект:\n"
        f"<b>{obj.name}</b>\n\n"
        f"в раздел 'Текущие объекты'?",
        parse_mode="HTML",
        reply_markup=get_confirm_keyboard(f"object:restore:confirm:{object_id}", "object:restore:cancel")
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
    
    await callback.message.edit_text(
        f"✅ <b>Объект возвращен</b>\n\n"
        f"Объект <b>{obj.name}</b> успешно перемещен в раздел 'Текущие объекты'.",
        parse_mode="HTML"
    )
    await callback.answer("✅ Объект возвращен")


@router.callback_query(F.data == "object:restore:cancel")
async def cancel_restore_object(callback: CallbackQuery):
    """
    Отменить возврат объекта
    """
    await callback.message.edit_text(
        "❌ Возврат объекта отменён."
    )
    await callback.answer("Отменено")


@router.callback_query(F.data.startswith("object:view_expenses:"))
async def view_expenses_list(callback: CallbackQuery, user: User, session: AsyncSession):
    """Просмотр списка расходов объекта"""
    
    object_id = int(callback.data.split(":")[2])
    
    # Получаем объект
    obj = await get_object_by_id(session, object_id, load_relations=False)
    if not obj:
        await callback.answer("❌ Объект не найден", show_alert=True)
        return
    
    # Получаем расходы
    expenses = await get_expenses_by_object(session, object_id)
    
    if not expenses:
        await callback.message.edit_text(
            f"📋 <b>Расходы объекта</b>\n\n"
            f"🏗️ {obj.name}\n\n"
            f"Пока нет добавленных расходов.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}")]
            ])
        )
        await callback.answer()
        return
    
    # Формируем список расходов с иконками статусов
    from bot.services.calculations import format_currency
    
    text = f"📋 <b>Расходы объекта</b>\n\n"
    text += f"🏗️ {obj.name}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Группируем по типу
    supplies = [e for e in expenses if e.type == ExpenseType.SUPPLIES]
    transport = [e for e in expenses if e.type == ExpenseType.TRANSPORT]
    overhead = [e for e in expenses if e.type == ExpenseType.OVERHEAD]
    
    expense_groups = [
        ("🧰 Расходники", supplies),
        ("🚚 Транспорт", transport),
        ("🧾 Накладные", overhead)
    ]
    
    builder = InlineKeyboardButton
    buttons = []
    
    for emoji_title, exp_list in expense_groups:
        if exp_list:
            text += f"\n{emoji_title}:\n"
            for exp in exp_list[:10]:  # Показываем до 10 расходов каждого типа
                # Иконка статуса оплаты
                if exp.payment_source == PaymentSource.PERSONAL:
                    if exp.compensation_status == CompensationStatus.PENDING:
                        status_icon = "⏳"  # К компенсации
                        status_text = "К возмещению прорабу"
                    else:
                        status_icon = "✅"  # Компенсировано
                        status_text = "Компенсация выполнена"
                else:
                    status_icon = "💳"  # Оплачено фирмой
                    status_text = "Оплачено с карты ИП"

                has_receipt = bool(exp.photo_url and exp.photo_url.startswith("file_"))
                receipt_note = " • 📎 Чек прикреплен" if has_receipt else ""
                button_receipt_icon = " 📎" if has_receipt else ""

                date_str = exp.date.strftime("%d.%m")
                text += f"\n{status_icon} {date_str} • {format_currency(exp.amount)}\n"
                text += f"   {exp.description[:50]}\n"
                text += f"   <i>{status_text}{receipt_note}</i>\n"

                # Добавляем кнопку для детального просмотра
                buttons.append([
                    InlineKeyboardButton(
                        text=f"{status_icon}{button_receipt_icon} {date_str} - {format_currency(exp.amount)}",
                        callback_data=f"expense:detail:{exp.id}"
                    )
                ])
    
    text += f"\n━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"Всего расходов: {len(expenses)}"
    
    # Добавляем кнопку назад
    buttons.append([InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}")])
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons[:15])  # Лимит кнопок
    )
    await callback.answer()


@router.callback_query(F.data.startswith("expense:detail:"))
async def view_expense_detail(callback: CallbackQuery, user: User, session: AsyncSession):
    """Детальный просмотр расхода"""
    
    expense_id = int(callback.data.split(":")[2])
    
    # Получаем расход
    expense = await get_expense_by_id(session, expense_id)
    if not expense:
        await callback.answer("❌ Расход не найден", show_alert=True)
        return
    
    # Форматируем детальную информацию
    from bot.services.calculations import format_currency
    
    type_names = {
        ExpenseType.SUPPLIES: "🧰 Расходники",
        ExpenseType.TRANSPORT: "🚚 Транспортные расходы",
        ExpenseType.OVERHEAD: "🧾 Накладные расходы"
    }
    
    # Иконка и статус
    if expense.payment_source == PaymentSource.PERSONAL:
        if expense.compensation_status == CompensationStatus.PENDING:
            status_icon = "⏳"
            status_text = "К возмещению прорабу"
            can_compensate = user.role == UserRole.ADMIN
        else:
            status_icon = "✅"
            status_text = "Компенсация выполнена!"
            can_compensate = False
    else:
        status_icon = "💳"
        status_text = "Оплачено с карты ИП"
        can_compensate = False
    
    has_receipt = bool(expense.photo_url and expense.photo_url.startswith("file_"))

    text = f"{status_icon} <b>Детали расхода</b>\n\n"
    text += f"Тип: {type_names.get(expense.type, expense.type)}\n"
    text += f"💰 Сумма: {format_currency(expense.amount)}\n"
    text += f"📅 Дата: {expense.date.strftime('%d.%m.%Y')}\n"
    text += f"📝 Описание: {expense.description}\n"
    text += f"━━━━━━━━━━━━━━━━━━━━━━\n"
    text += f"Статус: <b>{status_text}</b>\n"
    if has_receipt:
        text += "📎 Чек прикреплён — см. сообщение ниже\n"
 
    # Кнопки
    buttons = []
 
    # Если к компенсации и пользователь админ - добавляем кнопку компенсации
    if can_compensate:
        buttons.append([
            InlineKeyboardButton(
                text="✅ Отметить как компенсировано",
                callback_data=f"expense:compensate:{expense_id}"
            )
        ])
 
    # Кнопка назад
    buttons.append([
        InlineKeyboardButton(
            text="🔙 К списку расходов",
            callback_data=f"object:view_expenses:{expense.object_id}"
        )
    ])
 
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons)
    )

    if has_receipt:
        receipt_id = None
        try:
            receipt_id = int(expense.photo_url.split("_", 1)[1])
        except (ValueError, IndexError):
            receipt_id = None

        if receipt_id:
            receipt_file = await get_file_by_id(session, receipt_id)
            if receipt_file and receipt_file.file_data:
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
                await callback.message.answer_photo(
                    photo=photo,
                    caption=caption,
                    parse_mode="HTML"
                )
            else:
                await callback.message.answer("⚠️ Чек был прикреплён, но не найден в базе данных")

    await callback.answer()


@router.callback_query(F.data.startswith("expense:compensate:"))
async def compensate_expense(callback: CallbackQuery, user: User, session: AsyncSession):
    """Отметить расход как компенсированный"""
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    expense_id = int(callback.data.split(":")[2])
    
    # Обновляем статус
    expense = await update_compensation_status(session, expense_id, CompensationStatus.COMPENSATED)
    
    if not expense:
        await callback.answer("❌ Ошибка обновления статуса", show_alert=True)
        return
    
    await callback.answer("✅ Компенсация отмечена!", show_alert=True)
    
    # Перенаправляем на детальный просмотр
    await view_expense_detail(callback, user, session)


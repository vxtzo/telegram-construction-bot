"""
Обработчики для просмотра объектов
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, ObjectStatus, UserRole
from database.crud import (
    get_objects_by_status,
    get_object_by_id,
    update_object_status,
    get_files_by_object
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
    
    # Получаем файлы
    files = await get_files_by_object(session, object_id)
    
    # Генерируем отчет
    report_text = generate_object_report(obj, files)
    
    # Отправляем отчет с клавиатурой
    await callback.message.edit_text(
        report_text,
        parse_mode="HTML",
        reply_markup=get_object_card_keyboard(object_id, obj.status, user.role)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("object:complete:"))
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


@router.callback_query(F.data.startswith("object:view_receipts:"))
async def view_receipts(callback: CallbackQuery, session: AsyncSession):
    """
    Показать чеки и накладные объекта
    """
    await callback.answer()
    
    object_id = int(callback.data.split(":")[2])
    
    # Получаем объект
    obj = await get_object_by_id(session, object_id, load_relations=False)
    
    if not obj:
        await callback.message.answer("❌ Объект не найден")
        return
    
    # Получаем все файлы объекта
    from database.models import FileType
    files = await get_files_by_object(session, object_id)
    
    # Фильтруем чеки
    receipts = [f for f in files if f.file_type == FileType.RECEIPT]
    
    if not receipts:
        await callback.message.edit_text(
            f"📸 <b>Чеки объекта: {obj.name}</b>\n\n"
            f"❌ Нет загруженных чеков\n\n"
            f"Чеки добавляются автоматически при добавлении расходов с фото.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}")]
            ])
        )
        return
    
    # Формируем сообщение со списком чеков
    text = f"📸 <b>Чеки объекта: {obj.name}</b>\n\n"
    text += f"Всего чеков: {len(receipts)}\n\n"
    
    for i, receipt in enumerate(receipts[:10], 1):  # Показываем первые 10
        date_str = receipt.uploaded_at.strftime("%d.%m.%Y %H:%M")
        size_kb = (receipt.file_size or 0) // 1024
        text += f"{i}. {receipt.filename or 'Чек'} ({size_kb} КБ)\n"
        text += f"   📅 {date_str}\n\n"
    
    if len(receipts) > 10:
        text += f"... и ещё {len(receipts) - 10} чеков\n\n"
    
    text += "💡 Чтобы посмотреть чек, нажмите на кнопку ниже:"
    
    # Создаём клавиатуру с кнопками чеков
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    
    # Добавляем кнопки для первых 5 чеков
    for i, receipt in enumerate(receipts[:5], 1):
        builder.row(
            InlineKeyboardButton(
                text=f"📷 Чек #{i}",
                callback_data=f"receipt:view:{receipt.id}"
            )
        )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data=f"object:view:{object_id}")
    )
    
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.startswith("receipt:view:"))
async def view_single_receipt(callback: CallbackQuery, session: AsyncSession):
    """
    Показать конкретный чек
    """
    await callback.answer()
    
    file_id = int(callback.data.split(":")[2])
    
    # Получаем файл из БД
    from database.crud import get_file_by_id
    from aiogram.types import BufferedInputFile
    
    file = await get_file_by_id(session, file_id)
    
    if not file or not file.file_data:
        await callback.message.answer("❌ Чек не найден или был удалён")
        return
    
    # Отправляем фото
    try:
        photo = BufferedInputFile(
            file.file_data,
            filename=file.filename or "receipt.jpg"
        )
        
        caption = f"📸 <b>{file.filename or 'Чек'}</b>\n\n"
        caption += f"📅 Загружен: {file.uploaded_at.strftime('%d.%m.%Y %H:%M')}\n"
        caption += f"📦 Размер: {(file.file_size or 0) // 1024} КБ"
        
        await callback.message.answer_photo(
            photo=photo,
            caption=caption,
            parse_mode="HTML"
        )
        
        await callback.message.answer(
            "👆 Чек отправлен выше",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 К списку чеков", callback_data=f"object:view_receipts:{file.object_id}")]
            ])
        )
        
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка отправки чека: {str(e)}")


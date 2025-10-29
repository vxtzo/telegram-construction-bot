"""
Обработчики для просмотра объектов
"""
from aiogram import Router, F
from aiogram.types import CallbackQuery
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
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    object_id = int(callback.data.split(":")[3])
    
    # Обновляем статус объекта
    obj = await update_object_status(session, object_id, ObjectStatus.COMPLETED)
    
    if not obj:
        await callback.answer("❌ Ошибка завершения объекта", show_alert=True)
        return
    
    await callback.message.edit_text(
        f"✅ <b>Объект завершен</b>\n\n"
        f"Объект <b>{obj.name}</b> успешно перемещен в раздел 'Завершённые объекты'.",
        parse_mode="HTML"
    )
    await callback.answer("✅ Объект завершен")


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


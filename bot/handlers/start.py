"""
Обработчик команды /start и главного меню
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole, ObjectStatus
from database.crud import get_object_by_id, get_files_by_object
from bot.handlers.objects import (
    build_documents_menu_content,
    group_document_files,
    document_counts,
    build_objects_list_view,
)
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.objects_kb import get_objects_menu
from bot.keyboards.reports_kb import get_reports_menu
from bot.utils.messaging import delete_message, send_new_message

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext, session: AsyncSession):
    """
    Обработчик команды /start
    
    Args:
        message: Сообщение от пользователя
        user: Пользователь из middleware (уже проверен и авторизован)
        state: FSM контекст
    """
    
    # Очищаем состояние на всякий случай
    await state.clear()
    
    # Проверяем deep-link аргументы
    payload = ""
    raw_text = message.text or ""
    parts = raw_text.split(maxsplit=1)
    if len(parts) > 1:
        payload = parts[1].strip()
    if payload:
        payload = payload.split()[0]

    if payload.startswith("docs_"):
        try:
            object_id = int(payload.split("_", 1)[1])
        except (IndexError, ValueError):
            await message.answer("❌ Неверная ссылка на документы.")
        else:
            obj = await get_object_by_id(session, object_id, load_relations=False)
            if obj:
                files = await get_files_by_object(session, object_id)
                grouped = group_document_files(files)
                counts = document_counts(grouped)
                text, markup = build_documents_menu_content(object_id, obj.name, counts)
                await message.answer(text, parse_mode="HTML", reply_markup=markup)
                return
            await message.answer("❌ Объект не найден.")

    # Приветственное сообщение
    welcome_text = f"""
👋 Добро пожаловать, {user.full_name or user.username or 'пользователь'}!

🏗️ Система управления строительными объектами

Ваша роль: {"👑 Администратор" if user.role == UserRole.ADMIN else "👷 Прораб"}

Выберите действие из меню ниже:
"""
    
    await message.answer(
        welcome_text.strip(),
        reply_markup=get_main_menu(user.role)
    )


@router.message(Command("help"))
async def cmd_help(message: Message, user: User):
    """Справка по командам"""
    
    help_text = """
📖 Справка по боту

🏗️ <b>Объекты</b> - просмотр текущих и завершенных объектов

"""
    
    if user.role == UserRole.ADMIN:
        help_text += """
<b>Для администраторов:</b>
➕ <b>Добавить объект</b> - создание нового объекта
📊 <b>Создать отчёт</b> - генерация отчетов
👥 <b>Управление пользователями</b> - добавление/удаление пользователей

<b>Команды:</b>
/start - Главное меню
/help - Справка
/add_user <telegram_id> <role> - Добавить пользователя (admin/foreman)
/remove_user <telegram_id> - Удалить пользователя
/list_users - Список всех пользователей
"""
    else:
        help_text += """
<b>Доступные действия:</b>
• Просмотр всех объектов
• Добавление расходов (расходники, транспорт, накладные)
• Добавление авансов рабочим

💡 Используйте текстовый или голосовой ввод для быстрого добавления расходов!
"""
    
    await message.answer(help_text.strip(), parse_mode="HTML")


@router.message(F.text == "🏗️ Объекты")
async def menu_objects(message: Message, user: User, session: AsyncSession, state: FSMContext):
    """Открыть меню объектов"""
    await state.clear()

    if user.role == UserRole.ADMIN:
        await message.answer(
            "🏗️ <b>ОБЪЕКТЫ</b>\n\nВыберите категорию:",
            parse_mode="HTML",
            reply_markup=get_objects_menu(user.role)
        )
        return

    text, markup = await build_objects_list_view(session, ObjectStatus.ACTIVE)
    await message.answer(text, parse_mode="HTML", reply_markup=markup)


@router.message(F.text == "📊 Создать отчёт")
async def menu_reports(message: Message, user: User, state: FSMContext):
    """Открыть меню отчетов (только для админа)"""
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для создания отчетов.")
        return
    
    await state.clear()
    await message.answer(
        "📊 <b>СОЗДАНИЕ ОТЧЁТА</b>\n\nВыберите тип отчёта:",
        parse_mode="HTML",
        reply_markup=get_reports_menu()
    )


@router.callback_query(F.data == "main_menu")
async def callback_main_menu(callback: CallbackQuery, user: User, state: FSMContext):
    """Вернуться в главное меню"""
    await state.clear()
    await send_new_message(
        callback,
        "🏠 <b>Главное меню</b>\n\nВыберите действие из меню ниже:",
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "objects:menu")
async def callback_objects_menu(callback: CallbackQuery, user: User, session: AsyncSession, state: FSMContext):
    """Вернуться в меню объектов"""
    await state.clear()

    if user.role == UserRole.ADMIN:
        await send_new_message(
            callback,
            "🏗️ <b>ОБЪЕКТЫ</b>\n\nВыберите категорию:",
            parse_mode="HTML",
            reply_markup=get_objects_menu(user.role),
        )
        await callback.answer()
        return

    text, markup = await build_objects_list_view(session, ObjectStatus.ACTIVE)
    await send_new_message(
        callback,
        text,
        parse_mode="HTML",
        reply_markup=markup,
    )
    await callback.answer()


@router.callback_query(F.data == "report:menu")
async def callback_reports_menu(callback: CallbackQuery, user: User, state: FSMContext):
    """Вернуться в меню отчетов"""
    
    if user.role != UserRole.ADMIN:
        await callback.answer("❌ Недостаточно прав", show_alert=True)
        return
    
    await state.clear()
    await send_new_message(
        callback,
        "📊 <b>СОЗДАНИЕ ОТЧЁТА</b>\n\nВыберите тип отчёта:",
        parse_mode="HTML",
        reply_markup=get_reports_menu()
    )
    await callback.answer()


@router.callback_query(F.data == "cancel")
async def callback_cancel(callback: CallbackQuery, user: User, state: FSMContext):
    """Отмена текущего действия"""
    await state.clear()
    await send_new_message(
        callback,
        "❌ Действие отменено.\n\nВыберите действие из меню ниже:"
    )
    await callback.answer("Отменено")


@router.callback_query(F.data == "no_action")
async def callback_no_action(callback: CallbackQuery):
    """Заглушка для неактивных кнопок"""
    await callback.answer()



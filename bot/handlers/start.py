"""
Обработчик команды /start и главного меню
"""
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole
from bot.keyboards.main_menu import get_main_menu
from bot.keyboards.objects_kb import get_objects_menu
from bot.keyboards.reports_kb import get_reports_menu
from bot.keyboards.start_kb import get_start_keyboard
from bot.utils.messaging import delete_message, send_new_message

router = Router()


@router.message(CommandStart())
async def cmd_start(message: Message, user: User, state: FSMContext):
    """
    Обработчик команды /start
    
    Args:
        message: Сообщение от пользователя
        user: Пользователь из middleware (уже проверен и авторизован)
        state: FSM контекст
    """
    
    # Очищаем состояние на всякий случай
    await state.clear()
    
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
async def menu_objects(message: Message, state: FSMContext):
    """Открыть меню объектов"""
    await state.clear()
    await message.answer(
        "🏗️ <b>ОБЪЕКТЫ</b>\n\nВыберите категорию:",
        parse_mode="HTML",
        reply_markup=get_objects_menu()
    )


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
async def callback_objects_menu(callback: CallbackQuery, state: FSMContext):
    """Вернуться в меню объектов"""
    await state.clear()
    await send_new_message(
        callback,
        "🏗️ <b>ОБЪЕКТЫ</b>\n\nВыберите категорию:",
        parse_mode="HTML",
        reply_markup=get_objects_menu(),
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



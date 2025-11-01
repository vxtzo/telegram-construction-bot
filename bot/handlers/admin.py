"""
Обработчики админ-панели для управления пользователями
"""
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, UserRole
from database.crud import (
    create_user,
    get_user_by_telegram_id,
    get_all_users,
    delete_user,
    update_user_active_status,
    DeleteUserResult,
)

router = Router()


@router.message(F.text == "👥 Управление пользователями")
async def admin_panel_menu(message: Message, user: User):
    """Меню управления пользователями"""
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для управления пользователями.")
        return
    
    help_text = """
👥 <b>Управление пользователями</b>

<b>Доступные команды:</b>

/add_user <code>&lt;telegram_id&gt; &lt;role&gt;</code>
Добавить нового пользователя
Роли: admin, foreman
Пример: <code>/add_user 123456789 foreman Иван Петров</code>

/remove_user <code>&lt;telegram_id&gt;</code>
Удалить пользователя
Пример: <code>/remove_user 123456789</code>

/block_user <code>&lt;telegram_id&gt;</code>
Заблокировать пользователя

/unblock_user <code>&lt;telegram_id&gt;</code>
Разблокировать пользователя

/list_users
Показать список всех пользователей
"""
    
    await message.answer(help_text.strip(), parse_mode="HTML")


@router.message(Command("add_user"))
async def cmd_add_user(message: Message, user: User, session: AsyncSession):
    """Добавить или обновить пользователя (/add_user <telegram_id> <role> <ФИО>)"""

    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return

    parts = message.text.split()

    if len(parts) < 4:
        await message.answer(
            "❌ Неверный формат команды.\n\n"
            "Использование: <code>/add_user &lt;telegram_id&gt; &lt;role&gt; &lt;имя&gt;</code>\n\n"
            "Роли: admin, foreman\n"
            "Пример: <code>/add_user 123456789 foreman Иван Петров</code>",
            parse_mode="HTML"
        )
        return

    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return

    role_str = parts[2].lower()
    if role_str not in ["admin", "foreman"]:
        await message.answer("❌ Неверная роль. Доступные роли: admin, foreman")
        return

    role = UserRole.ADMIN if role_str == "admin" else UserRole.FOREMAN
    full_name = " ".join(parts[3:]).strip()

    if not full_name:
        await message.answer("❌ Укажите имя пользователя после роли.")
        return

    existing_user = await get_user_by_telegram_id(session, telegram_id)

    if existing_user:
        existing_user.role = role
        existing_user.full_name = full_name
        await session.commit()
        await message.answer(
            "♻️ Пользователь обновлён.\n\n"
            f"Имя: {full_name}\n"
            f"Роль: {role.value}"
        )
        return

    new_user = await create_user(
        session=session,
        telegram_id=telegram_id,
        role=role,
        full_name=full_name
    )

    await message.answer(
        f"✅ Пользователь добавлен!\n\n"
        f"Имя: {full_name}\n"
        f"Telegram ID: {telegram_id}\n"
        f"Роль: {role.value}\n\n"
        f"Пользователь может начать работу с ботом командой /start"
    )


@router.message(Command("remove_user"))
async def cmd_remove_user(message: Message, user: User, session: AsyncSession):
    """
    Удалить пользователя
    
    Формат: /remove_user <telegram_id>
    """
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды.\n\n"
            "Использование: <code>/remove_user &lt;telegram_id&gt;</code>\n"
            "Пример: <code>/remove_user 123456789</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return
    
    # Проверяем, что это не сам админ
    if telegram_id == user.telegram_id:
        await message.answer("❌ Вы не можете удалить самого себя.")
        return
    
    # Удаляем пользователя
    result = await delete_user(session, telegram_id)

    if result == DeleteUserResult.DELETED:
        await message.answer(
            f"✅ Пользователь с Telegram ID {telegram_id} успешно удалён."
        )
    elif result == DeleteUserResult.DEACTIVATED:
        await message.answer(
            "ℹ️ Пользователь имеет связанные расходы или объекты, поэтому вместо удаления он помечен как неактивный."
        )
    else:
        await message.answer(
            f"❌ Пользователь с Telegram ID {telegram_id} не найден."
        )


@router.message(Command("block_user"))
async def cmd_block_user(message: Message, user: User, session: AsyncSession):
    """
    Заблокировать пользователя
    
    Формат: /block_user <telegram_id>
    """
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды.\n\n"
            "Использование: <code>/block_user &lt;telegram_id&gt;</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return
    
    if telegram_id == user.telegram_id:
        await message.answer("❌ Вы не можете заблокировать самого себя.")
        return
    
    # Блокируем пользователя
    updated_user = await update_user_active_status(session, telegram_id, False)
    
    if updated_user:
        await message.answer(
            f"✅ Пользователь с Telegram ID {telegram_id} заблокирован."
        )
    else:
        await message.answer(
            f"❌ Пользователь с Telegram ID {telegram_id} не найден."
        )


@router.message(Command("unblock_user"))
async def cmd_unblock_user(message: Message, user: User, session: AsyncSession):
    """
    Разблокировать пользователя
    
    Формат: /unblock_user <telegram_id>
    """
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.answer(
            "❌ Неверный формат команды.\n\n"
            "Использование: <code>/unblock_user &lt;telegram_id&gt;</code>",
            parse_mode="HTML"
        )
        return
    
    try:
        telegram_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Telegram ID должен быть числом.")
        return
    
    # Разблокируем пользователя
    updated_user = await update_user_active_status(session, telegram_id, True)
    
    if updated_user:
        await message.answer(
            f"✅ Пользователь с Telegram ID {telegram_id} разблокирован."
        )
    else:
        await message.answer(
            f"❌ Пользователь с Telegram ID {telegram_id} не найден."
        )


@router.message(Command("list_users"))
async def cmd_list_users(message: Message, user: User, session: AsyncSession):
    """Показать список всех пользователей"""
    
    if user.role != UserRole.ADMIN:
        await message.answer("❌ У вас нет прав для выполнения этой команды.")
        return
    
    # Получаем всех пользователей
    users = await get_all_users(session)
    
    if not users:
        await message.answer("📋 Список пользователей пуст.")
        return
    
    # Формируем список
    text = "👥 <b>Список пользователей</b>\n\n"
    
    for u in users:
        status = "✅" if u.is_active else "❌"
        role_emoji = "👑" if u.role == UserRole.ADMIN else "👷"
        name = u.full_name or u.username or "Без имени"
        
        text += f"{status} {role_emoji} <b>{name}</b>\n"
        text += f"   ID: <code>{u.telegram_id}</code>\n"
        text += f"   Роль: {u.role.value}\n"
        text += f"   Добавлен: {u.created_at.strftime('%d.%m.%Y')}\n\n"
    
    text += f"Всего пользователей: {len(users)}"
    
    await message.answer(text.strip(), parse_mode="HTML")




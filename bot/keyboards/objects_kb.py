"""
Клавиатуры для работы с объектами
"""
from typing import List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from database.models import ConstructionObject, ObjectStatus, UserRole


def get_objects_menu() -> InlineKeyboardMarkup:
    """Меню раздела Объекты"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="▫️ Текущие объекты", callback_data="objects:active")
    )
    builder.row(
        InlineKeyboardButton(text="▫️ Завершённые объекты", callback_data="objects:completed")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    )
    return builder.as_markup()


def get_objects_list_keyboard(
    objects: List[ConstructionObject],
    status: ObjectStatus
) -> InlineKeyboardMarkup:
    """
    Клавиатура со списком объектов
    
    Args:
        objects: Список объектов
        status: Статус объектов
    """
    builder = InlineKeyboardBuilder()
    
    if not objects:
        builder.row(
            InlineKeyboardButton(text="Нет объектов", callback_data="no_action")
        )
    else:
        for obj in objects:
            # Обрезаем название если слишком длинное
            name = obj.name if len(obj.name) <= 40 else f"{obj.name[:37]}..."
            builder.row(
                InlineKeyboardButton(
                    text=f"🏗️ {name}",
                    callback_data=f"object:view:{obj.id}"
                )
            )
    
    # Кнопка Назад
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="objects:menu")
    )
    
    return builder.as_markup()


def get_object_card_keyboard(
    object_id: int,
    status: ObjectStatus,
    user_role: UserRole
) -> InlineKeyboardMarkup:
    """
    Клавиатура карточки объекта
    
    Args:
        object_id: ID объекта
        status: Статус объекта
        user_role: Роль пользователя
    """
    builder = InlineKeyboardBuilder()
    
    if status == ObjectStatus.ACTIVE:
        # Кнопки для текущего объекта
        
        # Все могут добавлять расходы и авансы
        builder.row(
            InlineKeyboardButton(
                text="➕ Добавить расходники",
                callback_data=f"expense:add:supplies:{object_id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="🚚 Добавить транспортные",
                callback_data=f"expense:add:transport:{object_id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="💵 Добавить аванс",
                callback_data=f"advance:add:{object_id}"
            )
        )
        builder.row(
            InlineKeyboardButton(
                text="📸 Посмотреть чеки",
                callback_data=f"object:view_receipts:{object_id}"
            )
        )
        
        # Только админ может завершать объекты
        if user_role == UserRole.ADMIN:
            builder.row(
                InlineKeyboardButton(
                    text="✅ Завершить объект",
                    callback_data=f"object:complete:{object_id}"
                )
            )
    
    elif status == ObjectStatus.COMPLETED:
        # Кнопки для завершенного объекта
        
        # Только админ может вернуть объект
        if user_role == UserRole.ADMIN:
            builder.row(
                InlineKeyboardButton(
                    text="🔁 Вернуть в текущие",
                    callback_data=f"object:restore:{object_id}"
                )
            )
    
    # Кнопка Назад
    back_status = "active" if status == ObjectStatus.ACTIVE else "completed"
    builder.row(
        InlineKeyboardButton(
            text="🔙 Назад к списку",
            callback_data=f"objects:{back_status}"
        )
    )
    
    return builder.as_markup()


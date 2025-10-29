"""
Главное меню и основные клавиатуры
"""
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder
from database.models import UserRole


def get_main_menu(user_role: UserRole) -> ReplyKeyboardMarkup:
    """
    Главное меню в зависимости от роли
    
    Args:
        user_role: Роль пользователя
        
    Returns:
        Клавиатура главного меню
    """
    builder = ReplyKeyboardBuilder()
    
    # Кнопки доступные всем
    builder.row(
        KeyboardButton(text="🏗️ Объекты")
    )
    
    # Кнопки только для админа
    if user_role == UserRole.ADMIN:
        builder.row(
            KeyboardButton(text="➕ Добавить объект"),
            KeyboardButton(text="📊 Создать отчёт")
        )
        builder.row(
            KeyboardButton(text="👥 Управление пользователями")
        )
    
    builder.adjust(1)  # По 1 кнопке в ряд
    
    return builder.as_markup(resize_keyboard=True)


def get_back_button() -> InlineKeyboardMarkup:
    """Кнопка Назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Назад", callback_data="back")
    return builder.as_markup()


def get_cancel_button() -> InlineKeyboardMarkup:
    """Кнопка Отмена"""
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel")
    return builder.as_markup()


def get_confirm_keyboard(confirm_data: str, cancel_data: str = "cancel") -> InlineKeyboardMarkup:
    """
    Клавиатура подтверждения
    
    Args:
        confirm_data: callback_data для кнопки подтверждения
        cancel_data: callback_data для кнопки отмены
    """
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Подтвердить", callback_data=confirm_data),
        InlineKeyboardButton(text="❌ Отмена", callback_data=cancel_data)
    )
    return builder.as_markup()


def get_skip_or_cancel() -> InlineKeyboardMarkup:
    """Кнопки Пропустить и Отмена"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⏭️ Пропустить", callback_data="skip"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()



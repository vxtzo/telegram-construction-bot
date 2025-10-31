"""
Клавиатуры для генерации отчетов
"""
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List
from database.models import ConstructionObject


def get_reports_menu() -> InlineKeyboardMarkup:
    """Меню создания отчетов"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Отчёт за период", callback_data="report:period")
    )
    builder.row(
        InlineKeyboardButton(text="🧱 Отчёт за завершённый объект", callback_data="report:object")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Главное меню", callback_data="main_menu")
    )
    return builder.as_markup()


def get_period_selection() -> InlineKeyboardMarkup:
    """Выбор периода для отчета"""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 За год", callback_data="report:period:year")
    )
    builder.row(
        InlineKeyboardButton(text="📅 За месяц", callback_data="report:period:month")
    )
    builder.row(
        InlineKeyboardButton(text="📅 За диапазон дат", callback_data="report:period:range")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="report:menu")
    )
    return builder.as_markup()


def get_years_keyboard(years: List[int], callback_prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for year in years:
        builder.button(text=str(year), callback_data=f"{callback_prefix}:{year}")
    if years:
        builder.adjust(3)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))
    return builder.as_markup()


def get_months_keyboard(year: int, callback_prefix: str, back_callback: str) -> InlineKeyboardMarkup:
    months = [
        "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
        "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
    ]

    builder = InlineKeyboardBuilder()
    for idx, name in enumerate(months, start=1):
        builder.button(text=name, callback_data=f"{callback_prefix}:{year}:{idx:02d}")
    builder.adjust(3)
    builder.row(InlineKeyboardButton(text="🔙 Назад", callback_data=back_callback))
    return builder.as_markup()


def get_completed_objects_list(objects: List[ConstructionObject]) -> InlineKeyboardMarkup:
    """
    Список завершенных объектов для отчета
    
    Args:
        objects: Список завершенных объектов
    """
    builder = InlineKeyboardBuilder()
    
    if not objects:
        builder.row(
            InlineKeyboardButton(text="Нет завершённых объектов", callback_data="no_action")
        )
    else:
        for obj in objects:
            name = obj.name if len(obj.name) <= 40 else f"{obj.name[:37]}..."
            builder.row(
                InlineKeyboardButton(
                    text=f"📄 {name}",
                    callback_data=f"report:generate:{obj.id}"
                )
            )
    
    builder.row(
        InlineKeyboardButton(text="🔙 Назад", callback_data="report:menu")
    )
    
    return builder.as_markup()




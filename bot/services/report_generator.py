"""
Генератор отчетов по объектам
"""
from datetime import datetime
from typing import List
from database.models import ConstructionObject, File, FileType
from bot.services.calculations import calculate_profit_data, format_currency, format_percentage


def generate_object_report(obj: ConstructionObject, files: List[File] = None) -> str:
    """
    Генерация текстового отчета по объекту
    
    Args:
        obj: Объект строительства с загруженными расходами и авансами
        files: Список файлов объекта
        
    Returns:
        Отформатированный текст отчета
    """
    
    # Рассчитываем все показатели
    data = calculate_profit_data(obj)
    
    # Форматируем даты
    start_date = obj.start_date.strftime("%d.%m.%Y") if obj.start_date else "—"
    end_date = obj.end_date.strftime("%d.%m.%Y") if obj.end_date else "—"
    
    # Формируем отчет
    report = f"""
🏗️ ОБЪЕКТ: {obj.name}
📍 Адрес: {obj.address or '—'}
👷 Бригадир: {obj.foreman_name or '—'}
📅 Период: {start_date} — {end_date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💸 Финансы
Предоплата: {format_currency(data['prepayment'])}
Окончательная оплата: {format_currency(data['final_payment'])}
Всего поступлений: {format_currency(data['total_income'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧱 Облицовка С3
По смете: {format_currency(data['estimate_s3'])}
Со скидкой: {format_currency(data['actual_s3_discount'])}
Разница: {format_currency(data['s3_difference'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⚒ Работы
По смете: {format_currency(data['estimate_works'])}
ФЗП мастера (45%): {format_currency(data['fzp_master'])}
ФЗП бригадира (10%): {format_currency(data['fzp_foreman'])}
Прибыль фирмы: {format_currency(data['work_profit'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🧰 Расходники
По смете: {format_currency(data['estimate_supplies'])}
Потрачено по факту: {format_currency(data['supplies_fact'])}
Разница: {format_currency(data['supplies_difference'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

💰 Накладные расходы
По смете: {format_currency(data['estimate_overhead'])}
Потрачено по факту: {format_currency(data['overhead_fact'])}
Разница: {format_currency(data['overhead_difference'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚚 Транспортные услуги
По смете: {format_currency(data['estimate_transport'])}
Потрачено по факту: {format_currency(data['transport_fact'])}
Разница: {format_currency(data['transport_difference'])}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Итоговые показатели
Общие доходы: {format_currency(data['total_income'])}
Общие расходы: {format_currency(data['total_expenses'])}
💰 Прибыль: {format_currency(data['total_profit'])}
📈 Рентабельность: {format_percentage(data['profitability'])}
"""
    
    # Добавляем информацию о файлах, если есть
    if files:
        report += "\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        report += "📎 Приложения:\n"
        
        photos = [f for f in files if f.file_type == FileType.PHOTO]
        receipts = [f for f in files if f.file_type == FileType.RECEIPT]
        docs = [f for f in files if f.file_type == FileType.DOCUMENT]
        
        if photos:
            report += f"📷 Фото: {len(photos)} шт.\n"
        if receipts:
            report += f"🧾 Чеки: {len(receipts)} шт.\n"
        if docs:
            report += f"📄 Документы: {len(docs)} шт.\n"
    
    return report.strip()


def generate_short_object_card(obj: ConstructionObject) -> str:
    """
    Генерация краткой карточки объекта
    
    Args:
        obj: Объект строительства
        
    Returns:
        Краткая информация об объекте
    """
    
    # Статус
    status_emoji = "🟢" if obj.status.value == "active" else "✅"
    status_text = "Текущий" if obj.status.value == "active" else "Завершенный"
    
    # Даты
    start_date = obj.start_date.strftime("%d.%m.%Y") if obj.start_date else "—"
    end_date = obj.end_date.strftime("%d.%m.%Y") if obj.end_date else "—"
    
    card = f"""
{status_emoji} {obj.name}
📍 {obj.address or '—'}
👷 Бригадир: {obj.foreman_name or '—'}
📅 {start_date} — {end_date}
💰 Бюджет: {format_currency(obj.prepayment + obj.final_payment)}
Статус: {status_text}
"""
    
    return card.strip()


def generate_period_report(objects: List[ConstructionObject], period_str: str) -> str:
    """
    Генерация сводного отчета за период
    
    Args:
        objects: Список объектов за период
        period_str: Строка с описанием периода
        
    Returns:
        Сводный отчет
    """
    
    if not objects:
        return f"📊 Отчет за {period_str}\n\nНет объектов за указанный период."
    
    # Считаем агрегированные показатели
    from decimal import Decimal
    total_income = Decimal(0)
    total_profit = Decimal(0)
    total_expenses = Decimal(0)
    
    for obj in objects:
        data = calculate_profit_data(obj)
        total_income += data['total_income']
        total_profit += data['total_profit']
        total_expenses += data['total_expenses']
    
    # Средняя рентабельность
    avg_profitability = (total_profit / total_income * 100) if total_income > 0 else Decimal(0)
    
    report = f"""
📊 СВОДНЫЙ ОТЧЕТ ЗА {period_str.upper()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Общие показатели:
Количество объектов: {len(objects)}
Общий доход: {format_currency(total_income)}
Общие расходы: {format_currency(total_expenses)}
Общая прибыль: {format_currency(total_profit)}
Средняя рентабельность: {format_percentage(avg_profitability)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Список объектов:
"""
    
    # Добавляем краткую информацию по каждому объекту
    for i, obj in enumerate(objects, 1):
        data = calculate_profit_data(obj)
        report += f"\n{i}. {obj.name}\n"
        report += f"   💰 Прибыль: {format_currency(data['total_profit'])}\n"
        report += f"   📈 Рентабельность: {format_percentage(data['profitability'])}\n"
    
    return report.strip()


"""
Генератор отчетов по объектам
"""
from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from database.models import ConstructionObject, File, FileType
from bot.services.calculations import calculate_profit_data, format_currency, format_percentage


def _currency(value: Decimal) -> str:
    return format_currency(value).replace("₽", " ₽")


def _percentage(value: Decimal) -> str:
    return format_percentage(value).replace("%", " %")


def _format_delta(value: Decimal) -> str:
    if value > 0:
        return f"🟩 +{_currency(value)}"
    if value < 0:
        return f"🟥 -{_currency(abs(value))}"
    return f"⬜ {_currency(Decimal(0))}"


def _format_positive(value: Decimal) -> str:
    if value > 0:
        return f"🟩 {_currency(value)}"
    if value < 0:
        return f"🟥 {_currency(abs(value))}"
    return f"⬜ {_currency(Decimal(0))}"


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
    total_advances_amount = sum(
        (advance.amount for advance in getattr(obj, "advances", [])),
        Decimal(0)
    )
    
    # Форматируем даты
    start_date = obj.start_date.strftime("%d.%m.%Y") if obj.start_date else "—"
    end_date = obj.end_date.strftime("%d.%m.%Y") if obj.end_date else "—"
    
    # Формируем отчет
    lines = [
        f"🏗 ОБЪЕКТ: {obj.name}",
        f"📍 Адрес: {obj.address or '—'}",
        f"👷 Бригадир: {obj.foreman_name or '—'}",
        f"📅 Период: {start_date} — {end_date}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "💸 ФИНАНСЫ",
        "",
        f"Предоплата: {_currency(data['prepayment'])}",
        f"Окончательная оплата: {_currency(data['final_payment'])}",
        f"💰 Всего поступлений: {_currency(data['total_income'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "🧱 ОБЛИЦОВКА С3",
        "",
        f"По смете: {_currency(data['estimate_s3'])}",
        f"Со скидкой: {_currency(data['actual_s3_discount'])}",
        f"Разница: {_format_delta(data['s3_difference'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "⚒️ РАБОТЫ",
        "",
        f"По смете: {_currency(data['estimate_works'])}",
        f"ФЗП мастера (45 %): {_currency(data['fzp_master'])}",
        f"ФЗП бригадира (10 %): {_currency(data['fzp_foreman'])}",
        f"Выдано на данный момент: {_currency(total_advances_amount)}",
        f"Прибыль фирмы: {_format_positive(data['work_profit'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "🧰 РАСХОДНИКИ",
        "",
        f"По смете: {_currency(data['estimate_supplies'])}",
        f"Потрачено по факту: {_currency(data['supplies_fact'])}",
        f"Разница: {_format_delta(data['supplies_difference'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "💰 НАКЛАДНЫЕ РАСХОДЫ",
        "",
        f"По смете: {_currency(data['estimate_overhead'])}",
        f"Потрачено по факту: {_currency(data['overhead_fact'])}",
        f"Разница: {_format_delta(data['overhead_difference'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "🚚 ТРАНСПОРТНЫЕ УСЛУГИ",
        "",
        f"По смете: {_currency(data['estimate_transport'])}",
        f"Потрачено по факту: {_currency(data['transport_fact'])}",
        f"Разница: {_format_delta(data['transport_difference'])}",
        "",
        "━━━━━━━━━━━━━━━━━━━",
        "",
        "📊 ИТОГОВЫЕ ПОКАЗАТЕЛИ",
        "",
        f"Общие доходы: {_currency(data['total_income'])}",
        f"💰 Прибыль: {_format_positive(data['total_profit'])}",
        f"📈 Рентабельность: {_percentage(data['profitability'])}",
    ]

    if files:
        receipts = [f for f in files if f.file_type == FileType.RECEIPT]
        docs = [f for f in files if f.file_type == FileType.DOCUMENT]
        photos = [f for f in files if f.file_type == FileType.PHOTO]

        attachments = []
        if receipts:
            attachments.append(f"🧾 Чеки: {len(receipts)} шт.")
        if docs:
            attachments.append(f"📄 Документы: {len(docs)} шт.")
        if photos:
            attachments.append(f"📷 Фото: {len(photos)} шт.")

        if attachments:
            lines.extend([
                "",
                "━━━━━━━━━━━━━━━━━━━",
                "",
                "📎 ПРИЛОЖЕНИЯ",
                "",
                *attachments,
            ])

    return "\n".join(lines).strip()


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


def generate_period_report(
    objects: List[ConstructionObject],
    period_str: str,
    company_expenses: Optional[dict] = None,
) -> str:
    """
    Генерация сводного отчета за период
    
    Args:
        objects: Список объектов за период
        period_str: Строка с описанием периода
        
    Returns:
        Сводный отчет
    """
    
    company_data = company_expenses or {"one_time": Decimal(0), "recurring": Decimal(0), "total": Decimal(0)}

    if not objects and company_data["total"] == 0:
        return f"📊 Отчет за {period_str}\n\nНет данных за указанный период."
    
    # Считаем агрегированные показатели
    total_income = Decimal(0)
    total_profit = Decimal(0)
    
    for obj in objects:
        data = calculate_profit_data(obj)
        total_income += data['total_income']
        total_profit += data['total_profit']
    
    company_total = company_data.get("total", Decimal(0))
    company_one_time = company_data.get("one_time", Decimal(0))
    company_recurring = company_data.get("recurring", Decimal(0))

    adjusted_profit = total_profit - company_total

    avg_profitability = (adjusted_profit / total_income * 100) if total_income > 0 else Decimal(0)
    
    report = f"""
📊 СВОДНЫЙ ОТЧЕТ ЗА {period_str.upper()}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📈 Общие показатели:
Количество объектов: {len(objects)}
Общий доход: {format_currency(total_income)}
Расходы фирмы: {format_currency(company_total)}
Общая прибыль: {format_currency(adjusted_profit)}
Средняя рентабельность: {format_percentage(avg_profitability)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🏢 Расходы фирмы:
   • Разовые: {format_currency(company_one_time)}
   • Ежемесячные: {format_currency(company_recurring)}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Список объектов:
"""

    if objects:
        for i, obj in enumerate(objects, 1):
            data = calculate_profit_data(obj)
            report += f"\n{i}. {obj.name}\n"
            report += f"   💰 Прибыль: {format_currency(data['total_profit'])}\n"
            report += f"   📈 Рентабельность: {format_percentage(data['profitability'])}\n"
    else:
        report += "\nНет объектов за период."
    
    return report.strip()


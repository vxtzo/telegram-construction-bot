"""
Сервис расчета прибыли, ФЗП и рентабельности
"""
from decimal import Decimal
from typing import Dict
from database.models import ConstructionObject


def calculate_profit_data(obj: ConstructionObject) -> Dict[str, Decimal]:
    """
    Рассчитать все финансовые показатели объекта
    
    Формула прибыли:
    Прибыль = (С3_смета - С3_скидка) + 
              (0.45 × Работы_смета) + 
              (Расходники_смета - Расходники_факт) +
              (Накладные_смета - Накладные_факт) +
              (Транспорт_смета - Транспорт_факт)
    
    Args:
        obj: Объект строительства с загруженными расходами
        
    Returns:
        Dict с финансовыми показателями
    """
    
    # Всего поступлений
    total_income = obj.prepayment + obj.final_payment
    
    # Разница по С3
    s3_difference = obj.estimate_s3 - obj.actual_s3_discount
    
    # ФЗП
    fzp_master = obj.estimate_works * Decimal("0.45")  # 45%
    fzp_foreman = obj.estimate_works * Decimal("0.10")  # 10%
    fzp_total = fzp_master + fzp_foreman
    
    # Прибыль фирмы с работ (остаток после ФЗП)
    work_profit = obj.estimate_works - fzp_total
    
    # Расчет фактических расходов по типам
    supplies_fact = sum(
        expense.amount for expense in obj.expenses 
        if expense.type.value == "supplies"
    )
    transport_fact = sum(
        expense.amount for expense in obj.expenses 
        if expense.type.value == "transport"
    )
    overhead_fact = sum(
        expense.amount for expense in obj.expenses 
        if expense.type.value == "overhead"
    )
    
    # Разницы
    supplies_difference = obj.estimate_supplies - supplies_fact
    overhead_difference = obj.estimate_overhead - overhead_fact
    transport_difference = obj.estimate_transport - transport_fact
    
    # Общая прибыль
    total_profit = (
        s3_difference +
        work_profit +
        supplies_difference +
        overhead_difference +
        transport_difference
    )
    
    # Общие расходы
    total_expenses = (
        obj.actual_s3_discount +
        fzp_total +
        supplies_fact +
        overhead_fact +
        transport_fact
    )
    
    # Рентабельность
    profitability = (total_profit / total_income * 100) if total_income > 0 else Decimal(0)
    
    return {
        # Доходы
        "total_income": total_income,
        "prepayment": obj.prepayment,
        "final_payment": obj.final_payment,
        
        # С3
        "estimate_s3": obj.estimate_s3,
        "actual_s3_discount": obj.actual_s3_discount,
        "s3_difference": s3_difference,
        
        # Работы и ФЗП
        "estimate_works": obj.estimate_works,
        "fzp_master": fzp_master,
        "fzp_foreman": fzp_foreman,
        "fzp_total": fzp_total,
        "work_profit": work_profit,
        
        # Расходники
        "estimate_supplies": obj.estimate_supplies,
        "supplies_fact": supplies_fact,
        "supplies_difference": supplies_difference,
        
        # Накладные
        "estimate_overhead": obj.estimate_overhead,
        "overhead_fact": overhead_fact,
        "overhead_difference": overhead_difference,
        
        # Транспорт
        "estimate_transport": obj.estimate_transport,
        "transport_fact": transport_fact,
        "transport_difference": transport_difference,
        
        # Итоги
        "total_expenses": total_expenses,
        "total_profit": total_profit,
        "profitability": profitability,
    }


def format_currency(amount: Decimal) -> str:
    """Форматировать сумму в рублях"""
    return f"{amount:,.2f}₽".replace(",", " ")


def format_percentage(value: Decimal) -> str:
    """Форматировать процент"""
    return f"{value:.2f}%"


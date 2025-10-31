"""
FSM состояния для добавления расходов и авансов
"""
from aiogram.fsm.state import State, StatesGroup


class AddExpenseStates(StatesGroup):
    """Состояния для добавления расхода"""
    
    waiting_input = State()  # Ожидание текста или голоса
    confirm_expense = State()  # Подтверждение распарсенных данных
    select_payment_source = State()  # Выбор источника оплаты
    waiting_photo = State()  # Ожидание фото чека (опционально)


class AddAdvanceStates(StatesGroup):
    """Состояния для добавления аванса"""
    
    waiting_input = State()  # Ожидание текста или голоса
    confirm_advance = State()  # Подтверждение распарсенных данных


class ReportPeriodStates(StatesGroup):
    """Состояния для выбора периода отчета"""
    
    waiting_year = State()
    waiting_month = State()
    waiting_date_from = State()
    waiting_date_to = State()


class EditExpenseStates(StatesGroup):
    """Состояния для редактирования расхода"""

    choose_field = State()
    waiting_value = State()
    choose_payment_source = State()


class EditAdvanceStates(StatesGroup):
    """Состояния для редактирования аванса"""

    choose_field = State()
    waiting_value = State()



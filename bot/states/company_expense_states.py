"""FSM состояния для управления расходами фирмы"""
from aiogram.fsm.state import State, StatesGroup


class CompanyExpenseStates(StatesGroup):
    waiting_input = State()
    confirm = State()
    waiting_date_manual = State()


class CompanyRecurringExpenseStates(StatesGroup):
    waiting_input = State()
    confirm = State()
    waiting_day_manual = State()
    waiting_start_manual = State()

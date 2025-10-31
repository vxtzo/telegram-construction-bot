"""FSM состояния для управления расходами фирмы"""
from aiogram.fsm.state import State, StatesGroup


class CompanyExpenseStates(StatesGroup):
    choosing_category = State()
    waiting_amount = State()
    waiting_date = State()
    waiting_description = State()


class CompanyRecurringExpenseStates(StatesGroup):
    choosing_category = State()
    waiting_amount = State()
    waiting_period = State()
    waiting_description = State()

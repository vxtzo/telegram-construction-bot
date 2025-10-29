"""
FSM состояния для добавления объекта
"""
from aiogram.fsm.state import State, StatesGroup


class AddObjectStates(StatesGroup):
    """Состояния для пошагового создания объекта"""
    
    # Основная информация
    enter_name = State()
    enter_address = State()
    enter_foreman = State()
    enter_dates = State()
    
    # Финансы
    enter_prepayment = State()
    enter_final_payment = State()
    
    # Смета
    enter_estimate_s3 = State()
    enter_actual_s3_discount = State()
    enter_estimate_works = State()
    enter_estimate_supplies = State()
    enter_estimate_overhead = State()
    enter_estimate_transport = State()
    
    # Подтверждение
    confirm_object = State()



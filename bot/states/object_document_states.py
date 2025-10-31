"""Состояния для загрузки документов объекта"""
from aiogram.fsm.state import State, StatesGroup


class ObjectDocumentStates(StatesGroup):
    """Состояния FSM для работы с документами объекта"""

    waiting_document = State()



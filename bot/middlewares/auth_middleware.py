"""
Middleware для проверки авторизации пользователей
"""
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from database.crud import get_user_by_telegram_id
from database.models import UserRole


class AuthMiddleware(BaseMiddleware):
    """Middleware для проверки доступа пользователя"""
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """
        Проверка доступа пользователя
        
        Args:
            handler: Обработчик события
            event: Событие (Message или CallbackQuery)
            data: Данные контекста
        """
        
        # Получаем session из data (должна быть добавлена раньше)
        session: AsyncSession = data.get("session")
        
        if not session:
            # Если нет сессии, пропускаем
            return await handler(event, data)
        
        # Получаем telegram_id пользователя
        if isinstance(event, Message):
            telegram_id = event.from_user.id
        elif isinstance(event, CallbackQuery):
            telegram_id = event.from_user.id
        else:
            return await handler(event, data)
        
        # Проверяем пользователя в БД
        user = await get_user_by_telegram_id(session, telegram_id)
        
        # Добавляем пользователя в контекст
        data["user"] = user
        data["telegram_id"] = telegram_id
        
        # Если пользователь не найден или не активен, блокируем доступ
        if not user or not user.is_active:
            if isinstance(event, Message):
                await event.answer(
                    "❌ Доступ запрещен.\n\n"
                    "Вы не авторизованы для использования этого бота.\n"
                    "Обратитесь к администратору для получения доступа."
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Доступ запрещен", show_alert=True)
            
            return  # Не вызываем handler
        
        # Пользователь авторизован, продолжаем обработку
        return await handler(event, data)


class RoleMiddleware(BaseMiddleware):
    """Middleware для проверки роли пользователя"""
    
    def __init__(self, allowed_roles: list[UserRole]):
        """
        Args:
            allowed_roles: Список разрешенных ролей
        """
        self.allowed_roles = allowed_roles
        super().__init__()
    
    async def __call__(
        self,
        handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: Message | CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        """Проверка роли пользователя"""
        
        user = data.get("user")
        
        if not user:
            # Пользователь не авторизован (должно было быть проверено AuthMiddleware)
            return
        
        # Проверяем роль
        if user.role not in self.allowed_roles:
            if isinstance(event, Message):
                await event.answer(
                    "❌ У вас нет прав для выполнения этого действия.\n\n"
                    f"Требуется роль: {', '.join([r.value for r in self.allowed_roles])}\n"
                    f"Ваша роль: {user.role.value}"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer("❌ Недостаточно прав", show_alert=True)
            
            return  # Не вызываем handler
        
        # Роль подходит, продолжаем
        return await handler(event, data)



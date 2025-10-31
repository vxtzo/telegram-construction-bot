"""Utility helpers for managing callback replies and bot metadata."""
import contextlib
from typing import Any, Optional

from aiogram import Bot
from aiogram.types import CallbackQuery, Message


async def delete_message(message: Message) -> None:
    with contextlib.suppress(Exception):
        await message.delete()


async def send_new_message(
    callback: CallbackQuery,
    text: str,
    **kwargs: Any,
):
    await delete_message(callback.message)
    return await callback.message.answer(text, **kwargs)


async def get_bot_username(bot: Bot | None) -> Optional[str]:
    """Безопасно получить username бота (кешируется в объекте Bot)."""

    if not bot:
        return None

    cached = getattr(bot, "_cached_username", None)
    if cached is not None:
        return cached

    try:
        me = await bot.get_me()
    except Exception:
        username: Optional[str] = None
    else:
        username = me.username

    setattr(bot, "_cached_username", username)
    return username


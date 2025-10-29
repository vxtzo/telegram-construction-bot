"""Utility helpers for managing callback replies."""
import contextlib
from typing import Any

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


"""Сервис для обработки PDF смет и извлечения структурированных данных для объекта."""
import asyncio
import json
from typing import Any, Dict

import pdfplumber
from openai import AsyncOpenAI

from bot.config import config


_openai_client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


async def extract_text_from_pdf(file_path: str) -> str:
    """Извлекает текст из PDF-файла в неблокирующем режиме."""

    def _sync_extract() -> str:
        chunks: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text() or ""
                chunks.append(page_text)
        return "\n".join(chunks)

    return await asyncio.to_thread(_sync_extract)


async def parse_pdf_to_object_data(text: str) -> Dict[str, Any]:
    """Отправляет извлечённый текст сметы в LLM и возвращает структуру данных объекта."""

    system_prompt = (
        "Ты помогаешь заполнить карточку строительного объекта по тексту сметы. "
        "Облицовка С3 указана в разделах с формулировками 'облицовочные элементы', "
        "'финишное покрытие', 'затирка'. Строка 'расходные материалы' соответствует расходникам."
    )

    user_prompt = (
        "Ниже текст сметы. Извлеки данные и верни JSON со строгой схемой.\n"
        "Если значение отсутствует, используй null. Суммы возвращай числом (можно с точкой).\n\n"
        "Текст сметы:\n"
        f"{text}"
    )

    schema_hint = {
        "name": "string | null",
        "address": "string | null",
        "foreman_name": "string | null",
        "start_date": "YYYY-MM-DD | null",
        "end_date": "YYYY-MM-DD | null",
        "prepayment": "number | null",
        "final_payment": "number | null",
        "estimate_s3": "number | null",
        "actual_s3_discount": "number | null",
        "estimate_works": "number | null",
        "estimate_supplies": "number | null",
        "estimate_overhead": "number | null",
        "estimate_transport": "number | null"
    }

    format_instructions = (
        "Верни только JSON без комментариев и пояснений. Пример структуры:\n"
        f"{json.dumps(schema_hint, ensure_ascii=False)}"
    )

    response = await _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
            {"role": "assistant", "content": format_instructions},
        ],
        temperature=0.1,
        max_tokens=700,
    )

    content = response.choices[0].message.content or "{}"

    if "```" in content:
        content = content.split("```", 2)[1]
        if content.startswith("json"):
            content = content[len("json"):]

    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return {}

    return data


async def parse_object_correction(message: str, current_data: Dict[str, Any]) -> Dict[str, Any]:
    """Определяет, какое поле объекта нужно изменить на основании пользовательского сообщения."""

    context = json.dumps(current_data, ensure_ascii=False)
    prompt = (
        "Пользователь просит изменить данные карточки строительного объекта. "
        "Нужно определить поле и новое значение. Если запрос не про карточку, верни пустой JSON.\n"
        "Доступные поля:\n"
        "- name (название объекта)\n"
        "- address\n"
        "- foreman_name\n"
        "- start_date (формат YYYY-MM-DD)\n"
        "- end_date (формат YYYY-MM-DD)\n"
        "- prepayment, final_payment, estimate_s3, actual_s3_discount, estimate_works, estimate_supplies, estimate_overhead, estimate_transport (числа в рублях)\n"
        "Если пользователь говорит 'облицовка со скидкой', это actual_s3_discount."
    )

    instructions = (
        "Верни JSON вида {\"field\": <имя поля>, \"value\": <значение>, \"confidence\": 0..1}. "
        "Если не удалось понять поле, верни {}. Если значение отсутствует, верни {}."
    )

    response = await _openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "assistant", "content": f"Текущие данные: {context}"},
            {"role": "user", "content": message},
            {"role": "assistant", "content": instructions},
        ],
        temperature=0.0,
        max_tokens=200,
    )

    raw = response.choices[0].message.content or "{}"
    if "```" in raw:
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[len("json"):]

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}

    return parsed if isinstance(parsed, dict) else {}



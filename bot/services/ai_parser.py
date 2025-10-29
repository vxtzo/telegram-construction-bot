"""
AI сервис для парсинга текста и голоса через OpenAI API
"""
import json
from datetime import datetime
from decimal import Decimal
from typing import Dict, Optional
import aiofiles
from openai import AsyncOpenAI
from bot.config import config

# Инициализация OpenAI клиента
client = AsyncOpenAI(api_key=config.OPENAI_API_KEY)


async def parse_expense_text(text: str, expense_type: str = "расход") -> Dict:
    """
    Парсинг текста расхода через GPT-4
    
    Args:
        text: Текст от пользователя
        expense_type: Тип расхода (расходники/транспорт/накладные)
        
    Returns:
        Dict с ключами: date, amount, description
    """
    
    system_prompt = f"""Ты - ассистент для парсинга информации о {expense_type}.
Твоя задача - извлечь из текста пользователя:
1. Дату (date) - в формате YYYY-MM-DD. Если не указана, используй сегодняшнюю дату: {datetime.now().strftime('%Y-%m-%d')}
2. Сумму (amount) - числом в рублях (без символа рубля)
3. Описание (description) - краткое описание расхода
4. Источник оплаты (payment_source):
   - "PERSONAL" если упоминается: "со своих денег", "к компенсации", "к возмещению", "свои деньги", "оплатил сам", "из своих"
   - "COMPANY" если упоминается: "оплачено фирмой", "с карты ИП", "оплачено компанией", "фирма оплатила"
   - По умолчанию "COMPANY" если не указано

Верни результат СТРОГО в формате JSON:
{{"date": "YYYY-MM-DD", "amount": число, "description": "текст", "payment_source": "COMPANY или PERSONAL"}}

Примеры:
- "Купил цемент на 5000 рублей 25 октября, со своих денег" -> {{"date": "2025-10-25", "amount": 5000, "description": "Цемент", "payment_source": "PERSONAL"}}
- "Доставка материалов 3500р оплачено фирмой" -> {{"date": "{datetime.now().strftime('%Y-%m-%d')}", "amount": 3500, "description": "Доставка материалов", "payment_source": "COMPANY"}}
- "Вчера потратил 2000 на инструменты к компенсации" -> {{"date": "{(datetime.now().replace(day=datetime.now().day-1)).strftime('%Y-%m-%d')}", "amount": 2000, "description": "Инструменты", "payment_source": "PERSONAL"}}
"""
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",  # Используем более быструю модель
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            max_tokens=150
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Парсим JSON
        # Убираем возможные markdown блоки
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(result_text)
        
        # Валидация и конвертация в верхний регистр
        payment_source = data.get("payment_source", "COMPANY").upper()
        if payment_source not in ["COMPANY", "PERSONAL"]:
            payment_source = "COMPANY"
        
        return {
            "date": data.get("date", datetime.now().strftime("%Y-%m-%d")),
            "amount": Decimal(str(data.get("amount", 0))),
            "description": data.get("description", ""),
            "payment_source": payment_source
        }
        
    except Exception as e:
        print(f"❌ Ошибка парсинга расхода: {e}")
        # Возвращаем дефолтные значения
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "amount": Decimal(0),
            "description": text[:200],  # Берем начало текста как описание
            "payment_source": "COMPANY"  # По умолчанию - оплата фирмой
        }


async def parse_advance_text(text: str) -> Dict:
    """
    Парсинг текста аванса через GPT-4
    
    Returns:
        Dict с ключами: worker_name, work_type, amount, date
    """
    
    system_prompt = f"""Ты - ассистент для парсинга информации об авансах рабочим.
Твоя задача - извлечь из текста:
1. Имя рабочего (worker_name)
2. Вид работ (work_type)
3. Сумму аванса (amount) - числом в рублях
4. Дату (date) - в формате YYYY-MM-DD. Если не указана, используй сегодняшнюю: {datetime.now().strftime('%Y-%m-%d')}

Верни результат СТРОГО в формате JSON:
{{"worker_name": "имя", "work_type": "вид работ", "amount": число, "date": "YYYY-MM-DD"}}

Примеры:
- "Иванов, кладка кирпича, 15000 рублей, 20 октября" -> {{"worker_name": "Иванов", "work_type": "Кладка кирпича", "amount": 15000, "date": "2025-10-20"}}
- "Аванс Петрову 10000р на облицовку" -> {{"worker_name": "Петров", "work_type": "Облицовка", "amount": 10000, "date": "{datetime.now().strftime('%Y-%m-%d')}"}}
"""
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text}
            ],
            temperature=0.1,
            max_tokens=150
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Убираем markdown
        if "```json" in result_text:
            result_text = result_text.split("```json")[1].split("```")[0].strip()
        elif "```" in result_text:
            result_text = result_text.split("```")[1].split("```")[0].strip()
        
        data = json.loads(result_text)
        
        return {
            "worker_name": data.get("worker_name", ""),
            "work_type": data.get("work_type", ""),
            "amount": Decimal(str(data.get("amount", 0))),
            "date": data.get("date", datetime.now().strftime("%Y-%m-%d"))
        }
        
    except Exception as e:
        print(f"❌ Ошибка парсинга аванса: {e}")
        return {
            "worker_name": "",
            "work_type": "",
            "amount": Decimal(0),
            "date": datetime.now().strftime("%Y-%m-%d")
        }


async def transcribe_voice(file_path: str) -> str:
    """
    Транскрибация голосового сообщения через Whisper API
    
    Args:
        file_path: Путь к аудио файлу
        
    Returns:
        Распознанный текст
    """
    try:
        async with aiofiles.open(file_path, 'rb') as audio_file:
            audio_data = await audio_file.read()
        
        # Создаем временный file-like объект
        from io import BytesIO
        audio_bytes = BytesIO(audio_data)
        audio_bytes.name = file_path  # Whisper требует имя файла
        
        response = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_bytes,
            language="ru"
        )
        
        return response.text
        
    except Exception as e:
        print(f"❌ Ошибка транскрибации голоса: {e}")
        return ""


async def parse_voice_expense(file_path: str, expense_type: str = "расход") -> Dict:
    """
    Полный цикл: транскрибация голоса + парсинг данных
    
    Args:
        file_path: Путь к аудио файлу
        expense_type: Тип расхода
        
    Returns:
        Dict с распарсенными данными
    """
    # Сначала распознаем голос
    text = await transcribe_voice(file_path)
    
    if not text:
        return {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "amount": Decimal(0),
            "description": "Ошибка распознавания голоса",
            "payment_source": "COMPANY"
        }
    
    # Затем парсим текст
    return await parse_expense_text(text, expense_type)


async def parse_voice_advance(file_path: str) -> Dict:
    """
    Полный цикл: транскрибация голоса + парсинг данных аванса
    """
    text = await transcribe_voice(file_path)
    
    if not text:
        return {
            "worker_name": "",
            "work_type": "",
            "amount": Decimal(0),
            "date": datetime.now().strftime("%Y-%m-%d")
        }
    
    return await parse_advance_text(text)



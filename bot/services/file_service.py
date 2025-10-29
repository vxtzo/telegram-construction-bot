"""
Сервис для работы с файлами (хранение в PostgreSQL)
"""
import io
from typing import Optional, BinaryIO
from aiogram import Bot
from aiogram.types import PhotoSize, Document, File as TgFile
from database.models import File, FileType
from database.crud import create_file, get_files_by_object
from sqlalchemy.ext.asyncio import AsyncSession


class FileService:
    """Класс для работы с файлами"""
    
    def __init__(self, bot: Bot):
        """
        Инициализация сервиса
        
        Args:
            bot: Экземпляр бота
        """
        self.bot = bot
    
    async def save_photo(
        self,
        session: AsyncSession,
        photo: PhotoSize,
        object_id: int,
        file_type: FileType = FileType.PHOTO
    ) -> Optional[File]:
        """
        Сохранить фото в базу данных
        
        Args:
            session: Сессия БД
            photo: Объект фото из Telegram
            object_id: ID объекта
            file_type: Тип файла
            
        Returns:
            Объект File или None
        """
        try:
            # Получаем файл из Telegram
            file: TgFile = await self.bot.get_file(photo.file_id)
            
            # Скачиваем файл в память
            file_bytes = io.BytesIO()
            await self.bot.download_file(file.file_path, file_bytes)
            file_content = file_bytes.getvalue()
            
            # Сохраняем в БД
            file_data = {
                "object_id": object_id,
                "file_type": file_type,
                "telegram_file_id": photo.file_id,
                "file_data": file_content,
                "filename": f"photo_{photo.file_id}.jpg",
                "mime_type": "image/jpeg",
                "file_size": len(file_content)
            }
            
            db_file = await create_file(session, file_data)
            print(f"✅ Фото сохранено в БД (ID: {db_file.id}, размер: {len(file_content)} байт)")
            return db_file
            
        except Exception as e:
            print(f"❌ Ошибка сохранения фото: {e}")
            return None
    
    async def save_document(
        self,
        session: AsyncSession,
        document: Document,
        object_id: int,
        file_type: FileType = FileType.DOCUMENT
    ) -> Optional[File]:
        """
        Сохранить документ в базу данных
        
        Args:
            session: Сессия БД
            document: Объект документа из Telegram
            object_id: ID объекта
            file_type: Тип файла
            
        Returns:
            Объект File или None
        """
        try:
            # Получаем файл из Telegram
            file: TgFile = await self.bot.get_file(document.file_id)
            
            # Скачиваем файл в память
            file_bytes = io.BytesIO()
            await self.bot.download_file(file.file_path, file_bytes)
            file_content = file_bytes.getvalue()
            
            # Сохраняем в БД
            file_data = {
                "object_id": object_id,
                "file_type": file_type,
                "telegram_file_id": document.file_id,
                "file_data": file_content,
                "filename": document.file_name or f"document_{document.file_id}",
                "mime_type": document.mime_type,
                "file_size": document.file_size
            }
            
            db_file = await create_file(session, file_data)
            print(f"✅ Документ сохранён в БД (ID: {db_file.id}, размер: {document.file_size} байт)")
            return db_file
            
        except Exception as e:
            print(f"❌ Ошибка сохранения документа: {e}")
            return None
    
    async def get_file_data(
        self,
        session: AsyncSession,
        file_id: int
    ) -> Optional[bytes]:
        """
        Получить данные файла из БД
        
        Args:
            session: Сессия БД
            file_id: ID файла
            
        Returns:
            Бинарные данные файла или None
        """
        try:
            from database.crud import get_file_by_id
            file = await get_file_by_id(session, file_id)
            
            if file and file.file_data:
                return file.file_data
            
            return None
            
        except Exception as e:
            print(f"❌ Ошибка получения файла: {e}")
            return None
    
    async def get_object_files(
        self,
        session: AsyncSession,
        object_id: int,
        file_type: Optional[FileType] = None
    ) -> list[File]:
        """
        Получить список файлов объекта
        
        Args:
            session: Сессия БД
            object_id: ID объекта
            file_type: Фильтр по типу файла (опционально)
            
        Returns:
            Список файлов
        """
        try:
            files = await get_files_by_object(session, object_id)
            
            if file_type:
                files = [f for f in files if f.file_type == file_type]
            
            return files
            
        except Exception as e:
            print(f"❌ Ошибка получения списка файлов: {e}")
            return []


"""
Сервис для работы с Google Drive API
"""
import io
import json
from typing import Optional, Tuple
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from bot.config import config


class GoogleDriveService:
    """Класс для работы с Google Drive"""
    
    def __init__(self):
        """Инициализация сервиса"""
        self.service = None
        self.parent_folder_id = config.GOOGLE_DRIVE_FOLDER_ID
        self._init_service()
    
    def _init_service(self):
        """Инициализация Google Drive API"""
        try:
            if not config.GOOGLE_DRIVE_CREDENTIALS:
                print("⚠️ Google Drive credentials не настроены")
                return
            
            # Создаем credentials из JSON
            credentials = service_account.Credentials.from_service_account_info(
                config.GOOGLE_DRIVE_CREDENTIALS,
                scopes=['https://www.googleapis.com/auth/drive.file']
            )
            
            # Создаем сервис
            self.service = build('drive', 'v3', credentials=credentials)
            print("✅ Google Drive сервис инициализирован")
            
        except Exception as e:
            print(f"❌ Ошибка инициализации Google Drive: {e}")
            self.service = None
    
    def create_folder(self, folder_name: str, parent_folder_id: Optional[str] = None) -> Optional[str]:
        """
        Создать папку на Google Drive
        
        Args:
            folder_name: Название папки
            parent_folder_id: ID родительской папки
            
        Returns:
            ID созданной папки или None
        """
        if not self.service:
            return None
        
        try:
            parent_id = parent_folder_id or self.parent_folder_id
            
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id] if parent_id else []
            }
            
            folder = self.service.files().create(
                body=file_metadata,
                fields='id, webViewLink'
            ).execute()
            
            # Делаем папку доступной для просмотра по ссылке
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            self.service.permissions().create(
                fileId=folder['id'],
                body=permission
            ).execute()
            
            print(f"✅ Создана папка '{folder_name}' (ID: {folder['id']})")
            return folder['id']
            
        except Exception as e:
            print(f"❌ Ошибка создания папки '{folder_name}': {e}")
            return None
    
    def create_object_folders(self, object_name: str) -> Optional[Tuple[str, str, str, str]]:
        """
        Создать структуру папок для объекта
        
        Args:
            object_name: Название объекта
            
        Returns:
            Tuple (main_folder_id, receipts_folder_id, photos_folder_id, docs_folder_id) или None
        """
        if not self.service:
            return None
        
        try:
            # Создаем главную папку объекта
            main_folder_id = self.create_folder(object_name)
            if not main_folder_id:
                return None
            
            # Создаем подпапки
            receipts_folder_id = self.create_folder("Чеки", main_folder_id)
            photos_folder_id = self.create_folder("Фото", main_folder_id)
            docs_folder_id = self.create_folder("Документы", main_folder_id)
            
            return (main_folder_id, receipts_folder_id, photos_folder_id, docs_folder_id)
            
        except Exception as e:
            print(f"❌ Ошибка создания структуры папок для '{object_name}': {e}")
            return None
    
    def upload_file(
        self,
        file_content: bytes,
        filename: str,
        folder_id: str,
        mime_type: str = 'application/octet-stream'
    ) -> Optional[Tuple[str, str]]:
        """
        Загрузить файл на Google Drive
        
        Args:
            file_content: Содержимое файла в байтах
            filename: Имя файла
            folder_id: ID папки для загрузки
            mime_type: MIME тип файла
            
        Returns:
            Tuple (file_id, web_view_link) или None
        """
        if not self.service:
            return None
        
        try:
            file_metadata = {
                'name': filename,
                'parents': [folder_id]
            }
            
            media = MediaIoBaseUpload(
                io.BytesIO(file_content),
                mimetype=mime_type,
                resumable=True
            )
            
            file = self.service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink, webContentLink'
            ).execute()
            
            # Делаем файл доступным для просмотра
            permission = {
                'type': 'anyone',
                'role': 'reader'
            }
            self.service.permissions().create(
                fileId=file['id'],
                body=permission
            ).execute()
            
            print(f"✅ Загружен файл '{filename}' (ID: {file['id']})")
            return (file['id'], file.get('webViewLink', ''))
            
        except Exception as e:
            print(f"❌ Ошибка загрузки файла '{filename}': {e}")
            return None
    
    def get_folder_link(self, folder_id: str) -> Optional[str]:
        """
        Получить ссылку на папку
        
        Args:
            folder_id: ID папки
            
        Returns:
            Ссылка на папку или None
        """
        if not self.service:
            return None
        
        try:
            folder = self.service.files().get(
                fileId=folder_id,
                fields='webViewLink'
            ).execute()
            
            return folder.get('webViewLink', '')
            
        except Exception as e:
            print(f"❌ Ошибка получения ссылки на папку: {e}")
            return None


# Глобальный экземпляр сервиса
gdrive_service = GoogleDriveService()


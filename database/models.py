"""
SQLAlchemy модели для базы данных
"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Integer, String, BigInteger, Boolean, DateTime, 
    Numeric, Text, Enum, ForeignKey, UniqueConstraint, LargeBinary
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
import enum


class Base(DeclarativeBase):
    """Базовый класс для всех моделей"""
    pass


class UserRole(str, enum.Enum):
    """Роли пользователей"""
    ADMIN = "admin"
    FOREMAN = "foreman"


class ObjectStatus(str, enum.Enum):
    """Статусы объектов"""
    ACTIVE = "active"
    COMPLETED = "completed"


class ExpenseType(str, enum.Enum):
    """Типы расходов"""
    SUPPLIES = "supplies"  # Расходники
    TRANSPORT = "transport"  # Транспортные
    OVERHEAD = "overhead"  # Накладные


class FileType(str, enum.Enum):
    """Типы файлов"""
    PHOTO = "photo"
    RECEIPT = "receipt"
    DOCUMENT = "document"


class User(Base):
    """Пользователи системы"""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255))
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), nullable=False, default=UserRole.FOREMAN)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    created_objects: Mapped[list["ConstructionObject"]] = relationship(
        "ConstructionObject", back_populates="creator", foreign_keys="ConstructionObject.created_by"
    )
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="added_by_user")
    advances: Mapped[list["Advance"]] = relationship("Advance", back_populates="added_by_user")
    
    def __repr__(self):
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, role={self.role})>"


class ConstructionObject(Base):
    """Строительные объекты"""
    __tablename__ = "objects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text)
    foreman_name: Mapped[Optional[str]] = mapped_column(String(255))
    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime)
    status: Mapped[ObjectStatus] = mapped_column(
        Enum(ObjectStatus), default=ObjectStatus.ACTIVE, nullable=False, index=True
    )
    
    # Финансы
    prepayment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    final_payment: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    
    # Смета
    estimate_s3: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    estimate_works: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    estimate_supplies: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    estimate_overhead: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    estimate_transport: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    
    # Факт (С3 со скидкой заполняется вручную)
    actual_s3_discount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    
    # Метаданные
    created_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Relationships
    creator: Mapped["User"] = relationship("User", back_populates="created_objects", foreign_keys=[created_by])
    expenses: Mapped[list["Expense"]] = relationship("Expense", back_populates="construction_object", cascade="all, delete-orphan")
    advances: Mapped[list["Advance"]] = relationship("Advance", back_populates="construction_object", cascade="all, delete-orphan")
    files: Mapped[list["File"]] = relationship("File", back_populates="construction_object", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<ConstructionObject(id={self.id}, name='{self.name}', status={self.status})>"


class Expense(Base):
    """Расходы (расходники, транспорт, накладные)"""
    __tablename__ = "expenses"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("objects.id"), nullable=False, index=True)
    type: Mapped[ExpenseType] = mapped_column(Enum(ExpenseType), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    photo_url: Mapped[Optional[str]] = mapped_column(String(500))
    added_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    construction_object: Mapped["ConstructionObject"] = relationship("ConstructionObject", back_populates="expenses")
    added_by_user: Mapped["User"] = relationship("User", back_populates="expenses")
    
    def __repr__(self):
        return f"<Expense(id={self.id}, type={self.type}, amount={self.amount})>"


class Advance(Base):
    """Авансы рабочим"""
    __tablename__ = "advances"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("objects.id"), nullable=False, index=True)
    worker_name: Mapped[str] = mapped_column(String(255), nullable=False)
    work_type: Mapped[str] = mapped_column(String(500), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    added_by: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    construction_object: Mapped["ConstructionObject"] = relationship("ConstructionObject", back_populates="advances")
    added_by_user: Mapped["User"] = relationship("User", back_populates="advances")
    
    def __repr__(self):
        return f"<Advance(id={self.id}, worker='{self.worker_name}', amount={self.amount})>"


class File(Base):
    """Файлы (фото, чеки, документы)"""
    __tablename__ = "files"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    object_id: Mapped[int] = mapped_column(Integer, ForeignKey("objects.id"), nullable=False, index=True)
    file_type: Mapped[FileType] = mapped_column(Enum(FileType), nullable=False)
    telegram_file_id: Mapped[str] = mapped_column(String(255), nullable=False)  # ID файла в Telegram
    file_data: Mapped[Optional[bytes]] = mapped_column(LargeBinary)  # Бинарные данные файла
    filename: Mapped[Optional[str]] = mapped_column(String(500))
    mime_type: Mapped[Optional[str]] = mapped_column(String(100))
    file_size: Mapped[Optional[int]] = mapped_column(Integer)  # Размер в байтах
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    construction_object: Mapped["ConstructionObject"] = relationship("ConstructionObject", back_populates="files")
    
    def __repr__(self):
        return f"<File(id={self.id}, type={self.file_type}, filename='{self.filename}')>"


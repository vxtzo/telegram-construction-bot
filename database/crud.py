"""
CRUD операции для работы с базой данных
"""
from typing import Optional, List
from datetime import datetime
from decimal import Decimal
from sqlalchemy import select, update, delete, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import (
    User, UserRole, ConstructionObject, ObjectStatus,
    Expense, ExpenseType, Advance, File, FileType
)


# ============ USER CRUD ============

async def get_user_by_telegram_id(session: AsyncSession, telegram_id: int) -> Optional[User]:
    """Получить пользователя по telegram_id"""
    result = await session.execute(
        select(User).where(User.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def create_user(
    session: AsyncSession,
    telegram_id: int,
    role: UserRole,
    username: Optional[str] = None,
    full_name: Optional[str] = None
) -> User:
    """Создать нового пользователя"""
    user = User(
        telegram_id=telegram_id,
        username=username,
        full_name=full_name,
        role=role,
        is_active=True
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def update_user_active_status(
    session: AsyncSession,
    telegram_id: int,
    is_active: bool
) -> Optional[User]:
    """Обновить статус активности пользователя"""
    result = await session.execute(
        update(User)
        .where(User.telegram_id == telegram_id)
        .values(is_active=is_active)
        .returning(User)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def get_all_users(session: AsyncSession) -> List[User]:
    """Получить всех пользователей"""
    result = await session.execute(select(User).order_by(User.created_at.desc()))
    return list(result.scalars().all())


async def delete_user(session: AsyncSession, telegram_id: int) -> bool:
    """Удалить пользователя"""
    result = await session.execute(
        delete(User).where(User.telegram_id == telegram_id)
    )
    await session.commit()
    return result.rowcount > 0


# ============ CONSTRUCTION OBJECT CRUD ============

async def create_object(
    session: AsyncSession,
    name: str,
    created_by: int,
    address: Optional[str] = None,
    foreman_name: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    prepayment: Decimal = Decimal(0),
    final_payment: Decimal = Decimal(0),
    estimate_s3: Decimal = Decimal(0),
    estimate_works: Decimal = Decimal(0),
    estimate_supplies: Decimal = Decimal(0),
    estimate_overhead: Decimal = Decimal(0),
    estimate_transport: Decimal = Decimal(0),
    actual_s3_discount: Decimal = Decimal(0),
) -> ConstructionObject:
    """Создать новый строительный объект"""
    obj = ConstructionObject(
        name=name,
        address=address,
        foreman_name=foreman_name,
        start_date=start_date,
        end_date=end_date,
        prepayment=prepayment,
        final_payment=final_payment,
        estimate_s3=estimate_s3,
        estimate_works=estimate_works,
        estimate_supplies=estimate_supplies,
        estimate_overhead=estimate_overhead,
        estimate_transport=estimate_transport,
        actual_s3_discount=actual_s3_discount,
        created_by=created_by,
        status=ObjectStatus.ACTIVE
    )
    session.add(obj)
    await session.commit()
    await session.refresh(obj)
    return obj


async def get_object_by_id(
    session: AsyncSession,
    object_id: int,
    load_relations: bool = True
) -> Optional[ConstructionObject]:
    """Получить объект по ID"""
    query = select(ConstructionObject).where(ConstructionObject.id == object_id)
    
    if load_relations:
        query = query.options(
            selectinload(ConstructionObject.expenses),
            selectinload(ConstructionObject.advances),
            selectinload(ConstructionObject.files),
            selectinload(ConstructionObject.creator)
        )
    
    result = await session.execute(query)
    return result.scalar_one_or_none()


async def get_objects_by_status(
    session: AsyncSession,
    status: ObjectStatus,
    load_relations: bool = False
) -> List[ConstructionObject]:
    """Получить объекты по статусу"""
    query = select(ConstructionObject).where(ConstructionObject.status == status).order_by(ConstructionObject.created_at.desc())
    
    if load_relations:
        query = query.options(
            selectinload(ConstructionObject.expenses),
            selectinload(ConstructionObject.advances),
            selectinload(ConstructionObject.creator)
        )
    
    result = await session.execute(query)
    return list(result.scalars().all())


async def update_object_status(
    session: AsyncSession,
    object_id: int,
    status: ObjectStatus
) -> Optional[ConstructionObject]:
    """Обновить статус объекта"""
    completed_at = datetime.utcnow() if status == ObjectStatus.COMPLETED else None
    
    result = await session.execute(
        update(ConstructionObject)
        .where(ConstructionObject.id == object_id)
        .values(status=status, completed_at=completed_at)
        .returning(ConstructionObject)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def update_object_gdrive_folder(
    session: AsyncSession,
    object_id: int,
    folder_id: str
) -> Optional[ConstructionObject]:
    """Обновить Google Drive folder ID объекта"""
    result = await session.execute(
        update(ConstructionObject)
        .where(ConstructionObject.id == object_id)
        .values(gdrive_folder_id=folder_id)
        .returning(ConstructionObject)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def update_object_s3_discount(
    session: AsyncSession,
    object_id: int,
    actual_s3_discount: Decimal
) -> Optional[ConstructionObject]:
    """Обновить фактическую стоимость С3 со скидкой"""
    result = await session.execute(
        update(ConstructionObject)
        .where(ConstructionObject.id == object_id)
        .values(actual_s3_discount=actual_s3_discount)
        .returning(ConstructionObject)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def get_objects_by_period(
    session: AsyncSession,
    start_date: datetime,
    end_date: datetime
) -> List[ConstructionObject]:
    """Получить объекты за период"""
    result = await session.execute(
        select(ConstructionObject)
        .where(
            or_(
                and_(
                    ConstructionObject.start_date >= start_date,
                    ConstructionObject.start_date <= end_date
                ),
                and_(
                    ConstructionObject.completed_at >= start_date,
                    ConstructionObject.completed_at <= end_date
                )
            )
        )
        .options(
            selectinload(ConstructionObject.expenses),
            selectinload(ConstructionObject.advances)
        )
        .order_by(ConstructionObject.created_at.desc())
    )
    return list(result.scalars().all())


# ============ EXPENSE CRUD ============

async def create_expense(
    session: AsyncSession,
    object_id: int,
    expense_type: ExpenseType,
    amount: Decimal,
    description: str,
    date: datetime,
    added_by: int,
    photo_url: Optional[str] = None
) -> Expense:
    """Создать расход"""
    expense = Expense(
        object_id=object_id,
        type=expense_type,
        amount=amount,
        description=description,
        date=date,
        photo_url=photo_url,
        added_by=added_by
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense


async def get_expenses_by_object(
    session: AsyncSession,
    object_id: int,
    expense_type: Optional[ExpenseType] = None
) -> List[Expense]:
    """Получить расходы по объекту"""
    query = select(Expense).where(Expense.object_id == object_id)
    
    if expense_type:
        query = query.where(Expense.type == expense_type)
    
    query = query.order_by(Expense.date.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


async def get_total_expenses_by_type(
    session: AsyncSession,
    object_id: int,
    expense_type: ExpenseType
) -> Decimal:
    """Получить сумму расходов определенного типа по объекту"""
    result = await session.execute(
        select(func.sum(Expense.amount))
        .where(and_(Expense.object_id == object_id, Expense.type == expense_type))
    )
    total = result.scalar()
    return Decimal(total) if total else Decimal(0)


# ============ ADVANCE CRUD ============

async def create_advance(
    session: AsyncSession,
    object_id: int,
    worker_name: str,
    work_type: str,
    amount: Decimal,
    date: datetime,
    added_by: int
) -> Advance:
    """Создать аванс"""
    advance = Advance(
        object_id=object_id,
        worker_name=worker_name,
        work_type=work_type,
        amount=amount,
        date=date,
        added_by=added_by
    )
    session.add(advance)
    await session.commit()
    await session.refresh(advance)
    return advance


async def get_advances_by_object(session: AsyncSession, object_id: int) -> List[Advance]:
    """Получить авансы по объекту"""
    result = await session.execute(
        select(Advance)
        .where(Advance.object_id == object_id)
        .order_by(Advance.date.desc())
    )
    return list(result.scalars().all())


async def get_total_advances(session: AsyncSession, object_id: int) -> Decimal:
    """Получить общую сумму авансов по объекту"""
    result = await session.execute(
        select(func.sum(Advance.amount)).where(Advance.object_id == object_id)
    )
    total = result.scalar()
    return Decimal(total) if total else Decimal(0)


# ============ FILE CRUD ============

async def create_file(
    session: AsyncSession,
    object_id: int,
    file_type: FileType,
    telegram_file_id: Optional[str] = None,
    gdrive_file_id: Optional[str] = None,
    gdrive_url: Optional[str] = None,
    filename: Optional[str] = None
) -> File:
    """Создать запись о файле"""
    file = File(
        object_id=object_id,
        file_type=file_type,
        telegram_file_id=telegram_file_id,
        gdrive_file_id=gdrive_file_id,
        gdrive_url=gdrive_url,
        filename=filename
    )
    session.add(file)
    await session.commit()
    await session.refresh(file)
    return file


async def get_files_by_object(
    session: AsyncSession,
    object_id: int,
    file_type: Optional[FileType] = None
) -> List[File]:
    """Получить файлы по объекту"""
    query = select(File).where(File.object_id == object_id)
    
    if file_type:
        query = query.where(File.file_type == file_type)
    
    query = query.order_by(File.uploaded_at.desc())
    result = await session.execute(query)
    return list(result.scalars().all())


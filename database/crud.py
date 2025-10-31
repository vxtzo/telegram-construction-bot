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
    Expense, ExpenseType, Advance, File, FileType,
    PaymentSource, CompensationStatus, ObjectLog, ObjectLogType,
    CompanyExpense, CompanyRecurringExpense, CompanyExpenseLog
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
    photo_url: Optional[str] = None,
    payment_source: PaymentSource = PaymentSource.COMPANY,
    compensation_status: Optional[CompensationStatus] = None
) -> Expense:
    """Создать расход"""
    expense = Expense(
        object_id=object_id,
        type=expense_type,
        amount=amount,
        description=description,
        date=date,
        photo_url=photo_url,
        added_by=added_by,
        payment_source=payment_source,
        compensation_status=compensation_status
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


async def get_expense_by_id(session: AsyncSession, expense_id: int) -> Optional[Expense]:
    """Получить расход по ID"""
    result = await session.execute(
        select(Expense).where(Expense.id == expense_id)
    )
    return result.scalar_one_or_none()


async def update_compensation_status(
    session: AsyncSession,
    expense_id: int,
    status: CompensationStatus
) -> Optional[Expense]:
    """Обновить статус компенсации расхода"""
    result = await session.execute(
        update(Expense)
        .where(Expense.id == expense_id)
        .values(compensation_status=status)
        .returning(Expense)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def get_pending_compensations_by_object(
    session: AsyncSession,
    object_id: int
) -> List[Expense]:
    """Получить расходы, ожидающие компенсации по объекту"""
    result = await session.execute(
        select(Expense)
        .where(
            and_(
                Expense.object_id == object_id,
                Expense.payment_source == PaymentSource.PERSONAL,
                Expense.compensation_status == CompensationStatus.PENDING
            )
        )
        .order_by(Expense.date.desc())
    )
    return list(result.scalars().all())


async def update_expense(
    session: AsyncSession,
    expense_id: int,
    **fields
) -> Optional[Expense]:
    """Обновить данные расхода"""
    if not fields:
        return await get_expense_by_id(session, expense_id)

    result = await session.execute(
        update(Expense)
        .where(Expense.id == expense_id)
        .values(**fields)
        .returning(Expense)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def delete_expense(session: AsyncSession, expense_id: int) -> bool:
    """Удалить расход"""
    result = await session.execute(
        delete(Expense).where(Expense.id == expense_id)
    )
    await session.commit()
    return result.rowcount > 0


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


async def get_advance_by_id(session: AsyncSession, advance_id: int) -> Optional[Advance]:
    """Получить аванс по ID"""
    result = await session.execute(
        select(Advance).where(Advance.id == advance_id)
    )
    return result.scalar_one_or_none()


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


async def update_advance(
    session: AsyncSession,
    advance_id: int,
    **fields
) -> Optional[Advance]:
    """Обновить данные аванса"""
    if not fields:
        return None

    result = await session.execute(
        update(Advance)
        .where(Advance.id == advance_id)
        .values(**fields)
        .returning(Advance)
    )
    await session.commit()
    return result.scalar_one_or_none()


async def delete_advance(session: AsyncSession, advance_id: int) -> bool:
    """Удалить аванс"""
    result = await session.execute(
        delete(Advance).where(Advance.id == advance_id)
    )
    await session.commit()
    return result.rowcount > 0


# ============ LOG CRUD ============


async def create_object_log(
    session: AsyncSession,
    object_id: int,
    action: ObjectLogType,
    description: str,
    user_id: Optional[int] = None
) -> ObjectLog:
    """Создать запись лога объекта"""
    log = ObjectLog(
        object_id=object_id,
        user_id=user_id,
        action=action,
        description=description
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def get_object_logs(
    session: AsyncSession,
    object_id: int,
    page: int,
    page_size: int
) -> tuple[list[ObjectLog], int]:
    """Получить логи по объекту с пагинацией"""
    total_result = await session.execute(
        select(func.count(ObjectLog.id)).where(ObjectLog.object_id == object_id)
    )
    total = total_result.scalar() or 0

    if total == 0:
        return [], 0

    page = max(page, 1)
    offset = (page - 1) * page_size

    result = await session.execute(
        select(ObjectLog)
        .where(ObjectLog.object_id == object_id)
        .order_by(ObjectLog.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .options(selectinload(ObjectLog.user))
    )

    logs = list(result.scalars().all())
    return logs, total


# ============ FILE CRUD ============

async def create_file(session: AsyncSession, file_data: dict) -> File:
    """Создать запись о файле"""
    file = File(**file_data)
    session.add(file)
    await session.commit()
    await session.refresh(file)
    return file


async def get_file_by_id(session: AsyncSession, file_id: int) -> Optional[File]:
    """Получить файл по ID"""
    result = await session.execute(
        select(File).where(File.id == file_id)
    )
    return result.scalar_one_or_none()


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


# ============ COMPANY EXPENSES CRUD ============


async def create_company_expense(
    session: AsyncSession,
    category: str,
    amount: Decimal,
    date: datetime,
    description: Optional[str],
    added_by: Optional[int],
) -> CompanyExpense:
    expense = CompanyExpense(
        category=category.strip(),
        amount=amount,
        date=date,
        description=description.strip() if description else None,
        added_by=added_by,
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense


async def create_company_recurring_expense(
    session: AsyncSession,
    category: str,
    amount: Decimal,
    period_month: int,
    period_year: int,
    description: Optional[str],
    added_by: Optional[int],
) -> CompanyRecurringExpense:
    expense = CompanyRecurringExpense(
        category=category.strip(),
        amount=amount,
        period_month=period_month,
        period_year=period_year,
        description=description.strip() if description else None,
        added_by=added_by,
    )
    session.add(expense)
    await session.commit()
    await session.refresh(expense)
    return expense


async def delete_company_expense(session: AsyncSession, expense_id: int) -> bool:
    result = await session.execute(
        delete(CompanyExpense).where(CompanyExpense.id == expense_id)
    )
    await session.commit()
    return result.rowcount > 0


async def delete_company_recurring_expense(session: AsyncSession, expense_id: int) -> bool:
    result = await session.execute(
        delete(CompanyRecurringExpense).where(CompanyRecurringExpense.id == expense_id)
    )
    await session.commit()
    return result.rowcount > 0


async def get_company_expense_categories(session: AsyncSession) -> List[tuple[str, Decimal, int]]:
    result = await session.execute(
        select(
            CompanyExpense.category,
            func.sum(CompanyExpense.amount),
            func.count(CompanyExpense.id),
        ).group_by(CompanyExpense.category)
        .order_by(func.sum(CompanyExpense.amount).desc())
    )
    return [(row[0], Decimal(row[1]), row[2]) for row in result.all()]


async def get_company_expenses_by_category(session: AsyncSession, category: str) -> List[CompanyExpense]:
    result = await session.execute(
        select(CompanyExpense)
        .where(CompanyExpense.category == category)
        .order_by(CompanyExpense.date.desc())
    )
    return list(result.scalars().all())


async def get_company_recurring_categories(session: AsyncSession) -> List[tuple[str, Decimal, int]]:
    result = await session.execute(
        select(
            CompanyRecurringExpense.category,
            func.sum(CompanyRecurringExpense.amount),
            func.count(CompanyRecurringExpense.id),
        ).group_by(CompanyRecurringExpense.category)
        .order_by(func.sum(CompanyRecurringExpense.amount).desc())
    )
    return [(row[0], Decimal(row[1]), row[2]) for row in result.all()]


async def get_company_recurring_by_category(session: AsyncSession, category: str) -> List[CompanyRecurringExpense]:
    result = await session.execute(
        select(CompanyRecurringExpense)
        .where(CompanyRecurringExpense.category == category)
        .order_by(CompanyRecurringExpense.period_year.desc(), CompanyRecurringExpense.period_month.desc())
    )
    return list(result.scalars().all())


async def get_company_expenses_for_period(
    session: AsyncSession,
    start_date: datetime,
    end_date: datetime,
) -> dict:
    one_time_query = await session.execute(
        select(func.sum(CompanyExpense.amount)).where(
            and_(CompanyExpense.date >= start_date, CompanyExpense.date <= end_date)
        )
    )
    one_time_total = one_time_query.scalar() or 0

    recurring_query = await session.execute(
        select(func.sum(CompanyRecurringExpense.amount)).where(
            and_(
                CompanyRecurringExpense.period_year * 100 + CompanyRecurringExpense.period_month >= start_date.year * 100 + start_date.month,
                CompanyRecurringExpense.period_year * 100 + CompanyRecurringExpense.period_month <= end_date.year * 100 + end_date.month,
            )
        )
    )
    recurring_total = recurring_query.scalar() or 0

    return {
        "one_time": Decimal(one_time_total),
        "recurring": Decimal(recurring_total),
        "total": Decimal(one_time_total) + Decimal(recurring_total),
    }


async def create_company_expense_log(
    session: AsyncSession,
    expense_type: str,
    entity_id: int,
    action: str,
    description: str,
    user_id: Optional[int] = None,
) -> CompanyExpenseLog:
    log = CompanyExpenseLog(
        expense_type=expense_type,
        entity_id=entity_id,
        action=action,
        description=description,
        user_id=user_id,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def get_company_expense_logs(
    session: AsyncSession,
    expense_type: str,
    entity_id: int,
    limit: int = 20,
) -> List[CompanyExpenseLog]:
    result = await session.execute(
        select(CompanyExpenseLog)
        .where(
            and_(
                CompanyExpenseLog.expense_type == expense_type,
                CompanyExpenseLog.entity_id == entity_id,
            )
        )
        .order_by(CompanyExpenseLog.created_at.desc())
        .limit(limit)
        .options(selectinload(CompanyExpenseLog.user))
    )
    return list(result.scalars().all())


# ============ OBJECT MANAGEMENT ============


async def delete_object(session: AsyncSession, object_id: int) -> bool:
    result = await session.execute(
        select(ConstructionObject).where(ConstructionObject.id == object_id)
    )
    obj = result.scalar_one_or_none()
    if not obj:
        return False

    await session.delete(obj)
    await session.commit()
    return True

